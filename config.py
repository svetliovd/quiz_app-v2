import os
import sys


def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = get_app_dir()


def resource_path(rel_path: str) -> str:
    try:
        base_meipass = getattr(sys, "_MEIPASS", None)
        if base_meipass:
            path = os.path.join(base_meipass, rel_path)
            if os.path.exists(path):
                return path
    except Exception:
        pass
    return os.path.join(APP_DIR, rel_path)


BASE_DIR = APP_DIR
QUESTIONS_DIR = os.path.join(APP_DIR, "questions")
IMAGES_DIR = os.path.join(APP_DIR, "images")
SOUNDS_DIR = os.path.join(APP_DIR, "sounds")
FONTS_DIR = os.path.join(APP_DIR, "fonts")
GRADING_FILE = os.path.join(APP_DIR, "grading_scale.csv")
HAPPY_PNG = os.path.join(IMAGES_DIR, "happy.png")
REPORTS_DIR = os.path.join(APP_DIR, "reports")
FOOTER_URL = "https://pmg-vd.org"

ADMIN_PASSWORD = os.environ.get("QUIZ_ADMIN_PASS", "admin123")

BTN_BG = "#3e3e5e"
BTN_BG_ACTIVE = "#32bb5b"
BTN_FG = "white"

LETTER_MAP_EN_TO_BG = {
    "A": "А",
    "B": "Б",
    "C": "В",
    "D": "Г",
    "a": "А",
    "b": "Б",
    "c": "В",
    "d": "Г",
}
BG_LETTERS_BY_COUNT = {3: ["А", "Б", "В"], 4: ["А", "Б", "В", "Г"]}

LINKS = {
    "БЕЛ": {
        "НВО 4 клас": "https://edu.mon.bg/library/4/1",
        "НВО 7 клас": "https://edu.mon.bg/library/7/1",
        "НВО 10 клас": "https://edu.mon.bg/library/10/1",
        "НВО 12 клас": "https://edu.mon.bg/library/12/1",
    },
    "Математика": {
        "НВО 4 клас": "https://edu.mon.bg/library/4/2",
        "НВО 7 клас": "https://edu.mon.bg/library/7/2",
        "НВО 10 клас": "https://edu.mon.bg/library/10/2",
        "НВО 12 клас": "https://edu.mon.bg/library/12/2",
    },
}

CORRECT_SOUND = resource_path(os.path.join("sounds", "correct.mp3"))
WRONG_SOUND = resource_path(os.path.join("sounds", "wrong.mp3"))
SUCCESS_SOUND = resource_path(os.path.join("sounds", "success.mp3"))
FAIL_SOUND = resource_path(os.path.join("sounds", "fail.mp3"))
