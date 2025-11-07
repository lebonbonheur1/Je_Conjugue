# user_info.py

import sqlite3 
from kivy.app import App  # <--- CORRECTION : Import nécessaire pour Kivy App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup

# Constantes de la base de données
DB_NAME = '_91Rafine_Config.db'
CONFIG_TABLE = 'Configuration'

class Formulaire(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        main_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        # Champ Nom
        main_layout.add_widget(Label(text="Nom :", size_hint=(1, None), height=dp(30)))
        self.nom_input = TextInput(multiline=False)
        main_layout.add_widget(self.nom_input)

        # Champ Prénom
        main_layout.add_widget(Label(text="Prénom :", size_hint=(1, None), height=dp(30)))
        self.prenom_input = TextInput(multiline=False)
        main_layout.add_widget(self.prenom_input)

        # Champ Numéro (Corrigé pour Numéro_téléphone dans la DB)
        main_layout.add_widget(Label(text="Numéro de téléphone :", size_hint=(1, None), height=dp(30)))
        self.numero_input = TextInput(multiline=False, input_filter='int') 
        main_layout.add_widget(self.numero_input)

        # ComboBox (Spinner)
        main_layout.add_widget(Label(text="Option :", size_hint=(1, None), height=dp(30)))
        self.option_spinner = Spinner(
            text="Sélectionner une option",
            values=(
                "Biochimie", "Commerciale", "Coupe_Couture", "Electricite", "Electronique", 
                "Literaire", "Mecanique", "Nutrution", "Pédagogie", "Science_Infirmiere", 
                "Scientifique", "Social"
            ),
            size_hint=(1, None),
            height=dp(44)
        )
        main_layout.add_widget(self.option_spinner)

        # Boutons   
        btn_layout = BoxLayout(size_hint=(1, None), height=dp(50), spacing=dp(10))

        self.valider_btn = Button(text="Valider", background_color=(0, 0, 1, 1))
        self.valider_btn.bind(on_press=self.valider)
        btn_layout.add_widget(self.valider_btn)

        self.retour_btn = Button(text="Retour", background_color=(0, 0, 1, 1))
        self.retour_btn.bind(on_press=self.go_back)
        btn_layout.add_widget(self.retour_btn)
        
        main_layout.add_widget(btn_layout)
        self.add_widget(main_layout)

    def update_config_db(self, nom, prenom, numero, option):
        """Met à jour l'enregistrement Id=1 dans la table Configuration et change PRF à 'PFO'."""
        conn = None
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            sql = f"""
            UPDATE {CONFIG_TABLE}
            SET Nom = ?, Prénom = ?, Numéro_téléphone = ?, Option = ?, PRF = 'PFO'
            WHERE Id = 1;
            """
            cursor.execute(sql, (nom, prenom, numero, option))
            conn.commit()

        except sqlite3.Error as e:
            print(f"Erreur SQLite lors de la mise à jour: {e}")
            self.show_error_popup(f"Erreur de base de données: {e}")
        finally:
            if conn:
                conn.close()

    def show_error_popup(self, message):
        """Affiche un pop-up d'erreur."""
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(Label(text=message, halign='center', valign='middle'))
        close_btn = Button(text='OK', size_hint=(1, None), height=dp(40))
        content.add_widget(close_btn)
        
        popup = Popup(title='Erreur de Validation', content=content,
                      size_hint=(0.7, 0.4), auto_dismiss=False)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def valider(self, instance):
        """Valide les données, les sauvegarde dans la DB et passe à l'écran principal."""
        nom = self.nom_input.text.strip()
        prenom = self.prenom_input.text.strip()
        numero = self.numero_input.text.strip()
        option = self.option_spinner.text
        
        if not nom or not prenom or not numero or option == "Sélectionner une option":
            self.show_error_popup("Veuillez remplir tous les champs.")
            return

        self.update_config_db(nom, prenom, numero, option)

        self.manager.transition.direction = 'left' 
        self.manager.current = 'main'

    def go_back(self, instance):
        """Méthode pour revenir à l'écran principal."""
        self.manager.transition.direction = 'right'
        self.manager.current = 'main'

if __name__ == "__main__":
    from kivy.uix.screenmanager import ScreenManager
    
    class TestApp(App):
        def build(self):
            sm = ScreenManager()
            sm.add_widget(Formulaire(name='main'))
            return sm
            
    TestApp().run()