import os
import sqlite3
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform, get_color_from_hex
from kivy.uix.screenmanager import Screen
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button

# --- Configuration de la base ---
DB_FILE = '_91Rafine_Config.db'
TABLE_NAME = 'Tableau_de_bord'

def setup_database():
    """Crée la table si elle n'existe pas."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS "{TABLE_NAME}" (
            "Id" INTEGER NOT NULL UNIQUE,
            "Nom_du_module" TEXT,
            "Titre" TEXT,
            "Date_Heure_ouverture" TEXT,
            "Date_Heure_fermeture" TEXT,
            "Duree_session" TEXT,
            PRIMARY KEY("Id" AUTOINCREMENT)
        );
    """)
    conn.commit()
    conn.close()

setup_database()


# --- Image clickable : Image + ButtonBehavior ---
class ImageButton(ButtonBehavior, Image):
    """Image qui se comporte comme un bouton, avec taille adaptative."""
    def __init__(self, source, on_release_callback=None, min_dp=40, max_dp=72, **kwargs):
        super().__init__(**kwargs)
        self.source = source
        self.allow_stretch = True
        self.keep_ratio = True
        self.size_hint = (None, None)
        self.min_dp = dp(min_dp)
        self.max_dp = dp(max_dp)
        self._update_size_by_window(Window.width, Window.height)
        Window.bind(size=self._on_window_size)
        if on_release_callback:
            self.bind(on_release=on_release_callback)

    def _on_window_size(self, instance, size):
        w, h = size
        self._update_size_by_window(w, h)

    def _update_size_by_window(self, width, height):
        fraction = max(0.08, min(0.14, 0.11))
        desired = int(width * fraction)
        desired_dp = max(self.min_dp, min(self.max_dp, dp(desired)))
        self.size = (desired_dp, desired_dp)


# --- Composant Carte ---
class Card(BoxLayout):
    """Carte visuelle avec hauteur auto-adaptative pour le titre multi-ligne."""
    def __init__(self, row_data, **kwargs):
        super().__init__(orientation='vertical', padding=dp(10), spacing=dp(6),
                         size_hint_y=None, **kwargs)

        with self.canvas.before:
            Color(0.96, 0.96, 1, 1)
            self.rect = RoundedRectangle(radius=[dp(10)], pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)

        raw_title = row_data[2] if len(row_data) > 2 and row_data[2] is not None else ""
        formatted_title = raw_title.replace(';', '\n').replace(',', '\n').strip()
        if not formatted_title:
            formatted_title = "N/A"

        title_label = Label(
            text=f"[b]Titre :[/b] {formatted_title}",
            markup=True,
            halign="left",
            valign="top",
            size_hint_y=None,
            height=dp(10),
            color=get_color_from_hex("#000000")
        )
        title_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] + dp(10)))
        self.bind(width=lambda instance, value: setattr(title_label, 'text_size', (value - dp(20), None)))
        self.add_widget(title_label)

        infos = [
            ("Ouverture", row_data[3] if len(row_data) > 3 else ""),
            ("Fermeture", row_data[4] if len(row_data) > 4 else ""),
            ("Durée", row_data[5] if len(row_data) > 5 else "")
        ]
        for label_text, val in infos:
            lbl = Label(
                text=f"[b]{label_text} :[/b] {val}",
                markup=True,
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(26),
                color=get_color_from_hex("#000000")
            )
            lbl.bind(width=lambda instance, value: setattr(instance, 'text_size', (value - dp(10), None)))
            self.add_widget(lbl)

        self.bind(minimum_height=self.setter('height'))

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


# --- Fallback si image manquante ---
class ButtonFallback(Button):
    def __init__(self, text, callback=None, **kwargs):
        super().__init__(text=text, size_hint=(None, None), width=dp(100), height=dp(48), **kwargs)
        if callback:
            try:
                self.bind(on_release=callback)
            except Exception:
                self.bind(on_release=lambda *a: callback())


