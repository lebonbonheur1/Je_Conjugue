# Save this as Conjugaison.py

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, SlideTransition, ScreenManager
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform
from kivy.graphics import Color, Rectangle
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown 
from kivy.clock import Clock 

from kivy.core.audio import SoundLoader 
import sqlite3
import os
from datetime import datetime
import time # Importation de 'time' pour le calcul de durée

# --- Configuration des couleurs ---
COLOR_CONJUG = (0.8, 0.1, 0.1, 1)  
COLOR_BACKGROUND = (0.95, 0.95, 0.95, 1) 
COLOR_NAV_BUTTON = (0.2, 0.4, 0.7, 1) 

# Fonction utilitaire create_image_button remplacée par un simple créateur de bouton
def create_text_button(text, button_style):
    """Crée un bouton standard avec du texte."""
    btn = Button(text=text, background_normal='', background_down='', **button_style) 
    btn.background_color = button_style.get('background_color', (1, 1, 1, 1))
    return btn
    
# --- CLASSE POUR L'AUTO-COMPLÉTION (Utilise DropDown) --
class AutoCompleteTextInput(TextInput):
    """
    TextInput qui affiche des suggestions via DropDown.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dropdown = DropDown(auto_dismiss=False, max_height=dp(150))
        self.all_suggestions = []
        self.is_selecting = False 
        
        self.bind(focus=self.on_focus_change)
        self.bind(text=self.on_text_change) 

    def on_text_change(self, instance, value):
        """Déclenche la recherche de suggestion de manière insensible à la casse et filtrée."""
        if self.is_selecting:
            self.is_selecting = False
            return
            
        value_strip = value.strip()
        
        if not self.focus or not value_strip:
            self.dropdown.dismiss()
            return

        value_lower = value_strip.lower()
        matches = [s for s in self.all_suggestions if s.lower().startswith(value_lower)]
        
        if matches:
            self.dropdown.clear_widgets()
            for match in matches[:5]:
                btn = Button(
                    text=match, 
                    size_hint_y=None, 
                    height=dp(30), 
                    font_size='12sp',
                    background_color=COLOR_BACKGROUND
                )
                btn.bind(on_release=lambda b, text=match: self.select_suggestion(text))
                self.dropdown.add_widget(btn)
                
            self.dropdown.height = dp(30) * min(5, len(matches))
            
            Clock.schedule_once(lambda dt: self.open_dropdown_safely(), 0)

        else:
            self.dropdown.dismiss()
    
    def open_dropdown_safely(self):
        """Ouvre le DropDown si le TextInput a toujours le focus et qu'il n'est pas déjà ouvert."""
        if self.focus and not self.dropdown.attach_to:
            self.dropdown.open(self)

    def select_suggestion(self, text):
        """Action au clic: sélectionne la suggestion, ferme le DropDown et lance la recherche."""
        
        self.is_selecting = True 
        self.text = text
        Clock.schedule_once(lambda dt: self.parent.parent.parent.parent.search_and_load_conjugation(None, search_only_verb=True), 0)
        self.dropdown.dismiss()


    def on_focus_change(self, instance, value):
        """Ferme le DropDown lorsque le TextInput perd le focus."""
        if not value:
            self.dropdown.dismiss()
            
# La classe principale hérite de Screen
class ConjugaisonScreen(Screen):
    # --- AJOUT: Chemins et variables pour l'enregistrement d'activité ---
    ACTIVITY_DB_PATH = '_91Rafine_Config.db'
    MODULE_NAME = "Conjugaison"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.db_path = '_91Rafine_Config.db'
        
        # Variables de Session d'Activité
        self.session_id = None
        self.session_start_time = None 
        self.consulted_verbs = set() # Utiliser un Set pour stocker les verbes uniques consultés

        self.conjugaisons = [] 
        self.current_index = -1
        self.audio_sound = None 
        self.current_conjugation_id = None 
        
        self.all_modes = []
        self.all_temps = {} 
        self.all_verbes_data = {} 
        
        self.current_font_size = 12 
        self.min_font_size = 10
        self.max_font_size = 30
        
        self.header_labels = [] 

        if platform != 'android':
            Window.size = (dp(440), dp(600))

        main_layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        # --- 1. Zone de Recherche Avancée ---
        self.search_layout_container = self.create_search_selectors()
        main_layout.add_widget(self.search_layout_container)

        # --- 2. Label de Titre / Affichage du Verbe ---
        self.title_label = Label(
            text="Chargement des conjugaisons...", 
            font_size='16sp', 
            size_hint_y=None, 
            height=dp(40), 
            halign='center',
            valign='middle',
            markup=True
        )
        main_layout.add_widget(self.title_label)
        
        # --- 2.5. Nouvelle section pour Rejouer et Retour ---
        top_buttons_layout = BoxLayout(orientation='horizontal', spacing=dp(5), size_hint_y=None, height=dp(40))
        
        button_style_top = {
            'font_size': '14sp', 
            'bold': True, 
            'color': (1, 1, 1, 1), 
            'background_color': COLOR_NAV_BUTTON, 
            'size_hint_y': None, 
            'height': dp(40),
            'size_hint_x': 1 # Pour la répartition égale des deux boutons
        }
        
        # Bouton Rejouer Audio (Gauche)
        self.btn_reload = create_text_button('Rejouer Audio', button_style_top)
        self.btn_reload.bind(on_press=self.reload_audio)
        top_buttons_layout.add_widget(self.btn_reload)
        
        # Bouton Retour (Droit)
        self.btn_back = create_text_button('Retour', button_style_top)
        self.btn_back.bind(on_press=self.on_back_button)
        top_buttons_layout.add_widget(self.btn_back)

        main_layout.add_widget(top_buttons_layout)


        # --- 3. Tableau de Conjugaison ---
        self.conjugation_grid = self.create_conjugation_grid()
        main_layout.add_widget(self.conjugation_grid)

        # --- 4. Boutons de Navigation (Bas) ---
        nav_combined_layout = BoxLayout(orientation='horizontal', spacing=dp(5), size_hint_y=None, height=dp(35))
        
        # Style uniforme pour les boutons restants (Précédent, Suivant, A+, A-)
        button_style_nav = {
            'font_size': '12sp', 
            'bold': True, 
            'color': (1, 1, 1, 1), 
            'background_color': COLOR_NAV_BUTTON, 
            'size_hint_y': None, 
            'height': dp(35),
            'size_hint_x': 1 # Distribue les 4 boutons également
        }
        
        # Bouton Précédent (Texte)
        self.btn_previous = create_text_button('Précédent', button_style_nav)
        self.btn_previous.bind(on_press=self.load_previous)
        nav_combined_layout.add_widget(self.btn_previous)

        # Bouton Suivant (Texte)
        self.btn_next = create_text_button('Suivant', button_style_nav)
        self.btn_next.bind(on_press=self.load_next)
        nav_combined_layout.add_widget(self.btn_next)
        
        # Bouton + (Texte)
        self.btn_font_plus = create_text_button('A+', button_style_nav)
        self.btn_font_plus.bind(on_press=self.increase_font_size)
        nav_combined_layout.add_widget(self.btn_font_plus)
        
        # Bouton - (Texte)
        self.btn_font_minus = create_text_button('A-', button_style_nav)
        self.btn_font_minus.bind(on_press=self.decrease_font_size)
        nav_combined_layout.add_widget(self.btn_font_minus)
        
        main_layout.add_widget(nav_combined_layout)
        
        self.add_widget(main_layout)
        
    # --- NOUVELLE FONCTION: Gère la connexion à la BD d'activité ---
    def get_activity_db_connection(self):
        """Retourne une connexion à la base de données d'activité."""
        try:
            return sqlite3.connect(self.ACTIVITY_DB_PATH)
        except sqlite3.Error as e:
            print(f"Erreur de connexion à la BD d'activité: {e}")
            return None

    # --- NOUVELLE FONCTION: Démarre une session ---
    def start_session(self):
        """Enregistre le début de la session dans Tableau_de_bord."""
        self.session_start_time = time.time()
        self.consulted_verbs = set() # Réinitialiser la liste des verbes

        conn = self.get_activity_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                open_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Initialisation de l'entrée dans Tableau_de_bord
                # Duree_session, Titre, Date_Heure_fermeture seront mis à jour à la fin
                cursor.execute("""
                    INSERT INTO Tableau_de_bord (Nom_du_module, Titre, Date_Heure_ouverture, Date_Heure_fermeture, Duree_session)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.MODULE_NAME, "Session en cours...", open_time, "N/A", "0"))
                
                self.session_id = cursor.lastrowid
                conn.commit()
                # print(f"Session démarrée avec ID: {self.session_id} à {open_time}")

            except sqlite3.Error as e:
                print(f"Erreur à l'enregistrement du début de session: {e}")
                self.session_id = None
            finally:
                conn.close()

    # --- NOUVELLE FONCTION: Termine une session ---
    def end_session(self):
        """Calcule la durée, agrège les verbes, et met à jour l'enregistrement de la session."""
        if self.session_id is None or self.session_start_time is None:
            return

        end_time = time.time()
        duration_seconds = end_time - self.session_start_time
        duration_minutes = round(duration_seconds / 60, 2)
        
        close_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        consulted_verbs_str = "; ".join(sorted(list(self.consulted_verbs)))
        
        # S'assurer que le champ Titre ne dépasse pas une taille raisonnable si la BD impose une limite.
        # Ici, on tronque à 500 caractères comme mesure de précaution.
        if len(consulted_verbs_str) > 500:
            consulted_verbs_str = consulted_verbs_str[:497] + "..."
            
        if not consulted_verbs_str:
            consulted_verbs_str = "Aucun verbe consulté"
            
        conn = self.get_activity_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE Tableau_de_bord
                    SET Titre = ?, 
                        Date_Heure_fermeture = ?, 
                        Duree_session = ?
                    WHERE Id = ?
                """, (consulted_verbs_str, close_time_str, str(duration_minutes), self.session_id))
                
                conn.commit()
                # print(f"Session ID {self.session_id} terminée. Durée: {duration_minutes} min. Verbes: {consulted_verbs_str}")
            except sqlite3.Error as e:
                print(f"Erreur à l'enregistrement de la fin de session: {e}")
            finally:
                conn.close()
                
        # Réinitialisation après la fin de la session
        self.session_id = None
        self.session_start_time = None
        self.consulted_verbs = set()


    def on_enter(self, *args):
        """
        Déclenchement du chargement des données, lecture du premier audio ET démarrage de la session.
        """
        # --- AJOUT: Démarrer la session d'activité ---
        self.start_session()
        
        if not self.conjugaisons: 
            self.load_all_data()
        elif self.current_conjugation_id is not None:
            # Rejouer l'audio si l'utilisateur revient à l'écran
            self.load_and_play_audio(self.current_conjugation_id)

    def create_search_selectors(self):
        """Crée le layout pour la recherche avancée."""
        
        container = GridLayout(
            cols=1, 
            spacing=dp(5), 
            size_hint_y=None,
            height=dp(180) 
        ) 

        style_interactive = {
            'font_size': '12sp', 
            'bold': True, 
            'color': (1, 1, 1, 1), 
            'background_color': COLOR_NAV_BUTTON, 
            'size_hint_y': None, 
            'height': dp(35)
        }
        
        def create_line(label_text, widget):
            line = BoxLayout(orientation='horizontal', spacing=dp(5), size_hint_y=None, height=dp(35))
            label = Label(text=f"[b]{label_text}[/b]:", markup=True, size_hint_x=0.25, halign='left', valign='middle', font_size='12sp')
            line.add_widget(label)
            line.add_widget(widget)
            return line

        # 1. Ligne Mode
        self.mode_spinner = Spinner(text='Chargement...', values=['Chargement...'], **style_interactive)
        self.mode_spinner.bind(text=self.on_mode_selected)
        container.add_widget(create_line("Mode", self.mode_spinner))
        
        # 2. Ligne Temps
        self.temps_spinner = Spinner(text='(Sélectionnez Mode)', values=['(Sélectionnez Mode)'], **style_interactive)
        self.temps_spinner.bind(text=self.on_temps_selected)
        container.add_widget(create_line("Temps", self.temps_spinner))
        
        # 3. Ligne Verbe (TextInput)
        self.verbe_input = AutoCompleteTextInput(
            font_size='14sp',
            foreground_color=(1, 1, 1, 1), 
            hint_text_color=(0.7, 0.7, 0.7, 1), 
            background_color=COLOR_NAV_BUTTON, 
            **{'size_hint_y': None, 'height': dp(35)}
        )
        container.add_widget(create_line("Verbe", self.verbe_input))
        
        # Label d'information
        self.search_action_label = Label(
            text="Taper le verbe ou cliquer 'Rechercher' pour trouver.", 
            font_size='10sp', 
            color=(0.4, 0.4, 0.4, 1), 
            size_hint_y=None, 
            height=dp(20), 
            halign='center', 
            valign='top'
        )
        container.add_widget(self.search_action_label)
        
        # 4. Bouton de recherche
        btn_search = Button(text="Rechercher Verbe (Mode/Temps)", **style_interactive)
        btn_search.bind(on_press=self.search_and_load_conjugation)
        container.add_widget(btn_search)
        
        return container

    def create_conjugation_grid(self):
        """Crée la grille d'affichage de la conjugaison (Tableau en bas de l'écran)."""
        grid_container = BoxLayout(orientation='vertical', size_hint_y=1)
        
        self.conjugation_table = GridLayout(cols=2, spacing=dp(2), size_hint_y=None, height=dp(180)) 

        self.conjugation_labels = []
        personnes = [
            ("1ère p. singulier", COLOR_CONJUG), ("2ème p. singulier", COLOR_CONJUG), ("3ème p. singulier", COLOR_CONJUG),
            ("1ère p. pluriel", COLOR_CONJUG), ("2ème p. pluriel", COLOR_CONJUG), ("3ème p. pluriel", COLOR_CONJUG),
        ]
        
        self.header_labels = []
        for text, color in personnes:
            person_label = Label(
                text=text, 
                color=(1, 1, 1, 1), 
                size_hint_y=None, 
                height=dp(30), 
                bold=True, 
                font_size=f'{self.current_font_size}sp', 
                halign='center', 
                valign='middle'
            )
            with person_label.canvas.before:
                Color(*color)
                person_label.person_rect = Rectangle(size=person_label.size, pos=person_label.pos)
            person_label.bind(size=lambda instance, value: setattr(instance.person_rect, 'size', value),
                              pos=lambda instance, value: setattr(instance.person_rect, 'pos', value))
            self.header_labels.append(person_label)

            conjug_label = Label(text="...", color=(0, 0, 0, 1), size_hint_y=None, height=dp(30), font_size=f'{self.current_font_size}sp', halign='center', valign='middle')
            with conjug_label.canvas.before:
                Color(*COLOR_BACKGROUND)
                conjug_label.conjug_rect = Rectangle(size=conjug_label.size, pos=conjug_label.pos)
            conjug_label.bind(size=lambda instance, value: setattr(instance.conjug_rect, 'size', value),
                              pos=lambda instance, value: setattr(instance.conjug_rect, 'pos', value))
            self.conjugation_labels.append(conjug_label)
            
        for i in range(6): 
            self.conjugation_table.add_widget(self.header_labels[i]) 
            self.conjugation_table.add_widget(self.conjugation_labels[i]) 

        grid_container.add_widget(self.conjugation_table)
        return grid_container

    def update_conjugation_font_size(self):
        """Applique la nouvelle taille de police à tous les labels (personne et forme) ET ajuste la hauteur de la grille."""
        
        line_height = max(dp(30), dp(self.current_font_size + 10)) 
        
        total_height = (line_height * 6) + (dp(2) * 5)
        
        self.conjugation_table.height = total_height 
        
        new_size_str = f'{self.current_font_size}sp'
        
        for label in self.header_labels:
            label.font_size = new_size_str
            label.height = line_height
        
        for label in self.conjugation_labels:
            label.font_size = new_size_str
            label.height = line_height

    def increase_font_size(self, instance):
        """Augmente la taille de police du tableau."""
        if self.current_font_size < self.max_font_size:
            self.current_font_size += 2 
            self.update_conjugation_font_size()

    def decrease_font_size(self, instance):
        """Diminue la taille de police du tableau."""
        if self.current_font_size > self.min_font_size:
            self.current_font_size -= 2 
            self.update_conjugation_font_size()

    def load_all_data(self):
        """Charge toutes les conjugaisons pour le défilement et les données pour la recherche."""
        if not os.path.exists(self.db_path):
            self.title_label.text = "[color=ff0000]ERREUR : Base de données Conjugaison.db manquante![/color]"
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            COLUMNS = "Id, Verbe_infinitif, Mode, Temps, Singulier_1, Singulier_2, Singulier_3, Pluriel_1, Pluriel_2, Pluriel_3"

            cursor.execute(f"SELECT {COLUMNS} FROM Conjugaison ORDER BY Id")
            self.conjugaisons = cursor.fetchall()
            
            cursor.execute("SELECT DISTINCT TRIM(Mode) FROM Conjugaison ORDER BY 1")
            self.all_modes = [row[0] for row in cursor.fetchall()]
            
            for mode in self.all_modes:
                cursor.execute("SELECT DISTINCT TRIM(Temps) FROM Conjugaison WHERE TRIM(Mode) = ? ORDER BY 1", (mode,))
                temps_list = [row[0] for row in cursor.fetchall()]
                self.all_temps[mode] = temps_list

                for temps in temps_list:
                    cursor.execute("SELECT DISTINCT TRIM(Verbe_infinitif) FROM Conjugaison WHERE TRIM(Mode) = ? AND TRIM(Temps) = ? ORDER BY 1", (mode, temps))
                    self.all_verbes_data[(mode, temps)] = [row[0] for row in cursor.fetchall()] 
            
            conn.close()

            if self.all_modes:
                self.mode_spinner.values = self.all_modes
                self.mode_spinner.text = self.all_modes[0] 
                self.on_mode_selected(None, self.all_modes[0], initial_load=True) 
            
            if self.conjugaisons:
                # Lecture de l'audio au premier chargement
                self.load_conjugation(0, skip_audio=False) 
            else:
                self.title_label.text = "[color=ff0000]Aucune conjugaison trouvée dans la base de données.[/color]"

        except sqlite3.Error as e:
            self.title_label.text = f"[color=ff0000]ERREUR BD : {e}[/color]"

    def load_conjugation(self, index, skip_audio=False):
        """Charge et affiche une conjugaison spécifique par index, et joue l'audio."""
        if not self.conjugaisons or index < 0 or index >= len(self.conjugaisons):
            return

        self.current_index = index
        data = self.conjugaisons[self.current_index]
        
        conjugation_id = data[0]
        self.current_conjugation_id = conjugation_id 

        verb_inf = data[1]
        mode = data[2]
        temps = data[3]
        forms = data[4:] 

        self.title_label.text = f"[b]{verb_inf.upper()}[/b]\n{mode.lower()} - {temps.lower()}"
        
        for i, form in enumerate(forms):
            self.conjugation_labels[i].text = form if form else "..."
            
        # --- AJOUT: Enregistrer le verbe consulté (pour la session d'activité) ---
        self.consulted_verbs.add(verb_inf.strip().lower())

        if not skip_audio:
            self.load_and_play_audio(conjugation_id)
            
    def load_next(self, instance):
        """Passe à l'entrée de conjugaison suivante (Défilement)."""
        if self.conjugaisons:
            next_index = (self.current_index + 1) % len(self.conjugaisons)
            self.load_conjugation(next_index)
            
    def load_previous(self, instance):
        """Passe à l'entrée de conjugaison précédente (Défilement)."""
        if self.conjugaisons:
            prev_index = (self.current_index - 1 + len(self.conjugaisons)) % len(self.conjugaisons)
            self.load_conjugation(prev_index)

    def on_back_button(self, instance):
        """Retourne à l'écran principal ('main')."""
        self.stop_audio() 
        # --- AJOUT: Terminer la session avant de quitter ---
        self.end_session()
        
        if self.manager:
            # CORRECTION : Retourne toujours à l'écran 'main'
            self.manager.transition = SlideTransition(direction='right')
            self.manager.current = 'main' 

    def update_verbe_suggestions(self):
        mode = self.mode_spinner.text
        temps = self.temps_spinner.text
        
        if mode in self.all_temps and temps in self.all_temps.get(mode, []):
            current_suggestions = self.all_verbes_data.get((mode, temps), [])
        else:
            current_suggestions = []
        
        self.verbe_input.all_suggestions = current_suggestions
        self.search_action_label.text = f"Prêt. {len(current_suggestions)} verbes disponibles pour cette sélection."


    def on_mode_selected(self, spinner, text, initial_load=False):
        self.verbe_input.dropdown.dismiss()
        
        if text in self.all_temps:
            temps_list = self.all_temps[text]
            self.temps_spinner.values = temps_list
            if not initial_load and temps_list:
                self.temps_spinner.text = temps_list[0] 
            elif initial_load and temps_list:
                self.temps_spinner.text = temps_list[0] 
        else:
            self.temps_spinner.values = ['(Sélectionnez Mode)']
            self.temps_spinner.text = '(Sélectionnez Mode)'
            
        self.update_verbe_suggestions()


    def on_temps_selected(self, spinner, text):
        self.verbe_input.dropdown.dismiss()
        self.update_verbe_suggestions()
    
    
    def search_and_load_conjugation(self, instance, search_only_verb=False):
        user_input_verb = self.verbe_input.text.strip()
        verb_for_db_query_lower = user_input_verb.lower().strip() 
        
        mode_for_db_query = self.mode_spinner.text.strip()
        temps_for_db_query = self.temps_spinner.text.strip()
        
        if not verb_for_db_query_lower or mode_for_db_query.startswith('Choisir') or temps_for_db_query.startswith('Sélectionnez'):
            self.search_action_label.text = "[color=ff8800]Sélectionnez Mode, Temps et entrez/sélectionnez un Verbe.[/color]"
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            COLUMNS = "Id, Verbe_infinitif, Mode, Temps, Singulier_1, Singulier_2, Singulier_3, Pluriel_1, Pluriel_2, Pluriel_3"

            cursor.execute(f"""
                SELECT {COLUMNS} FROM Conjugaison 
                WHERE LOWER(TRIM(Verbe_infinitif)) = ?  
                AND TRIM(Mode) = ? 
                AND TRIM(Temps) = ?
            """, (verb_for_db_query_lower, mode_for_db_query, temps_for_db_query))
            
            data = cursor.fetchone()
            conn.close()
            
            if data:
                conjugation_id = data[0]
                self.current_conjugation_id = conjugation_id 

                status = "...." if not search_only_verb else "...."
                self.title_label.text = f"[b]{data[1].upper()}[/b]\n{data[2].lower()} - {data[3].lower()} [color=00AA00]{status}[/color]"
                
                forms = data[4:]
                for i, form in enumerate(forms):
                    self.conjugation_labels[i].text = form if form else "..."
                
                # --- AJOUT: Enregistrer le verbe consulté (pour la session d'activité) ---
                self.consulted_verbs.add(data[1].strip().lower())
                
                self.load_and_play_audio(conjugation_id)
                self.search_action_label.text = "Conjugaison chargée."
            else:
                self.current_conjugation_id = None 
                self.title_label.text = f"[color=ff0000]Verbe non trouvé : [b]{user_input_verb}[/b][/color]"
                self.search_action_label.text = f"Verbe non trouvé pour la combinaison {mode_for_db_query}/{temps_for_db_query}."
                self.stop_audio()

        except sqlite3.Error as e:
            self.title_label.text = f"[color=ff0000]ERREUR BD : {e}[/color]"
    
    def stop_audio(self):
        """Arrête l'audio en cours de lecture."""
        if self.audio_sound:
            self.audio_sound.stop()
            self.audio_sound = None

    def load_and_play_audio(self, conjugation_id):
        """Charge et joue le fichier audio basé sur l'Id."""
        self.stop_audio() 
        
        audio_folder = os.path.join(os.getcwd(), 'Audio_conjugaison')
        if not os.path.exists(audio_folder):
            self.search_action_label.text = "[color=ff8800]Dossier 'Audio_conjugaison' manquant. Lecture audio impossible.[/color]"
            return

        audio_file = os.path.join(audio_folder, f'{conjugation_id}.mp3')
        self.audio_sound = SoundLoader.load(audio_file)

        if self.audio_sound:
            if os.path.exists(audio_file):
                self.audio_sound.play()
            else:
                self.search_action_label.text = f"[color=ff8800]Fichier audio non trouvé: {conjugation_id}.mp3[/color]"
        else:
            self.search_action_label.text = f"[color=ff8800]Erreur chargement audio pour: {conjugation_id}.mp3[/color]"

    def reload_audio(self, instance):
        """Relance la lecture de l'audio de la conjugaison actuellement affichée."""
        if self.current_conjugation_id is not None:
            self.load_and_play_audio(self.current_conjugation_id)
        else:
            self.search_action_label.text = "[color=ff8800]Aucun verbe sélectionné/affiché pour rejouer l'audio.[/color]"


