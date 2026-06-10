QuizApp skins
=============

The default skin is defined in skins.py. Additional local skins come from
standard asset folders under templates.

Quick start:
1. Create a folder under templates, for example templates/minecraft.
2. Add wallpaper and sound files using the standard filenames below.
3. Add a text file in the folder, for example tier.txt.
4. Write exactly one word in that file: easy, medium, or hard.

The app automatically creates one skin per template folder:
- templates/minecraft -> skin id "minecraft", name "Minecraft"
- templates/fortnite -> skin id "fortnite", name "Fortnite"
- templates/csgo -> skin id "csgo", name "CS:GO"

Folders are processed alphabetically.

Unlock tiers:
- easy: 30 total correct answers
- medium: 50 total correct answers
- hard: 100 total correct answers

Admin demo unlocks use smaller thresholds:
- easy: 1 demo correct answer
- medium: 2 demo correct answers
- hard: 3 demo correct answers

Advanced manual example for skins/skins.json:

{
  "skins": [
    {
      "id": "my_theme",
      "name": "My Theme",
      "description": "Short text shown in the skin chooser.",
      "asset_dir": "templates/my_theme",
      "unlock": {"tier": "easy", "total_correct": 30, "demo_total_correct": 1},
      "wallpaper": "wallpaper.png",
      "music": "music.mp3",
      "unlock_sound": "unlock.mp3",
      "select_sound": "select.wav",
      "correct_sound": "correct.wav",
      "wrong_sound": "wrong.wav",
      "success_sound": "success.mp3",
      "fail_sound": "fail.mp3",
      "win_image": "win.png",
      "fail_image": "fail.png",
      "font_family": "Arial",
      "colors": {
        "bg": "#101114",
        "panel": "#1f2128",
        "text": "#ffffff",
        "muted": "#cfd7e6",
        "button": "#3f3f46",
        "button_active": "#f97316",
        "button_hover": "#52525b",
        "accent": "#22d3ee",
        "success": "#84cc16",
        "danger": "#ef4444",
        "warning": "#facc15",
        "link": "#67e8f9"
      }
    }
  ]
}

Place assets in the folder from asset_dir, for example:
templates/my_theme/wallpaper.png
templates/my_theme/music.mp3

Standard automatic filenames:
- tier.txt: contains easy, medium, or hard
- wallpaper.jpg or wallpaper.png
- music.mp3, or another music-like MP3/OGG/WAV file as a fallback
- unlock_sound.mp3
- select_sound.mp3
- correct_sound.mp3
- wrong_sound.mp3
- success_sound.mp3 or win_sound.mp3
- fail_sound.mp3 or lose_sound.mp3
- win.png or success.png
- fail.png or lose.png

Recommended assets:
- Wallpaper: PNG or JPG, 1920x1080 minimum. Keep important details near the center.
- Music: MP3 or OGG, 30-90 seconds if it loops.
- Short sounds: WAV or MP3, ideally under 3 seconds.
- Result icons: PNG recommended, square images work best.
- Optional sounds: unlock_sound, select_sound, correct_sound, wrong_sound, success_sound, fail_sound.

Administrators can preview all skins from the admin screens without unlocking them.
Student profiles unlock skins only from completed student-mode tests.