# --- Écran principal ---
class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        header = Label(
            text="📋 Tableau de Bord",
            size_hint_y=None,
            height=dp(56),
            font_size='20sp',
            bold=True,
            color=get_color_from_hex("#000000")
        )
        main_layout.add_widget(header)

        self.scroll = ScrollView(size_hint=(1, 1))
        self.cards_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(6)])
        self.cards_layout.bind(minimum_height=self.cards_layout.setter('height'))
        self.scroll.add_widget(self.cards_layout)
        main_layout.add_widget(self.scroll)

        # --- Pied de page dynamique (3 boutons image : gauche, centre, droite) ---
        footer = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(72),
            padding=[dp(8), 0, dp(8), 0],
            spacing=dp(8)
        )

        # Chemins d'images
        back_path = 'assets/retour.png'
        refresh_path = 'assets/actualiser.png'
        delete_path = 'assets/dellete.png'

        # Création des boutons images
        back_btn = ImageButton(source=back_path, on_release_callback=self.go_back_to_main)
        refresh_btn = ImageButton(source=refresh_path, on_release_callback=lambda i: self.load_data())
        delete_btn = ImageButton(source=delete_path, on_release_callback=lambda i: self.delete_all())

        # --- Répartition dynamique ---
        left_box = BoxLayout(size_hint_x=0.33, orientation='horizontal')
        center_box = BoxLayout(size_hint_x=0.34, orientation='horizontal')
        right_box = BoxLayout(size_hint_x=0.33, orientation='horizontal')

        # Centrage horizontal et vertical des boutons
        left_box.add_widget(Label(size_hint=(None, 1), width=0))
        left_box.add_widget(back_btn)
        left_box.add_widget(Label(size_hint=(None, 1), width=0))

        center_box.add_widget(Label(size_hint=(None, 1), width=0))
        center_box.add_widget(refresh_btn)
        center_box.add_widget(Label(size_hint=(None, 1), width=0))

        right_box.add_widget(Label(size_hint=(None, 1), width=0))
        right_box.add_widget(delete_btn)
        right_box.add_widget(Label(size_hint=(None, 1), width=0))

        # Centrer les boutons dans leur zone
        back_btn.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        refresh_btn.pos_hint = {'center_x': 0.5, 'center_y': 0.5}
        delete_btn.pos_hint = {'center_x': 0.5, 'center_y': 0.5}

        # Ajout au pied de page
        footer.add_widget(left_box)
        footer.add_widget(center_box)
        footer.add_widget(right_box)

        # Ajout du pied de page au layout principal
        main_layout.add_widget(footer)
        self.add_widget(main_layout)
        self.load_data()

    # --- Méthodes principales ---
    def go_back_to_main(self, instance):
        app = App.get_running_app()
        if hasattr(app, 'root') and app.root:
            try:
                app.root.current = 'main'
            except Exception:
                print("🔁 'main' non disponible dans le ScreenManager.")

    def load_data(self):
        self.cards_layout.clear_widgets()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM "{TABLE_NAME}" ORDER BY Id DESC')
        data = cursor.fetchall()
        conn.close()

        if not data:
            self.cards_layout.add_widget(Label(
                text="Aucune donnée trouvée.",
                color=get_color_from_hex("#777777"),
                size_hint_y=None,
                height=dp(40)
            ))
            return

        for row in data:
            card = Card(row)
            card.size_hint_y = None
            self.cards_layout.add_widget(card)

    def delete_all(self, *args):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM "{TABLE_NAME}"')
        conn.commit()
        conn.close()
        print("✅ Toutes les lignes ont été supprimées.")
        self.load_data()


# --- Application principale ---
class TableauDeBordApp(App):
    title = 'Francais-A'

    def build(self):
        if platform not in ('android', 'ios'):
            Window.size = (dp(480), dp(800))
        return DashboardScreen()


if __name__ == '__main__':
    TableauDeBordApp().run()
