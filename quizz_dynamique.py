# quizz_dynamique.py
import sqlite3
import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput as KivyTextInput
from kivy.uix.spinner import Spinner
from kivy.core.audio import SoundLoader # MODIFICATION: On importe Kivy SoundLoader
# from playsound import playsound # MODIFICATION: On retire l'import de playsound
from kivy.uix.screenmanager import Screen, SlideTransition
from datetime import datetime


DB_FILE = "_91Rafine_Config.db"
ASSETS_DIR = "assets"
TRUE_SOUND = os.path.join(ASSETS_DIR, "true.wav")
FALSE_SOUND = os.path.join(ASSETS_DIR, "false.wav")
# Sons pour le mode déblocage
BRAVO_SOUND = os.path.join(ASSETS_DIR, "bravo.mp3")
RETOUR_SOUND = os.path.join(ASSETS_DIR, "retour.mp3")
TANTATIVE_SOUND = os.path.join(ASSETS_DIR, "tantative.mp3") # Garde MP3, Kivy le gère mieux.
ECHEC_SOUND = os.path.join(ASSETS_DIR, "Echec.mp3")


# Mappage des niveaux pour conversion du format affiché/Recitation au format Quizz_Francais (sans accent)
LEVELS_MAP = {
    "1ère": "1er", "2ème": "2eme", "3ème": "3eme",
    "4ème": "4eme", "5ème": "5eme", "6ème": "6eme"
}
LEVELS_LIST = list(LEVELS_MAP.keys())


class QuizzLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(10)
        self.spacing = dp(10)
        
        self.conn = None
        self.cursor = None

        self.questions = []
        self.index = 0
        self.correct_count = 0
        self.answered_count = 0
        self.session_start_time = datetime.now() 

        # Variables de mode de déblocage
        self.mode = 'Training'
        self.target_level = None 
        self.evaluation_level = None
        self.quiz_counter = 0
        self.quiz_score = 0

        # Timer
        self.timer_seconds_configured = None
        self.time_left = 0
        self.timer_event = None
        self.timer_running = False
        self.timer_stopped_by_user = False

        self.sound_enabled = True

        self.currently_answered = False
        self.correct_index = None
        
        # AJOUT / MODIFICATION: Chargement des sons avec Kivy SoundLoader
        self.sound_true = SoundLoader.load(TRUE_SOUND)
        self.sound_false = SoundLoader.load(FALSE_SOUND)
        self.sound_bravo = SoundLoader.load(BRAVO_SOUND)
        self.sound_retour = SoundLoader.load(RETOUR_SOUND)
        self.sound_tantative = SoundLoader.load(TANTATIVE_SOUND)
        self.sound_echec = SoundLoader.load(ECHEC_SOUND)
        
        # Mappage pour show_simple_popup
        self.sound_map = {
            TRUE_SOUND: self.sound_true,
            FALSE_SOUND: self.sound_false,
            BRAVO_SOUND: self.sound_bravo,
            RETOUR_SOUND: self.sound_retour,
            TANTATIVE_SOUND: self.sound_tantative,
            ECHEC_SOUND: self.sound_echec,
        }
        # FIN MODIFICATION AUDIO
        
        self.build()

    def convert_level_to_db(self, display_level):
        """Convertit le format affiché ('1ère') au format DB Quizz ('1er')."""
        return LEVELS_MAP.get(display_level, display_level)

    def calculate_evaluation_level(self, target_level):
        """Calcule le niveau d'évaluation (niveau choisi - 1)."""
        if target_level == LEVELS_LIST[0]:
            return target_level
        
        try:
            target_index = LEVELS_LIST.index(target_level)
            evaluation_level = LEVELS_LIST[target_index - 1]
            return evaluation_level
        except ValueError:
            return None
    
    def check_db_connection(self):
        """Assure que la connexion DB est ouverte, si non, essaie de l'ouvrir."""
        if self.conn is None:
            try:
                self.conn = sqlite3.connect(DB_FILE)
                self.cursor = self.conn.cursor()
                return True
            except sqlite3.Error as e:
                print(f"Erreur de connexion DB: {e}")
                return False
        return True

    def get_unlock_status(self, level):
        """
        Vérifie l'état de déblocage pour un niveau donné dans la table Recitation.
        Retourne 'oui' si au moins une ligne est débloquée pour cette classe.
        """
        if not self.check_db_connection():
            return 'non' 

        try:
            # Utilisation du format avec accent ('1ère', '2ème', etc.) pour la table Recitation.
            self.cursor.execute("SELECT Debloquer FROM Recitation WHERE Classe = ?", (level,))
            
            results = self.cursor.fetchall()
            if not results:
                return 'inconnu'
            
            # S'il y a des lignes, on vérifie si l'une d'elles est déjà "oui"
            for row in results:
                if row[0].lower() == 'oui':
                    return 'oui'
            
            return 'non'
            
        except sqlite3.Error as e:
            print(f"Erreur de lecture de l'état de déblocage pour {level}: {e}")
            return 'non'

    def start_new_session(self):
        """
        Gère la connexion DB, réinitialise l'heure de début de session et charge 
        les questions selon le mode.
        """
        # 1. Gestion de la connexion DB
        if not self.check_db_connection():
            return

        # 2. Chargement des questions
        self.questions = []
        self.index = 0
        self.correct_count = 0
        self.answered_count = 0
        
        select_cols = "Id, Question, Ass1, Ass2, Ass3, Ass4, Ass5, Bn, Chapitre, Niveau, Explication"
        query = f"SELECT {select_cols} FROM Quizz_Francais"
        
        if self.mode == 'Unlocking' and self.evaluation_level:
            # Conversion du niveau d'évaluation ('2ème') au format Quizz_Francais ('2eme')
            db_level = self.convert_level_to_db(self.evaluation_level)
            # Filtrage par niveau et limite à 30 questions aléatoires
            query += f" WHERE Niveau = '{db_level}' ORDER BY RANDOM() LIMIT 30"
            print(f"Mode Déblocage : Chargement de 30 questions du niveau {self.evaluation_level} (DB Quizz: {db_level})")
        else:
            # Mode Entraînement : Toutes les questions aléatoires
            query += " ORDER BY RANDOM()"
            print("Mode Entraînement : Chargement de toutes les questions aléatoires")

        try:
            self.cursor.execute(query)
            self.questions = self.cursor.fetchall()
        except sqlite3.OperationalError as e:
            self.questions = []
            print(f"Avertissement: Erreur de requête DB: {e}")

        # 3. Réinitialise l'heure de début
        self.session_start_time = datetime.now()
        self.show_question()
        
    # POPUPS DE SÉLECTION DU MODE
    def show_mode_selection_popup(self):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text="Choisissez le mode \nd'utilisation du Quizz :", size_hint_y=0.3))

        btn_training = Button(text="Mode Entraînement", size_hint_y=0.3)
        btn_unlocking = Button(text="Mode Déblocage", size_hint_y=0.3)
        
        content.add_widget(btn_training)
        content.add_widget(btn_unlocking)

        self.mode_popup = Popup(title="MODULE QUIZZ – MODES D’UTILISATION", content=content, size_hint=(0.8, 0.5), auto_dismiss=False)

        def select_training(instance):
            self.mode = 'Training'
            self.mode_popup.dismiss()
            self.start_new_session()

        def select_unlocking(instance):
            self.mode_popup.dismiss()
            self.show_level_selection_popup()

        btn_training.bind(on_release=select_training)
        btn_unlocking.bind(on_release=select_unlocking)
        self.mode_popup.open()
        
    def show_level_selection_popup(self):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        
        content.add_widget(Label(text="Sélectionnez \nle niveau à débloquer :", size_hint_y=0.3))

        self.choix_Niveau_spiner = Spinner(
            text='Choisir un niveau',
            values=LEVELS_LIST,
            size_hint=(1, 0.2)
        )
        content.add_widget(self.choix_Niveau_spiner)

        btn_start_quiz = Button(text="Lancer le Quiz \nde Déblocage", size_hint_y=0.3)
        content.add_widget(btn_start_quiz)

        level_popup = Popup(title="Mode Déblocage – Sélection du Niveau", content=content, size_hint=(0.8, 0.5), auto_dismiss=False)

        def start_unlocking_quiz(instance):
            target_level = self.choix_Niveau_spiner.text
            if target_level not in LEVELS_MAP:
                return 

            # LOGIQUE DE CONTRÔLE DE DÉBLOCAGE
            status = self.get_unlock_status(target_level)
            
            if status == 'oui':
                # Niveau déjà débloqué
                level_popup.dismiss()
                self.show_simple_popup(
                    title="Attention !",
                    message="Oups ! Les chapitres \nque vous tentez de \ndébloquer sont déjà\ndébloqués.",
                    sound_path=TANTATIVE_SOUND, 
                    on_dismiss_callback=lambda: self.show_mode_selection_popup()
                )
                return

            self.target_level = target_level
            self.evaluation_level = self.calculate_evaluation_level(target_level)
            
            if not self.evaluation_level:
                return 

            level_popup.dismiss()
            self.mode = 'Unlocking'
            self.quiz_score = 0
            self.quiz_counter = 0
            self.start_new_session()

        btn_start_quiz.bind(on_release=start_unlocking_quiz)
        level_popup.open()
    
    def build(self):
        if platform != "android":
            Window.size = (dp(440), dp(650))

        # Haut
        top_layout = BoxLayout(orientation="horizontal", size_hint_y=0.09, spacing=dp(5))
        self.btn_increase = Button(text="+")
        self.btn_increase.bind(on_release=self.increase_font) 
        top_layout.add_widget(self.btn_increase)

        self.btn_decrease = Button(text="-")
        self.btn_decrease.bind(on_release=self.decrease_font)
        top_layout.add_widget(self.btn_decrease)

        self.btn_on_off = Button(text="Son: ON")
        self.btn_on_off.bind(on_release=self.toggle_sound)
        top_layout.add_widget(self.btn_on_off)

        self.btn_timer = Button(text="Timer")
        self.btn_timer.bind(on_release=self.timer_button_pressed)
        top_layout.add_widget(self.btn_timer)

        self.score_label = Button(text="0/0", size_hint_x=2, disabled=True)
        top_layout.add_widget(self.score_label)

        self.add_widget(top_layout)

        # Centre
        center_layout = BoxLayout(orientation="vertical", spacing=dp(8))

        q_scroll = ScrollView(size_hint_y=0.25)
        self.question_text = TextInput(readonly=True, multiline=True, size_hint=(1, None))
        q_scroll.add_widget(self.question_text)
        center_layout.add_widget(q_scroll)

        self.assertions_layout = GridLayout(cols=1, spacing=dp(6), size_hint=(1, None))
        self.assertions_layout.bind(minimum_height=self.assertions_layout.setter('height'))
        self.assertion_buttons = []
        for i in range(5):
            btn = Button(
                text=f"Ass{i+1}",
                size_hint=(1, None),
                background_normal='',
                background_down='',
                background_color=(1, 1, 1, 1),
                color=(0, 0, 0, 1),
                # PARAMÈTRES POUR LE MULTILIGNE DYNAMIQUE ET CENTRÉ
                text_size=(None, None), 
                valign='middle',
                halign='center',
                height=dp(48)
            )
            
            # BIND 1: Définit text_size à la largeur du bouton (moins une marge) pour forcer le wrap.
            btn.bind(width=lambda instance, value: setattr(instance, 'text_size', (value - dp(20), None)))
            
            # BIND 2: Ajuste la hauteur du bouton à la hauteur du texte rendu (texture_size).
            btn.bind(texture_size=lambda instance, value: setattr(instance, 'height', max(dp(48), value[1] + dp(10))))
            
            btn._index = i
            btn.bind(on_release=self.on_assertion_clicked)
            self.assertion_buttons.append(btn)
            self.assertions_layout.add_widget(btn)

        a_scroll = ScrollView(size_hint_y=0.5)
        a_scroll.add_widget(self.assertions_layout)
        center_layout.add_widget(a_scroll)

        e_scroll = ScrollView(size_hint_y=0.15)
        self.explanation_text = TextInput(readonly=True, multiline=True, size_hint=(1, None))
        e_scroll.add_widget(self.explanation_text)
        center_layout.add_widget(e_scroll)

        self.add_widget(center_layout)

        # Bas
        bottom_layout = BoxLayout(orientation="horizontal", size_hint_y=0.09, spacing=dp(10))
        self.btn_previous = Button(text="Précédent")
        self.btn_previous.bind(on_release=self.on_previous)
        bottom_layout.add_widget(self.btn_previous)

        self.btn_return = Button(text="Retour")
        self.btn_return.bind(on_release=self.on_return_to_main)
        bottom_layout.add_widget(self.btn_return)

        self.btn_next = Button(text="Suivant")
        self.btn_next.bind(on_release=self.on_next)
        bottom_layout.add_widget(self.btn_next)

        self.add_widget(bottom_layout)

    def log_session_activity(self):
        if self.conn is None or self.cursor is None:
            print("Erreur: Connexion DB non disponible pour l'enregistrement de session.")
            return

        session_end_time = datetime.now()
        duration = session_end_time - self.session_start_time
        duration_str = str(duration).split('.')[0]
        start_time_str = self.session_start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = session_end_time.strftime("%Y-%m-%d %H:%M:%S")
        module_name = 'QCM'
        title = 'QCM'
        
        try:
            self.cursor.execute("""
                INSERT INTO Tableau_de_bord 
                (Nom_du_module, Titre, Date_Heure_ouverture, Date_Heure_fermeture, Duree_session)
                VALUES (?, ?, ?, ?, ?)
            """, (module_name, title, start_time_str, end_time_str, duration_str))
            
            self.conn.commit()
            print(f"Session QCM enregistrée: {start_time_str} -> {end_time_str} ({duration_str})")
        except sqlite3.Error as e:
            print(f"Erreur d'enregistrement dans la DB (Tableau_de_bord): {e}")

    def on_return_to_main(self, instance):
        self.log_session_activity()
        
        if self.conn:
             self.conn.close()
             self.conn = None
             self.cursor = None

        self.parent.parent.transition = SlideTransition(direction='right')
        self.parent.parent.current = 'main'

    def show_question(self):
        self.currently_answered = False
        for btn in self.assertion_buttons:
            btn.disabled = False
            btn.background_color = (1, 1, 1, 1)
            btn.color = (0, 0, 0, 1)
        self.explanation_text.text = ""

        if not self.questions:
            self.question_text.text = "Aucune question \ndisponible pour \nce mode/niveau."
            return

        if self.index < 0:
            self.index = 0
        if self.index >= len(self.questions):
            self.index = 0

        row = self.questions[self.index]
        (q_id, question,
         ass1, ass2, ass3, ass4, ass5,
         bn, chapitre, niveau, explication) = row

        self.question_text.text = question
        assertions = [ass1, ass2, ass3, ass4, ass5]
        for i, btn in enumerate(self.assertion_buttons):
            btn.text = assertions[i]

        try:
            self.correct_index = int(bn) - 1
        except Exception:
            self.correct_index = None

        self.current_explanation = explication or ""
        
        if self.mode == 'Unlocking':
            # Mise à jour de l'affichage du score avec le numéro de la question
            q_num_display = self.quiz_counter + 1
            if q_num_display > len(self.questions):
                 q_num_display = len(self.questions) 
            self.score_label.text = f"Quiz Déblocage: {self.quiz_score}/{self.quiz_counter} (Q {q_num_display}/{len(self.questions)})"
        else:
            self.score_label.text = f"{self.correct_count}/{self.answered_count}"

        # Timer reset
        if self.timer_seconds_configured is not None and not self.timer_stopped_by_user:
            self.time_left = int(self.timer_seconds_configured)
            self.start_timer()
        else:
            self.stop_timer_event()

    def on_assertion_clicked(self, instance):
        if self.currently_answered:
            return

        chosen_index = instance._index
        is_correct = (chosen_index == self.correct_index)

        if is_correct:
            instance.background_color = (0, 1, 0, 1)
            self.play_true_sound()
            self.correct_count += 1
        else:
            instance.background_color = (1, 0, 0, 1)
            if self.correct_index is not None:
                self.assertion_buttons[self.correct_index].background_color = (0, 1, 0, 1)
            self.play_false_sound()
            
        # Logique de score pour le mode Déblocage
        if self.mode == 'Unlocking':
            if is_correct:
                self.quiz_score += 1
            self.quiz_counter += 1
            
            self.score_label.text = f"Quiz Déblocage: {self.quiz_score}/{self.quiz_counter} (Q {self.quiz_counter}/{len(self.questions)})"

        for btn in self.assertion_buttons:
            btn.disabled = True

        self.explanation_text.text = self.current_explanation
        self.answered_count += 1
        self.currently_answered = True
        
        # Mise à jour du score pour le mode Entraînement
        if self.mode == 'Training':
            self.score_label.text = f"{self.correct_count}/{self.answered_count}"


        self.stop_timer_event()
        
        # Logique de fin de quiz de déblocage ou de transition automatique
        if self.mode == 'Unlocking':
            if self.quiz_counter == len(self.questions):
                # Fin du quiz: Évaluation après un court délai
                Clock.schedule_once(lambda dt: self.end_unlocking_quiz(), 1)
            else:
                # Transition automatique vers la question suivante après 2 secondes
                Clock.schedule_once(lambda dt: self.on_next(None), 2)


    def end_unlocking_quiz(self):
        """Évalue le score final et déclenche le déblocage ou le message d'échec."""
        score = self.quiz_score
        max_score = len(self.questions)
        target_level = self.target_level
        
        self.stop_timer_event()
        
        # LOGIQUE DE VÉRIFICATION DU SCORE
        if score >= 20: # Cas de réussite (>= 20/30)
            # MESSAGE DE RÉUSSITE MIS À JOUR
            message = (f"{score}/{max_score} \nFélicitations ! Vous venez \nde débloquer tous \nles\n"
                       f"chapitres du niveau \nsélectionné")
            sound_path = BRAVO_SOUND # Son de réussite
            self.update_recitation_table(target_level, 'oui')
            
        else: # Cas d'échec (< 20/30)
            # Message d'échec personnalisé (inchangé)
            message = (f"{score}/{max_score}, Tu es presque là !\n"
                       f"Un petit effort de plus \nsur le niveau précédent\n ({self.evaluation_level}), \net tu pourras débloquer\n"
                       f"celui-ci. Allez, \nje crois en toi !")
            sound_path = ECHEC_SOUND 

        # Utilisation de la fonction de pop-up simple
        self.show_simple_popup(
            title="Résultat de l'Évaluation",
            message=message,
            sound_path=sound_path,
            on_dismiss_callback=lambda: self.on_return_to_main(None)
        )
        
        # Réinitialisation des variables du mode Déblocage
        self.mode = 'Training'
        self.quiz_score = 0
        self.quiz_counter = 0
        self.target_level = None
        self.evaluation_level = None

    def update_recitation_table(self, classe, debloquer_status):
        """Met à jour la colonne Debloquer de la table Recitation."""
        if not self.check_db_connection():
            print("Erreur: Connexion DB non disponible pour la mise à jour Recitation.")
            return

        try:
            self.cursor.execute("""
                UPDATE Recitation
                SET Debloquer = ?
                WHERE Classe = ?
            """, (debloquer_status, classe))

            if self.cursor.rowcount > 0:
                self.conn.commit()
                print(f"Table Recitation mise à jour: {self.cursor.rowcount} lignes modifiées pour Classe='{classe}', Debloquer='{debloquer_status}'")
            else:
                print(f"ÉCHEC DE LA MISE À JOUR: Aucune ligne n'a été mise à jour dans Recitation pour la Classe='{classe}'. ")

        except sqlite3.Error as e:
            print(f"Erreur de mise à jour de la table Recitation: {e}")

    def show_simple_popup(self, title, message, sound_path, on_dismiss_callback=None):
        """Affiche un pop-up standard, joue un son et exécute un callback à la fermeture."""
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text=message, size_hint_y=0.7, halign='center', valign='middle'))
        
        btn_ok = Button(text="OK", size_hint_y=0.3)
        content.add_widget(btn_ok)
        
        result_popup = Popup(title=title, content=content, size_hint=(0.7, 0.5), auto_dismiss=False)
        
        if on_dismiss_callback:
            result_popup.bind(on_dismiss=lambda instance: on_dismiss_callback())
            
        btn_ok.bind(on_release=result_popup.dismiss)
        
        result_popup.open()
        
        # MODIFICATION: Utilisation de Kivy SoundLoader
        if self.sound_enabled:
            sound_object = self.sound_map.get(sound_path)
            if sound_object:
                # Kivy .play() est asynchrone et fiable. 
                # L'appel direct suffit.
                sound_object.play()
    
    # ---------------------
    def on_next(self, instance):
        if self.mode == 'Unlocking' and self.quiz_counter >= len(self.questions):
            return
            
        if self.index < len(self.questions) - 1:
            self.index += 1
        else:
            self.index = 0
        self.show_question()

    def on_previous(self, instance):
        if self.mode == 'Unlocking':
            return 
            
        if self.index > 0:
            self.index -= 1
        else:
            self.index = len(self.questions) - 1
        self.show_question()

    # ---------------- Timer ----------------
    def timer_button_pressed(self, instance):
        if self.timer_running:
            self.timer_stopped_by_user = True
            self.stop_timer_event()
            self.btn_timer.text = "Timer (stoppé)"
            return

        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text="Timer (secondes) :"))
        input_sec = KivyTextInput(text=str(self.timer_seconds_configured or 30),
                                  multiline=False, input_filter='int')
        content.add_widget(input_sec)

        btn_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
        btn_ok = Button(text="Activer")
        btn_cancel = Button(text="Annuler")
        btn_box.add_widget(btn_ok)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)

        popup = Popup(title="Configurer Timer", content=content, size_hint=(0.8, 0.4))

        def do_ok(_):
            try:
                n = int(input_sec.text.strip())
                if n <= 0:
                    raise ValueError()
            except Exception:
                n = 30
            self.timer_seconds_configured = n
            self.timer_stopped_by_user = False
            self.time_left = n
            popup.dismiss()
            self.start_timer()

        def do_cancel(_):
            popup.dismiss()

        btn_ok.bind(on_release=do_ok)
        btn_cancel.bind(on_release=do_cancel)
        popup.open()

    def start_timer(self):
        self.stop_timer_event()
        self.timer_event = Clock.schedule_interval(self._timer_tick, 1)
        self.timer_running = True
        self.btn_timer.text = f"{self.time_left}s"

    def _timer_tick(self, dt):
        if self.time_left > 0:
            self.time_left -= 1
            self.btn_timer.text = f"{self.time_left}s"
        else:
            self.on_timer_expire()

    def stop_timer_event(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        self.timer_running = False

    def on_timer_expire(self):
        if self.currently_answered:
            return
        if self.correct_index is not None:
            self.assertion_buttons[self.correct_index].background_color = (0, 1, 0, 1)
        for btn in self.assertion_buttons:
            btn.disabled = True
        self.play_false_sound()
        self.explanation_text.text = self.current_explanation
        self.answered_count += 1
        self.currently_answered = True
        self.score_label.text = f"{self.correct_count}/{self.answered_count}"
        self.stop_timer_event()

    # ---------------- Sons ----------------
    def toggle_sound(self, instance):
        self.sound_enabled = not self.sound_enabled
        self.btn_on_off.text = "Son: ON" if self.sound_enabled else "Son: OFF"

    # MODIFICATION: Utilisation de Kivy SoundLoader
    def play_true_sound(self):
        if self.sound_enabled and self.sound_true:
            self.sound_true.play()

    # MODIFICATION: Utilisation de Kivy SoundLoader
    def play_false_sound(self):
        if self.sound_enabled and self.sound_false:
            self.sound_false.play()

    # ---------------- Police ----------------
    def increase_font(self, instance):
        self.question_text.font_size = self.question_text.font_size + 2
        self.explanation_text.font_size = self.explanation_text.font_size + 2
        for btn in self.assertion_buttons:
            btn.font_size = btn.font_size + 2

    def decrease_font(self, instance):
        self.question_text.font_size = max(10, self.question_text.font_size - 2)
        self.explanation_text.font_size = max(10, self.explanation_text.font_size - 2)
        for btn in self.assertion_buttons:
            btn.font_size = max(10, btn.font_size - 2)

class QuizzScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.quizz_layout_instance = QuizzLayout()
        self.add_widget(self.quizz_layout_instance)
        
    def on_enter(self, *args):
        """Affiche le pop-up de sélection du mode au lieu de démarrer directement."""
        if hasattr(self, 'quizz_layout_instance'):
            self.quizz_layout_instance.show_mode_selection_popup()

