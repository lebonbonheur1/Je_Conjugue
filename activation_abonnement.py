# activation_abonnement.py
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen, SlideTransition
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform

class ActivationAbonnementScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Main layout
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        # Text input for at least 60 words
        self.text_input = TextInput(hint_text='Entrez votre texte ici...', size_hint=(1, 0.4))

        # ComboBox for network selection
        self.network_spinner = Spinner(
            text='Choisissez le réseau',
            values=('Vod', 'Arirt', 'Afr'),
            size_hint=(1, 0.1)
        )

        # Label for code insertion
        code_label = Label(text='Insérer le code ici', size_hint=(1, 0.1))

        # Single line text input for code
        code_input = TextInput(hint_text='Entrez le code ici...', size_hint=(1, None), height=dp(40))

        # Buttons layout
        buttons_layout = BoxLayout(spacing=dp(10), size_hint=(1, 0.2))
        validate_button = Button(text='Valider',background_color=(1, 0, 1, 1))
        cancel_button = Button(text='Annuler',background_color=(1, 0, 1, 1))
        back_button = Button(text='Retour',background_color=(1, 0, 1, 1))

        buttons_layout.add_widget(validate_button)
        buttons_layout.add_widget(cancel_button)
        buttons_layout.add_widget(back_button)

        # Bind the "Retour" button to the go_back method
        back_button.bind(on_press=self.go_back)

        # Add widgets to main layout
        layout.add_widget(self.text_input)
        layout.add_widget(self.network_spinner)
        layout.add_widget(code_label)
        layout.add_widget(code_input)  # Add the single line text input here
        layout.add_widget(buttons_layout)

        self.add_widget(layout)

    def go_back(self, instance):
        """Méthode pour revenir à l'écran principal."""
        self.manager.transition = SlideTransition(direction='right')
        self.manager.current = 'main'