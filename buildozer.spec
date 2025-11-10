[app]

title = Ardoise V1
package.name = monprojetkivy
package.domain = com.votredomaine   ; <- A MODIFIER (Exemple: com.monnom)
version = 0.1
requirements = python3,kivy,sdl2_mixer
source.dir = .
source.exclude_dirs = tests, bin, .buildozer, __pycache__
main.py = main.py
android.archs = arm64-v8a
android.minapi = 21
android.api = 27
orientation = portrait
debug = True

[buildozer]
log_level = 1
build_dir = .buildozer
bin_dir = bin

[app-specific]
