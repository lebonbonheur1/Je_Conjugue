# main_app.py

# -*- coding: utf-8 -*-
import os
import sys
import sqlite3 

# Set the video provider to ffpyplayer before any Kivy import
os.environ['KIVY_VIDEO'] = 'ffpyplayer'

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup 
from kivy.uix.image import Image 

# Imports des classes d'écrans 
try:
    from Conjugaison import ConjugaisonScreen 
except ImportError:
    class ConjugaisonScreen(Screen): pass
    print("WARNING: Conjugaison.py not found. Using dummy screen.")
    
try:
    from Gramaire_francais_app import FrancaisScreen 
except ImportError:
    class FrancaisScreen(Screen): pass
    print("WARNING: Gramaire_francais_app.py not found. Using dummy screen.")
    
try:
    from user_info import Formulaire 
except ImportError:
    class Formulaire(Screen): pass
    print("WARNING: user_info.py not found. Using dummy screen.")

try:
    from quizz_dynamique import QuizzScreen 
except ImportError:
    class QuizzScreen(Screen): pass
    print("WARNING: quizz_dynamique.py not found. Using dummy screen.")

try:
    from tableau_de_bord import DashboardScreen 
except ImportError:
    class DashboardScreen(Screen): pass
    print("WARNING: tableau_de_bord.py not found. Using dummy screen.")

# Configure window size for non-Android platforms
if platform != 'android':
    Window.size = (dp(440), dp(550))

# =================================================================
# LOGIQUE DE BASE DE DONNÉES (DB) ET DE CONFIGURATION
# =================================================================

DB_NAME = '_91Rafine_Config.db'
CONFIG_TABLE = 'Configuration'
TABLEAU_DE_BORD_TABLE = 'Tableau_de_bord'

# SQL pour créer la table 'Configuration'
CREATE_CONFIG_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {CONFIG_TABLE} (
    "Id" INTEGER NOT NULL UNIQUE,
    "Nom" TEXT,
    "Prénom" TEXT,
    "Numéro_téléphone" TEXT,
    "Option" TEXT,
    "PRF" TEXT,
    "Date_activation" TEXT,
    "Date_expiration" TEXT,
    "Compteur_Date" TEXT,
    "Device_id" TEXT,
    "Duree_code" TEXT,
    "Etat_Activation" TEXT,
    PRIMARY KEY("Id" AUTOINCREMENT)
);
"""
# SQL pour créer la table Tableau_de_bord
CREATE_DASHBOARD_TABLE_SQL = f"""
    CREATE TABLE IF NOT EXISTS {TABLEAU_DE_BORD_TABLE} (
        Id INTEGER NOT NULL UNIQUE,
        Nom_du_module TEXT,
        Titre TEXT,
        Date_Heure_ouverture TEXT,
        Date_Heure_fermeture TEXT,
        Duree_session TEXT,
        PRIMARY KEY(Id AUTOINCREMENT)
    )
