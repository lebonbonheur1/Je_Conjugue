# francais_app.py (ou Gramaire_francais_app.py)

import os
import sys
import sqlite3
import random
from inspect import getsourcefile
from datetime import datetime
from math import floor 

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.properties import NumericProperty, ObjectProperty, BooleanProperty
from kivy.clock import Clock
from kivy.core.audio import SoundLoader 
from kivy.app import App
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.button import Button
from kivy.animation import Animation


# Fonction utilitaire pour trouver le répertoire de script
def get_script_dir(follow_symlinks=True):
    if getattr(sys, 'frozen', False):
        path = os.path.abspath(sys.executable)
    else:
        path = getsourcefile(lambda: 0)
    return os.path.dirname(path)


# Classe pour créer un bouton à partir d'une image
class ImageButton(ButtonBehavior, Image):
    def __init__(self, source, **kwargs):
        super().__init__(**kwargs)
        self.source = source


class FrancaisScreen(Screen):
    # Propriétés et états Kivy
    font_size_sp = NumericProperty(20)
    scroll_speed = NumericProperty(10)
    current_audio = ObjectProperty(None, allownone=True)
    audio_duration = NumericProperty(0)

    current_recitation_id = NumericProperty(0)
    recitation_data = ObjectProperty(None)

    _scroll_event = ObjectProperty(None, allownone=True)
    _start_time = NumericProperty(0)
    _initial_label_y = NumericProperty(0)

    segments = []
    current_segment_index = 0
    segment_duration = 0

    _is_paused = BooleanProperty(False)
    _paused_audio_position = NumericProperty(0)
    _time_of_last_segment_change = NumericProperty(0)
    _remaining_time = NumericProperty(0)

    miroir_active = BooleanProperty(True)
    
    # Propriétés de suivi de session
    session_id = NumericProperty(0) 
    session_start_time = ObjectProperty(None, allownone=True) 
    session_module = ObjectProperty(None, allownone=True) 
    session_titles = [] 


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'francais'
        self.script_dir = get_script_dir()
        self.assets_dir = os.path.join(self.script_dir, "assets")
        self.db_path = os.path.join(self.script_dir, "_91Rafine_Config.db") 
        self.config_db_path = "_91Rafine_Config.db"
        self.recitation_dir = os.path.join(self.script_dir, "Recitation")
        self.conte_dir = os.path.join(self.script_dir, "ConteAudio")

        alert_audio_file = os.path.join(self.assets_dir, "Attention.mp3")
        self.alert_sound = SoundLoader.load(alert_audio_file)

        self.setup_ui()
        Window.bind(on_resize=self.on_resize)
        self.bind(on_enter=self.show_selection_popup)
        self._check_and_create_tableau_de_bord()

    # ==== Fonctions de base de données de configuration (Session) ====
    def get_config_db_connection(self):
        if not os.path.exists(self.config_db_path):
             return None
        try:
            conn = sqlite3.connect(self.config_db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None

    def _check_and_create_tableau_de_bord(self):
        try:
            conn = sqlite3.connect(self.config_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "Tableau_de_bord" (
                   "Id"                   INTEGER NOT NULL UNIQUE,
                   "Nom_du_module"         TEXT,
                   "Titre"                 TEXT,
                   "Date_Heure_ouverture" TEXT,
                   "Date_Heure_fermeture" TEXT,
                   "Duree_session"         TEXT,
                    PRIMARY KEY("Id" AUTOINCREMENT)
                );
            """)
            conn.commit()
        except Exception as e:
            print(f"Erreur de connexion ou de création de table: {e}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    def start_new_session(self, module_name, title):
        conn = self.get_config_db_connection()
        if conn:
            try:
                now = datetime.now()
                date_heure_ouverture = now.strftime('%Y-%m-%d %H:%M:%S') 

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Tableau_de_bord (Nom_du_module, Titre, Date_Heure_ouverture, Date_Heure_fermeture, Duree_session)
                    VALUES (?, ?, ?, ?, ?)
                """, (module_name, title, date_heure_ouverture, None, None))
                
                self.session_id = cursor.lastrowid
                self.session_start_time = now
                self.session_module = module_name
                self.session_titles = [title]
                
                conn.commit()
            except Exception as e:
                print(f"Erreur au démarrage de session: {e}")
                self.session_id = 0
            finally:
                conn.close()

    def update_session_titles(self, title):
        if self.session_id == 0 or not title:
            return
            
        if title not in self.session_titles:
            self.session_titles.append(title)
            titles_str = ", ".join(self.session_titles)
            
            conn = self.get_config_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE Tableau_de_bord SET Titre = ? WHERE Id = ?
                    """, (titles_str, self.session_id))
                    conn.commit()
                except Exception as e:
                    print(f"Erreur de mise à jour des titres: {e}")
                finally:
                    conn.close()

    def end_current_session(self):
        if self.session_id == 0:
            return
            
        conn = self.get_config_db_connection()
        if conn and self.session_start_time:
            try:
                now = datetime.now()
                date_heure_fermeture = now.strftime('%Y-%m-%d %H:%M:%S')

                duration = now - self.session_start_time
                duree_minutes = floor(duration.total_seconds() / 60)
                duree_session_str = f"{duree_minutes} min" 

                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Tableau_de_bord 
                    SET Date_Heure_fermeture = ?, Duree_session = ?
                    WHERE Id = ?
                """, (date_heure_fermeture, duree_session_str, self.session_id))
                
                conn.commit()
            except Exception as e:
                print(f"Erreur de fin de session: {e}")
            finally:
                conn.close()
                
        self.session_id = 0
        self.session_start_time = None
        self.session_module = None
        self.session_titles = []
    # ==== FIN Fonctions de base de données de configuration ====
    
    
    def setup_ui(self):
        root = FloatLayout()
        self.add_widget(root)

        # === Barre haute ===
        self.btn_top = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(70),
                                 spacing=dp(10), padding=[dp(5)])
        root.add_widget(self.btn_top)
        self.btn_top.pos_hint = {"x": 0, "top": 1}

        self.btn_fplus = ImageButton(source=os.path.join(self.assets_dir, "Btn_f+.png"))
        self.btn_fplus.bind(on_press=lambda x: self.change_font_size(2))
        self.btn_fmoins = ImageButton(source=os.path.join(self.assets_dir, "Btn_f-.png"))
        self.btn_fmoins.bind(on_press=lambda x: self.change_font_size(-2))

        self.btn_splus = ImageButton(source=os.path.join(self.assets_dir, "Btn_s+.png"))
        self.btn_splus.bind(on_press=lambda x: self.navigate_segment('next'))
        self.btn_smoins = ImageButton(source=os.path.join(self.assets_dir, "Btn_s-.png"))
        self.btn_smoins.bind(on_press=lambda x: self.navigate_segment('prev'))

        miroir_on_path = os.path.join(self.assets_dir, "miroir_on.png")
        miroir_off_path = os.path.join(self.assets_dir, "miroir_off.png")
        initial_miroir_src = miroir_on_path if os.path.exists(miroir_on_path) else miroir_off_path
        self.btn_miroir = ImageButton(source=initial_miroir_src)
        self.btn_miroir.bind(on_press=self.toggle_miroir)

        self.btn_top.add_widget(self.btn_fplus)
        self.btn_top.add_widget(self.btn_fmoins)
        self.btn_top.add_widget(self.btn_splus)
        self.btn_top.add_widget(self.btn_smoins)
        self.btn_top.add_widget(self.btn_miroir)

        # === Barre basse ===
        self.btn_bar = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(80),
                                 spacing=dp(10), padding=[dp(5)])
        root.add_widget(self.btn_bar)
        self.btn_bar.pos_hint = {"x": 0, "y": 0}

        self.btn_onoff_state = True
        self.btn_onoff = ImageButton(source=os.path.join(self.assets_dir, "Btn_On.png"))
        self.btn_onoff.bind(on_press=self.toggle_onoff)
        self.btn_onoff.disabled_source = os.path.join(self.assets_dir, "Btn_Off.png")

        self.btn_prev = ImageButton(source=os.path.join(self.assets_dir, "Btn_precedent.png"))
        self.btn_prev.bind(on_press=lambda x: self.navigate_recitation('prev'))

        self.btn_play_state = False
        self.btn_play = ImageButton(source=os.path.join(self.assets_dir, "Btn_jouer.png"))
        self.btn_play.bind(on_press=self.toggle_play_pause)

        self.btn_next = ImageButton(source=os.path.join(self.assets_dir, "Btn_suivant.png"))
        self.btn_next.bind(on_press=lambda x: self.navigate_recitation('next'))

        self.btn_back = ImageButton(source=os.path.join(self.assets_dir, "Btn_retour.png"))
        self.btn_back.bind(on_press=self.go_back)

        self.btn_bar.add_widget(self.btn_onoff)
        self.btn_bar.add_widget(self.btn_prev)
        self.btn_bar.add_widget(self.btn_play)
        self.btn_bar.add_widget(self.btn_next)
        self.btn_bar.add_widget(self.btn_back)

        # === Zone centrale ===
        self.text_area = FloatLayout(size_hint=(1, 1))
        root.add_widget(self.text_area)

        self.title_label = Label(
            text="",
            size_hint=(None, None),
            halign="center",
            valign="middle",
            bold=True,
            font_size=self.font_size_sp * 0.9, 
            text_size=(Window.width * 0.9, None) 
        )
        self.title_label.bind(texture_size=self.center_labels)
        self.text_area.add_widget(self.title_label)

        self.mirror_label = Label(
            text="",
            size_hint=(None, None),
            halign="center",
            valign="middle",
            font_size=self.font_size_sp * 0.9,
            color=(1, 1, 0, 1), 
            opacity=0,
            text_size=(Window.width * 0.9, None)
        )
        self.mirror_label.bind(texture_size=self.center_labels)
        self.text_area.add_widget(self.mirror_label)

        self.text_label = Label(
            text="Sélectionnez un module\n,Et un titre pour commencer.",
            size_hint=(None, None),
            halign="center",
            valign="middle",
            font_size=self.font_size_sp,
            opacity=1,
            markup=True,
            text_size=(Window.width * 0.9, None)
        )
        self.text_label.bind(texture_size=self.center_labels)
        self.text_area.add_widget(self.text_label)

        self.center_labels()

    # ==== centrer les labels et positionner le miroir ====
    def center_labels(self, *args):
        
        # 1. Positionner le Titre 
        self.title_label.text_size = (Window.width * 0.9, None) 
        self.title_label.texture_update()
        self.title_label.width = self.title_label.texture_size[0]
        self.title_label.height = self.title_label.texture_size[1]
        
        self.title_label.x = (Window.width - self.title_label.width) / 2
        title_bottom_y = Window.height - dp(100) 
        self.title_label.y = title_bottom_y

        # 2. Détermination de la zone centrale sûre
        SAFE_TITLE_GAP = dp(20) 
        safe_top_limit_y = self.title_label.y - SAFE_TITLE_GAP
        bottom_bar_height = self.btn_bar.height
        new_available_height = safe_top_limit_y - bottom_bar_height

        # 3. Positionner le Label Principal (texte)
        self.text_label.text_size = (Window.width * 0.9, None)
        self.text_label.texture_update()
        self.text_label.width = self.text_label.texture_size[0]
        self.text_label.height = self.text_label.texture_size[1]

        self.text_label.x = (Window.width - self.text_label.width) / 2
        
        centered_y = bottom_bar_height + (new_available_height / 2) - (self.text_label.height / 2)
        max_y = safe_top_limit_y - self.text_label.height
        
        self.text_label.y = min(centered_y, max_y)
        self._initial_label_y = self.text_label.y 


        # 4. Positionner le Label Miroir
        self.mirror_label.text_size = (Window.width * 0.9, None)
        self.mirror_label.texture_update()
        self.mirror_label.width = self.mirror_label.texture_size[0]
        self.mirror_label.height = self.mirror_label.texture_size[1]
        self.mirror_label.x = (Window.width - self.mirror_label.width) / 2
        
        self.mirror_label.y = self.text_label.top + dp(15) 


    # ==== Fonctions de Base de Données (Recitation) ====
    def get_db_connection(self):
        if not os.path.exists(self.db_path):
            return None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None

    def get_classes(self):
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT Classe FROM Recitation ORDER BY Classe")
            classes = [row['Classe'] for row in cursor.fetchall() if row['Classe']]
            conn.close()
            return classes
        return []

    def get_modules(self):
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT Module FROM Recitation WHERE Module <> 'Lecture' ORDER BY Module")
            modules = [row['Module'] for row in cursor.fetchall() if row['Module']]
            conn.close()
            return modules
        return {}

    def get_titles_for_class_and_module(self, classe, module):
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Id, Titre FROM Recitation WHERE Classe=? AND Module=? ORDER BY Titre",
                           (classe, module))
            titles = {row['Titre']: row['Id'] for row in cursor.fetchall()}
            conn.close()
            return titles
        return {}
    
    def get_recitation_by_id(self, recitation_id):
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Recitation WHERE Id=?", (recitation_id,))
            data = cursor.fetchone()
            conn.close()
            return dict(data) if data else None
        return None

    # Fonction pour fermer le popup de sélection SANS quitter l'écran FrancaisScreen
    def dismiss_popup_only(self, *args):
        if hasattr(self, 'popup_dialog') and self.popup_dialog:
            self.popup_dialog.dismiss()
            
    # ==== Popup de sélection ====
    def show_selection_popup(self, *args):
        classes = self.get_classes()
        modules = self.get_modules()
        if not classes or not modules:
            self.btn_onoff.disabled = False
            self.btn_miroir.disabled = False
            self.btn_onoff.source = os.path.join(self.assets_dir, "Btn_On.png" if self.btn_onoff_state else "Btn_Off.png")
            self.btn_miroir.source = os.path.join(self.assets_dir, "miroir_on.png" if self.miroir_active else "miroir_off.png")
            try:
                self.btn_onoff.reload()
                self.btn_miroir.reload()
            except Exception:
                pass
            return

        self.class_spinner = Spinner(text="Niveau", values=classes,
                                     size_hint=(0.8, None), height=dp(40))
        self.module_spinner = Spinner(text="Sélectionner un module", values=modules,
                                      size_hint=(0.8, None), height=dp(40))
        self.title_spinner = Spinner(text="Sélectionner un titre", values=[],
                                     size_hint=(0.8, None), height=dp(40), disabled=True)

        def update_titles(*a):
            classe = self.class_spinner.text
            module = self.module_spinner.text
            if "Sélectionner" in classe or "Sélectionner" in module:
                self.title_spinner.disabled = True
                self.title_spinner.values = []
                self.title_spinner.text = "Sélectionner un titre"
                return

            module_to_query = module

            self.current_class_titles = self.get_titles_for_class_and_module(classe, module_to_query)
            self.title_spinner.values = list(self.current_class_titles.keys())
            self.title_spinner.disabled = False
            self.title_spinner.text = "Sélectionner un titre" 

        self.class_spinner.bind(text=update_titles)
        self.module_spinner.bind(text=update_titles)
        self.title_spinner.bind(text=self.select_recitation)

        content = BoxLayout(orientation="vertical", spacing=dp(20), padding=dp(20))
        content.add_widget(self.class_spinner)
        content.add_widget(self.module_spinner)
        content.add_widget(self.title_spinner)
        
        return_btn = Button(text="Retour", size_hint=(0.8, None), height=dp(40))
        content.add_widget(return_btn)

        self.popup_dialog = Popup(title="Choisir un texte", content=content,
                                  size_hint=(0.8, 0.6), auto_dismiss=False)
        
        return_btn.bind(on_press=self.dismiss_popup_only)
        
        self.popup_dialog.open()

    # === select_recitation: Ajout de la contrainte 'Debloquer' + Alerte Sonore ===
    def select_recitation(self, instance, text):
        if "Sélectionner" in text or not text:
            return
            
        if self.session_id != 0:
            self.end_current_session()
            
        rec_id = self.current_class_titles.get(text)
        if rec_id:
            recitation_data = self.get_recitation_by_id(rec_id)
            
            if not recitation_data:
                self.popup_dialog.dismiss()
                self.text_label.text = "[b]Erreur : Impossible de charger le contenu du titre sélectionné.[/b]"
                self.center_labels()
                return

            debloquer = recitation_data.get('Debloquer', 'non').lower().strip()
            
            if debloquer != 'oui':
                if self.alert_sound:
                    self.alert_sound.play()
                    
                error_popup = Popup(
                    title='Titre Inaccessible', 
                    content=Label(text='Oups !\nLe chapitre que tu veux \nexplorer est verrouillé .\nFais marche arrière \net lance le module QCM.\nSi tu obtiens au moins \n80 % de bonnes réponses, \nce chapitre sera à toi !', 
                                  text_size=(self.popup_dialog.width * 0.7, None), 
                                  halign='center'),
                    size_hint=(0.7, 0.4),
                    auto_dismiss=True
                )
                error_popup.open()
                return 

            self.recitation_data = recitation_data
            self.current_recitation_id = rec_id
            
            chosen_module = self.module_spinner.text
            session_module_name = self.recitation_data.get('Module', chosen_module)
                 
            self.start_new_session(session_module_name, text)
            
            self.load_recitation(self.recitation_data)
            
            self.btn_onoff.disabled = False
            self.btn_miroir.disabled = False
            self.btn_miroir.source = os.path.join(self.assets_dir, "miroir_on.png" if self.miroir_active else "miroir_off.png")
            try:
                self.btn_miroir.reload()
            except Exception:
                pass

            self.popup_dialog.dismiss()

    # ==== Segmentation du texte ====
    def segment_text(self, body, num_segments=5):
        words = body.split()
        if not words:
            return [""]
        segment_length = max(1, len(words) // num_segments)
        segments = []
        for i in range(num_segments):
            start = i * segment_length
            end = (i + 1) * segment_length if i < num_segments - 1 else len(words)
            segment_words = words[start:end]
            lines, current = [], []
            for word in segment_words:
                current.append(word)
                if len(current) >= 5:
                    lines.append(" ".join(current))
                    current = []
            if current:
                lines.append(" ".join(current))
            segments.append("\n".join(lines))
        return segments

    # ==== Chargement & démarrage automatique ====
    def load_recitation(self, data):
        if not data:
            return

        self.stop_playback(reset_state=True)
        
        if self.session_id != 0:
            self.update_session_titles(data.get('Titre', ""))

        self.segments = self.segment_text(data.get('Text', ""))
        self.current_segment_index = 0

        self.title_label.text = data.get('Titre', "").upper() 
        self.center_labels()

        module = (data.get("Module") or "").lower()
        if "récitation" in module or "recitation" in module:
            audio_dir = self.recitation_dir
        elif "conte" in module or "grammaire" in module:
            audio_dir = self.conte_dir
        else:
            audio_dir = self.recitation_dir

        audio_file = os.path.join(audio_dir, f"{data['Id']}.mp3")
        self.current_audio = SoundLoader.load(audio_file) if os.path.exists(audio_file) else None

        self.audio_duration = self.current_audio.length if self.current_audio else max(10, len(data.get('Text', '')) // 5)

        num_segments_effective = max(1, len(self.segments))
        self.segment_duration = self.audio_duration / num_segments_effective

        if self.segments:
            self.current_segment_index = 0
            self.show_next_segment(with_animation=False)

        if self.current_audio and self.btn_onoff_state:
            self.current_audio.play()

        if self.segments:
            self._time_of_last_segment_change = Clock.time()
            self._scroll_event = Clock.schedule_once(lambda dt: self.show_segment_scheduled(), self.segment_duration)

        self.btn_play_state = True
        self._is_paused = False
        self._paused_audio_position = 0
        self._remaining_time = 0
        try:
            self.btn_play.source = os.path.join(self.assets_dir, "Btn_pause.png")
            self.btn_play.reload()
        except Exception:
            pass
        
    # ==== Scheduler pour passer au segment suivant ====
    def show_segment_scheduled(self):
        if self._scroll_event:
            self._scroll_event.cancel()
        self.current_segment_index += 1
        if self.current_segment_index < len(self.segments):
            self.show_next_segment()
            self._time_of_last_segment_change = Clock.time()
            self._scroll_event = Clock.schedule_once(lambda dt: self.show_segment_scheduled(), self.segment_duration)
        else:
            self.stop_playback(reset_state=True)
            if self.segments:
                self.text_label.opacity = 1
                self.text_label.text = self.segments[-1]
                self.center_labels()

    # ==== Mise à jour du label miroir ====
    def update_mirror_label(self):
        if not getattr(self, "miroir_active", True):
            self.mirror_label.text = ""
            self.mirror_label.opacity = 0
            return

        if self.current_segment_index > 0 and self.segments:
            prev_lines = self.segments[self.current_segment_index - 1].split("\n")
            if len(prev_lines) >= 3:
                self.mirror_label.text = "\n".join(prev_lines[-3:])
                self.mirror_label.opacity = 1
            else:
                self.mirror_label.text = ""
                self.mirror_label.opacity = 0
        else:
            self.mirror_label.text = ""
            self.mirror_label.opacity = 0

        self.center_labels()

    # ==== Affichage du segment courant ====
    def show_next_segment(self, with_animation=True):
        if not self.segments:
            self.text_label.text = ""
            return

        segment_text = self.segments[self.current_segment_index]

        try:
            self.update_mirror_label()
        except Exception:
            pass

        if with_animation:
            self.text_label.opacity = 0
            self.text_label.text = segment_text
            self.center_labels()
            start_y = self._initial_label_y + dp(5)
            self.text_label.y = start_y
            anim = Animation(opacity=1, y=self._initial_label_y, duration=0.3, t='out_quad')
            anim.start(self.text_label)
        else:
            Animation.stop_all(self.text_label)
            self.text_label.opacity = 1
            self.text_label.text = segment_text
            self.center_labels()

    # ==== Arrêt / Reset ====
    def stop_playback(self, reset_state=False):
        if self.current_audio:
            try:
                self.current_audio.stop()
            except Exception:
                pass
            if reset_state:
                try:
                    self.current_audio.seek(0)
                except Exception:
                    pass

        if self._scroll_event:
            try:
                self._scroll_event.cancel()
            except Exception:
                pass
            self._scroll_event = None

        Animation.stop_all(self.text_label)

        try:
            self.mirror_label.text = ""
            self.mirror_label.opacity = 0
        except Exception:
            pass

        self.btn_play_state = False
        self._is_paused = True
        self._paused_audio_position = 0
        self._remaining_time = 0
        self._time_of_last_segment_change = 0

        try:
            self.btn_play.source = os.path.join(self.assets_dir, "Btn_jouer.png")
            self.btn_play.reload()
        except Exception:
            pass

    # ==== Toggle On/Off son ====
    def toggle_onoff(self, instance):
        if instance.disabled:
            return
        
        self.btn_onoff_state = not self.btn_onoff_state
        instance.source = os.path.join(self.assets_dir, "Btn_On.png" if self.btn_onoff_state else "Btn_Off.png")
        try:
            instance.reload()
        except Exception:
            pass

        if self.btn_onoff_state and self.btn_play_state and self.current_audio:
            try:
                if self._paused_audio_position and self._paused_audio_position > 0:
                    self.current_audio.seek(self._paused_audio_position)
                else:
                    audio_seek_pos = self.current_segment_index * self.segment_duration
                    self.current_audio.seek(audio_seek_pos)
                self.current_audio.play()
            except Exception:
                pass
        elif not self.btn_onoff_state and self.current_audio and not self._is_paused:
            try:
                self.current_audio.stop()
            except Exception:
                pass

    # ==== Pause / Reprise ====
    def toggle_play_pause(self, instance):
        if self.current_recitation_id == 0:
            return

        if self._is_paused:
            if self.current_audio and self.btn_onoff_state:
                try:
                    if self._paused_audio_position and self._paused_audio_position > 0:
                        self.current_audio.seek(self._paused_audio_position)
                    else:
                        audio_seek_pos = self.current_segment_index * self.segment_duration
                        self.current_audio.seek(audio_seek_pos)
                    self.current_audio.play()
                except Exception:
                    pass

            if self.current_segment_index < len(self.segments):
                delay = self._remaining_time if self._remaining_time > 0 else self.segment_duration
                self._scroll_event = Clock.schedule_once(lambda dt: self.show_segment_scheduled(), delay)
                time_elapsed_before_pause = Clock.time() - self._time_of_last_segment_change
                self._time_of_last_segment_change = Clock.time() - time_elapsed_before_pause

            self.btn_play_state = True
            self._is_paused = False
            self._remaining_time = 0
            try:
                instance.source = os.path.join(self.assets_dir, "Btn_pause.png")
                instance.reload()
            except Exception:
                pass
        else:
            if self.current_audio:
                try:
                    self.current_audio.stop()
                    self._paused_audio_position = self.current_audio.get_pos()
                except Exception:
                    self._paused_audio_position = 0
            if self._scroll_event:
                self._scroll_event.cancel()
                time_elapsed_in_segment = Clock.time() - self._time_of_last_segment_change
                self._remaining_time = max(0, self.segment_duration - time_elapsed_in_segment)

            self.btn_play_state = False
            self._is_paused = True
            try:
                instance.source = os.path.join(self.assets_dir, "Btn_jouer.png")
                instance.reload()
            except Exception:
                pass

    # ==== Navigation par segment (S+/S-) ====
    def navigate_segment(self, direction):
        if not self.segments:
            return
        
        new_index = self.current_segment_index
        if direction == 'next':
            new_index = min(len(self.segments) - 1, self.current_segment_index + 1)
        elif direction == 'prev':
            new_index = max(0, self.current_segment_index - 1)
            
        if new_index == self.current_segment_index:
            return

        self.current_segment_index = new_index

        self.stop_playback(reset_state=False) 
        
        self.show_next_segment(with_animation=False)

        self._paused_audio_position = self.current_segment_index * self.segment_duration
        self._remaining_time = 0

        self._is_paused = True
        self.btn_play_state = False
        try:
            self.btn_play.source = os.path.join(self.assets_dir, "Btn_jouer.png")
            self.btn_play.reload()
        except Exception:
            pass

    # === navigate_recitation: Navigation entre récitations avec vérification 'Debloquer' ===
    def navigate_recitation(self, direction):
        if not self.recitation_data or not getattr(self, "current_class_titles", None):
            return
            
        titles_list = list(self.current_class_titles.keys())
        current_title = self.recitation_data.get('Titre')
        if current_title not in titles_list:
            return
        
        idx = titles_list.index(current_title)
        idx = (idx + 1) % len(titles_list) if direction == 'next' else (idx - 1) % len(titles_list)
        next_title = titles_list[idx]
        rec_id = self.current_class_titles.get(next_title)
        
        if rec_id:
            next_recitation_data = self.get_recitation_by_id(rec_id)

            if not next_recitation_data:
                return
            
            debloquer = next_recitation_data.get('Debloquer', 'non').lower().strip()
            
            if debloquer != 'oui':
                if self.alert_sound:
                    self.alert_sound.play()
                    
                error_popup = Popup(
                    title='Titre Inaccessible', 
                    content=Label(text='Le chapitre que tu veux \nexplorer est verrouillé .\nFais marche arrière \net lance le module QCM.\nSi tu obtiens au moins \n80 % de bonnes réponses, \nce chapitre sera à toi !', 
                    # content=Label(text=f'"{next_title}" Oups !\nLe chapitre que tu veux \nexplorer est verrouillé .\nFais marche arrière \net lance le module QCM.\nSi tu obtiens au moins \n80 % de bonnes réponses, \nce chapitre sera à toi !',           
                                text_size=(Window.width * 0.5, None), 
                                  halign='center'),
                    size_hint=(0.7, 0.4),
                    auto_dismiss=True
                )
                error_popup.open()
                return 

            self.recitation_data = next_recitation_data
            self.current_recitation_id = rec_id
            
            self.update_session_titles(next_title)
            
            self.load_recitation(self.recitation_data)
            
            self.btn_onoff.disabled = False
            self.btn_miroir.disabled = False
            self.btn_miroir.source = os.path.join(self.assets_dir, "miroir_on.png" if self.miroir_active else "miroir_off.png")
            try:
                self.btn_miroir.reload()
            except Exception:
                pass


    # ======================================================================================
    # === MÉTHODE go_back CORRIGÉE (Cible : 'main') ===
    # ======================================================================================
    def go_back(self, instance):
        # 1. Finaliser la session en cours
        if self.session_id != 0:
            self.end_current_session()
        
        # 2. Stopper la lecture et réinitialiser l'état
        self.stop_playback(reset_state=True)
        
        # 3. Réinitialisation des états des boutons
        self.btn_onoff_state = True 
        self.miroir_active = True

        self.btn_onoff.disabled = False
        self.btn_miroir.disabled = False
        self.btn_onoff.source = os.path.join(self.assets_dir, "Btn_On.png") 
        self.btn_miroir.source = os.path.join(self.assets_dir, "miroir_on.png")
        try:
            self.btn_onoff.reload()
            self.btn_miroir.reload()
        except Exception:
            pass
        
        # 4. NAVIGUER VERS L'ÉCRAN PRINCIPAL
        if self.manager:
            if 'main' in self.manager.screen_names: # <-- Correction appliquée ici
                print("DEBUG: Tentative de navigation réussie vers l'écran 'main'.")
                self.manager.current = 'main'
            else:
                print(f"ERREUR DEBUG: L'écran 'main' n'existe pas dans le ScreenManager. Écrans disponibles: {self.manager.screen_names}")
                self.text_label.text = "Erreur: L'écran 'main' est introuvable.\n(Voir console pour le débogage)"
                self.title_label.text = ""
                self.center_labels()
        else:
            print("ERREUR DEBUG: FrancaisScreen n'est pas attaché à un ScreenManager (self.manager est None).")
            self.text_label.text = "Erreur: ScreenManager introuvable.\n(Voir console pour le débogage)"
            self.title_label.text = ""
            self.center_labels()

    # ==== change_font_size ====
    def change_font_size(self, delta):
        new_size = self.font_size_sp + delta
        if 10 <= new_size <= 50:
            self.font_size_sp = new_size
            try:
                self.text_label.font_size = self.font_size_sp
                self.mirror_label.font_size = self.font_size_sp * 0.9
                self.title_label.font_size = self.font_size_sp * 0.9 
            except Exception:
                pass
            self.center_labels()

    # ==== on_resize ====
    def on_resize(self, instance, width, height):
        if height > width:
            self.btn_bar.height = dp(80)
            self.btn_top.height = dp(70)
        else:
            self.btn_bar.height = dp(60)
            self.btn_top.height = dp(55)

        self.title_label.text_size = (width * 0.9, None)
        self.mirror_label.text_size = (width * 0.9, None)
        self.text_label.text_size = (width * 0.9, None)

        self.center_labels()

    # ==== Fonctions miroir ====
    def toggle_miroir(self, instance):
        if instance.disabled:
            return
        if getattr(self, "miroir_active", True):
            self.miroir_off()
        else:
            self.miroir_on()

    def miroir_on(self):
        self.miroir_active = True
        try:
            self.btn_miroir.source = os.path.join(self.assets_dir, "miroir_on.png")
            self.btn_miroir.reload()
        except Exception:
            pass
        try:
            self.update_mirror_label()
        except Exception:
            pass

    def miroir_off(self):
        self.miroir_active = False
        try:
            self.btn_miroir.source = os.path.join(self.assets_dir, "miroir_off.png")
            self.btn_miroir.reload()
        except Exception:
            pass
        try:
            self.mirror_label.text = ""
            self.mirror_label.opacity = 0
        except Exception:
            pass


class FrancaisApp(App):
    def build(self):
        # NOTE: Ceci est pour l'exécution autonome, non utilisé dans main_app.py
        return FrancaisScreen()


if __name__ == "__main__":
    FrancaisApp().run()