# --- Classe d'Application de Test ---
class MyApp(App):
    def build(self):
        if not os.path.exists('Audio_conjugaison'):
             os.makedirs('Audio_conjugaison')
             
        # Créer la DB d'activité si elle n'existe pas (pour le test)
        if not os.path.exists(ConjugaisonScreen.ACTIVITY_DB_PATH):
            conn = sqlite3.connect(ConjugaisonScreen.ACTIVITY_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE "Tableau_de_bord" (
                "Id"	INTEGER NOT NULL UNIQUE,
                "Nom_du_module"	TEXT,
                "Titre"	TEXT,
                "Date_Heure_ouverture"	TEXT,
                "Date_Heure_fermeture"	TEXT,
                "Duree_session"	TEXT,
                PRIMARY KEY("Id" AUTOINCREMENT)
                );
            """)
            conn.commit()
            conn.close()

        
        sm = ScreenManager()
        # Seuls les écrans nécessaires pour la navigation (main et conjugaison) sont ajoutés.
        sm.add_widget(Screen(name='main')) 
        
        conjugaison_screen = ConjugaisonScreen(name='conjugaison') 
        sm.add_widget(conjugaison_screen)
        
        # Démarrer sur 'main' pour simuler le menu principal
        sm.current = 'main' 
        return sm

if __name__ == "__main__":
    # Note: Vous devez vous assurer que 'Conjugaison.db' et 
    # '_91Rafine_Config_francais.db' existent dans le répertoire du script
    # pour que le programme fonctionne correctement.
    MyApp().run()