"""

# SQL pour insérer la ligne initiale (Id=1, PRF='PF', Etat_Activation='INACTIF') si elle n'existe pas
INITIAL_ROW_SQL = f"""
INSERT INTO {CONFIG_TABLE} (Id, PRF, Etat_Activation) 
SELECT 1, 'PF', 'INACTIF'
WHERE NOT EXISTS (SELECT 1 FROM {CONFIG_TABLE} WHERE Id = 1);
"""

def initialize_db(read_only=False):
    """
    Connecte à la DB et effectue l'initialisation/nettoyage si read_only=False.
    """
    conn = None
    db_exists = os.path.exists(DB_NAME)
    
    try:
        if read_only and db_exists:
            # Mode lecture seule pour vérification rapide
            conn = sqlite3.connect(f'file:{DB_NAME}?mode=ro', uri=True)
            return conn
        
        # Mode lecture/écriture (pour création/initialisation/nettoyage)
        print("Connexion/Initialisation en mode LECTURE/ÉCRITURE. Nettoyage de la base de données exécuté.")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # 1. Création des tables
        cursor.execute(CREATE_CONFIG_TABLE_SQL)
        cursor.execute(CREATE_DASHBOARD_TABLE_SQL) 
        
        # 2. Insertion de la ligne initiale (uniquement si elle manque)
        cursor.execute(INITIAL_ROW_SQL) 
        
        # 3. LOGIQUE DE NETTOYAGE (Rétention)
        cursor.execute(f"SELECT COUNT(Id) FROM {TABLEAU_DE_BORD_TABLE}")
        count = cursor.fetchone()[0]
        
        if count > 60:
            print(f"✅ CLEANUP: La table {TABLEAU_DE_BORD_TABLE} contient {count} lignes (> 60). Début du nettoyage...")
            
            # Étape A: Identifier les 5 derniers enregistrements (à conserver)
            cursor.execute(f"""
                SELECT Id FROM {TABLEAU_DE_BORD_TABLE}
                ORDER BY Id DESC
                LIMIT 30
            """)
            ids_to_keep = [row[0] for row in cursor.fetchall()]
            
            if ids_to_keep:
                ids_to_keep_str = ','.join(map(str, ids_to_keep))
                
                # Étape B: Supprimer toutes les lignes antérieures aux 5 dernières
                delete_sql = f"""
                    DELETE FROM {TABLEAU_DE_BORD_TABLE}
                    WHERE Id NOT IN ({ids_to_keep_str})
                """
                cursor.execute(delete_sql)
                print(f"   Nettoyage terminé. {cursor.rowcount} lignes supprimées. {len(ids_to_keep)} lignes conservées.")
            else:
                print(f"   ATTENTION: Échec de la sélection des IDs à conserver.")
        else:
            print(f"   Nettoyage non requis. La table {TABLEAU_DE_BORD_TABLE} contient {count} lignes.")
        
        # 4. Finalisation: Committer les changements
        conn.commit()
        return conn
    
    except sqlite3.OperationalError as e:
        print(f"Erreur SQLite (Operational) lors de l'initialisation: {e}")
        if conn:
            conn.close()
        return None
    except sqlite3.Error as e:
        print(f"Erreur SQLite lors de l'initialisation: {e}")
        if conn:
            conn.close()
        return None

def check_startup_conditions(conn):
    """
    Vérifie les conditions de démarrage et retourne l'écran initial et le statut d'activation.
    """
    if conn is None:
        return 'main', 'ERREUR' 
        
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT PRF, Etat_Activation FROM {CONFIG_TABLE} WHERE Id = 1")
        result = cursor.fetchone()
        
        if result is None:
            return 'user_info', 'INCONNU' 
            
        prf = result[0].lower()      
        etat_activation = result[1].upper() 

        startup_screen = 'main'
        
        # 1. VÉRIFICATION PRF : Identification requise
        if prf == 'pf':
            startup_screen = 'user_info'
        # 2. VÉRIFICATION Activation : Si INACTIF ou DP, forcer l'écran d'activation ou désactiver le bouton
        elif etat_activation == 'INACTIF':
            startup_screen = 'activation'
        # NOUVELLE LOGIQUE: Si Etat_Activation est 'DP', le statut est renvoyé pour désactiver le bouton.
        # Si la vérification DP est l'unique vérification ici, l'écran de démarrage reste 'main'.

        return startup_screen, etat_activation 

    except sqlite3.Error as e:
        print(f"Erreur SQLite lors de la vérification des conditions: {e}")
        return 'main', 'ERREUR' 

# =================================================================
# CLASSES DES ÉCRANS 
# =================================================================

class ActivationAbonnementScreen(Screen):
    # ... (Classe inchangée) ...
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Main layout
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        self.text_input = TextInput(hint_text='Entrez votre texte ici...', size_hint=(1, 0.4))
        self.network_spinner = Spinner(text='Choisissez le réseau', values=('Vod', 'Arirt', 'Afr'), size_hint=(1, 0.1))
        code_label = Label(text='Insérer le code ici', size_hint=(1, 0.1))
        code_input = TextInput(hint_text='Entrez le code ici...', size_hint=(1, None), height=dp(40))

        buttons_layout = BoxLayout(spacing=dp(10), size_hint=(1, 0.2))
        validate_button = Button(text='Valider',background_color=(1, 0, 1, 1))
        cancel_button = Button(text='Annuler',background_color=(1, 0, 1, 1))
        back_button = Button(text='Retour',background_color=(1, 0, 1, 1))
        
        buttons_layout.add_widget(validate_button)
        buttons_layout.add_widget(cancel_button)
        buttons_layout.add_widget(back_button)

        back_button.bind(on_press=self.go_back)

        layout.add_widget(self.text_input)
        layout.add_widget(self.network_spinner)
        layout.add_widget(code_label)
        layout.add_widget(code_input)
        layout.add_widget(buttons_layout)

        self.add_widget(layout)

    def go_back(self, instance):
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'main'

class MainScreen(Screen):
    def __init__(self, activation_status='INCONNU', **kwargs):
        super().__init__(**kwargs)
        
        # 1. LAYOUT PRINCIPAL (orientation verticale pour la division 70/30)
        main_layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        # ====================================================================
        # 2. CADRAN PHOTO (70% de la hauteur totale)
        # ====================================================================
        image_panel = BoxLayout(orientation='vertical', size_hint=(1, 0.7), padding=dp(5), spacing=dp(5))
        
        title_label = Label(
            text="Cours Dynamique", 
            font_size='24sp', 
            size_hint_y=None, 
            height=dp(50), 
            color=(0.1, 0.1, 0.1, 1)
        )
        image_panel.add_widget(title_label)
        
        try:
            image_widget = Image(
                source='assets/screen.png', 
                allow_stretch=True, 
                keep_ratio=True, 
                size_hint=(1, 1)
            )
            image_panel.add_widget(image_widget)
        except Exception as e:
            error_label = Label(text=f"Image 'assets/screen.png' manquante. Placez-la dans le dossier 'assets'.", color=(1, 0, 0, 1))
            image_panel.add_widget(error_label)
        
        main_layout.add_widget(image_panel)
        
        # ====================================================================
        # 3. CONTENEUR DES BOUTONS (30% de la hauteur totale)
        # ====================================================================
        buttons_container = BoxLayout(orientation='vertical', spacing=dp(10), size_hint=(1, 0.3), padding=(0, dp(10), 0, dp(10)))
        
        button_size_hint = (1, 1/3) 
        
        # Bouton 1: Activation
        self.btn_activation = Button(
            text='Activation Abonnement', 
            background_color=(0.1, 0.1, 0.8, 1), 
            size_hint=button_size_hint
        )
        
        # Bouton 2: Commencer
        self.btn_commencer = Button(
            text='Commencer', 
            background_color=(0.2, 0.7, 0.2, 1), 
            size_hint=button_size_hint
        )
        
        # Bouton 3: Tableau de bord
        self.btn_tableau_de_bord = Button(
            text='Tableau de bord', 
            background_color=(0.8, 0.5, 0.1, 1), 
            size_hint=button_size_hint
        )
        
        # LOGIQUE D'ACTIVATION MISE À JOUR
        # Le bouton est désactivé si l'état est 'ACTIF' (pas besoin d'activation) 
        # OU si l'état est 'DP' (Désactivé en Permanence, selon votre demande)
        if activation_status == 'ACTIF' or activation_status == 'DP':
            self.btn_activation.disabled = True
            self.btn_activation.opacity = 0.5 
        else:
            # S'il est INACTIF, NP ou autre, il est activé pour permettre l'abonnement
            self.btn_activation.disabled = False
            self.btn_activation.opacity = 1.0

        # Ajout des boutons au conteneur
        buttons_container.add_widget(self.btn_activation)
        buttons_container.add_widget(self.btn_commencer)
        buttons_container.add_widget(self.btn_tableau_de_bord)
        
        main_layout.add_widget(buttons_container)

        # LIAISONS (Bindings)
        self.btn_activation.bind(on_press=self.go_to_activation)
        self.btn_commencer.bind(on_press=self.show_module_popup)
        self.btn_tableau_de_bord.bind(on_press=self.go_to_dashboard)
        
        self.add_widget(main_layout)
        
    def go_to_activation(self, instance):
        """Méthode pour passer à l'écran d'activation."""
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = 'activation'
        
    def go_to_dashboard(self, instance):
        """Méthode pour passer à l'écran du Tableau de Bord."""
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = 'dashboard'


    def show_module_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(20))
        label = Label(text="Choisissez un module :", size_hint_y=None, height=dp(40))
        btn_conjugaison = Button(text='Conjugaison', size_hint_y=None, height=dp(50), background_color=(0.2, 0.4, 0.7, 1))
        btn_grammaire = Button(text='Grammaire', size_hint_y=None, height=dp(50), background_color=(0.1, 0.8, 0.5, 1))
        
        btn_qcm = Button(text='QCM', size_hint_y=None, height=dp(50), background_color=(0.5, 0.0, 0.5, 1))
        
        btn_cancel = Button(text='Annuler', size_hint_y=None, height=dp(40), background_color=(0.8, 0.2, 0.2, 1))
        
        content.add_widget(label)
        content.add_widget(btn_conjugaison)
        content.add_widget(btn_grammaire)
        content.add_widget(btn_qcm)
        content.add_widget(btn_cancel)
        
        self.module_popup = Popup(title='Sélection du Module', content=content, size_hint=(0.7, 0.5), auto_dismiss=False) 
        
        btn_conjugaison.bind(on_press=self.go_to_conjugaison)
        btn_grammaire.bind(on_press=self.go_to_grammaire)
        btn_qcm.bind(on_press=self.go_to_qcm)
        btn_cancel.bind(on_press=self.module_popup.dismiss)
        self.module_popup.open()


    def go_to_conjugaison(self, instance):
        if hasattr(self, 'module_popup'):
            self.module_popup.dismiss()
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = 'conjugaison'

    def go_to_grammaire(self, instance):
        if hasattr(self, 'module_popup'):
            self.module_popup.dismiss()
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = 'francais'
        
    def go_to_qcm(self, instance):
        """Méthode pour passer à l'écran du Quizz (QCM)."""
        if hasattr(self, 'module_popup'):
            self.module_popup.dismiss()
        self.manager.transition = SlideTransition(direction='left')
        self.manager.current = 'qcm'


# Main App
class CoursDynamiqueApp(App):
    def build(self):
        # 1. Connexion et Initialisation (y compris le nettoyage) en mode lecture/écriture
        db_conn = initialize_db(read_only=False)
            
        initial_screen_name, activation_status = check_startup_conditions(db_conn)
        
        if db_conn:
            db_conn.close()

        # 2. Création du ScreenManager et ajout des écrans
        sm = ScreenManager()
        
        # Passe le statut d'activation à MainScreen
        sm.add_widget(MainScreen(name='main', activation_status=activation_status))
        sm.add_widget(ActivationAbonnementScreen(name='activation'))
        sm.add_widget(ConjugaisonScreen(name='conjugaison')) 
        sm.add_widget(FrancaisScreen(name='francais')) 
        sm.add_widget(Formulaire(name='user_info')) 
        sm.add_widget(QuizzScreen(name='qcm')) 
        
        # AJOUT DU NOUVEL ÉCRAN TABLEAU DE BORD
        sm.add_widget(DashboardScreen(name='dashboard')) 
        
        # 3. Définir l'écran initial déterminé par la logique de configuration
        sm.current = initial_screen_name
        
        return sm

if __name__ == '__main__':
    CoursDynamiqueApp().run()