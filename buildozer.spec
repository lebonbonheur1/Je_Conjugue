[app]
# Nom de ton application
title = Je Conjugue
package.name = jeconjugue
package.domain = org.example

# Fichier principal
source.main = main_app.py

# Version de l'application
version = 1.0

# Orientation de l'application
orientation = portrait

# Dépendances Python
requirements = python3,kivy

# Inclure tous les fichiers du projet
source.include_exts = py,png,jpg,kv,atlas,db

# Permissions Android si nécessaire
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE

# Affichage splash screen (optionnel)
#android.icon = icon.png
#android.presplash = presplash.png
