
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import time
import os
import ctypes
import webbrowser
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from achievements import (
    PROFILE_EXTENSION,
    create_profile,
    load_profile,
    save_profile,
    update_profile_after_result,
)
from answer_utils import normalize_answer as _normalize_answer
from audio import play_music, play_sound, stop_music
from config import (
    ADMIN_PASSWORD,
    APP_DIR,
    BG_LETTERS_BY_COUNT,
    BTN_BG,
    BTN_BG_ACTIVE,
    BTN_FG,
    CORRECT_SOUND,
    FAIL_SOUND,
    FONTS_DIR,
    FOOTER_URL,
    GRADING_FILE,
    HAPPY_PNG,
    IMAGES_DIR,
    LETTER_MAP_EN_TO_BG,
    LINKS,
    PROFILES_DIR,
    QUESTIONS_DIR,
    REPORTS_DIR,
    SKINS_DIR,
    SOUNDS_DIR,
    SUCCESS_SOUND,
    TEMPLATES_DIR,
    WRONG_SOUND,
    resource_path,
)
from grading import calculate_grade, import_grading_scale_csv as save_grading_scale_csv
from grading import load_grading_scale
from footer import build_footer
from info_windows import open_instructions_window, open_team_window
from pdf_report import build_pdf_report
from question_store import delete_question_csvs, ensure_question_folder, load_question_records, store_excel_questions
from radio_player import open_radio_player
from skins import DEFAULT_COLORS, DEFAULT_SKIN_ID, SkinManager

grading_df = load_grading_scale(GRADING_FILE)

RESULT_IMAGE_MAX_SIZE = 500
RESULT_IMAGE_MIN_SIZE = 160
RESULT_IMAGE_RESERVED_HEIGHT = 500

# ---------- App class ----------
class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz система")
        self.skin_manager = SkinManager(SKINS_DIR)
        self.student_profile = create_profile()
        self.active_skin = self.skin_manager.get(DEFAULT_SKIN_ID)
        self._wallpaper_label = None
        self._wallpaper_photo = None
        self._skin_music_path = None
        self.admin_demo_unlocks = False
        self.quiz_skin_id = DEFAULT_SKIN_ID
        self.root.configure(bg=self._theme_color("bg"))
        self.root.geometry("900x650")

        self.subject = None
        self.category = None
        self.questions = []
        self.current_index = 0
        self.score = 0
        self.timer_seconds = 0
        self.timer_enabled = False
        self.timer_running = False
        self.progress = None
        self.timer_label = None
        self.footer_frame = None
        self.logo_image_small = None
        self.user_answers = []
        self._current_widgets = {}
        self.selected_category = None
        self.selected_subject = None
        self.sample_size_var = tk.IntVar(value=20)
        self.is_admin = False
        self.in_test = False
        self.radio_playing = False
        self.current_radio_stream = None
        self.ffplay_process = None
        self.zoom_factor = 1.0
        self._zoom_buttons = []

        self._register_pdf_font()
        self.create_start_screen()
        self.enable_kiosk()
        self._bind_zoom_shortcuts()

    def _clear_screen(self):
        for w in self.root.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self.root.configure(bg=self._theme_color("bg"))
        self._wallpaper_label = None
        self._wallpaper_photo = None
        self._refresh_wallpaper()

    def _theme_color(self, key, fallback=None):
        colors = (getattr(self, "active_skin", None) or {}).get("colors") or DEFAULT_COLORS
        return colors.get(key, DEFAULT_COLORS.get(key, fallback))

    def _theme_font(self):
        return (getattr(self, "active_skin", None) or {}).get("font_family") or "Arial"

    def _profile_short_key(self):
        return str(self.student_profile.get("student_key", ""))[:8].upper()

    def _profile_summary_text(self):
        unlocked = len(self.student_profile.get("unlocked_skins") or [])
        total = len(self.skin_manager.all())
        total_correct = int(self.student_profile.get("total_correct") or 0)
        return f"Профил: {self._profile_short_key()} | Верни общо: {total_correct} | Скинове: {unlocked}/{total}"

    def _refresh_wallpaper(self):
        try:
            if self._wallpaper_label:
                self._wallpaper_label.destroy()
        except Exception:
            pass
        self._wallpaper_label = None
        self._wallpaper_photo = None

        wallpaper_path = self.skin_manager.asset_path(self.active_skin, "wallpaper")
        if not wallpaper_path:
            return
        try:
            self.root.update_idletasks()
            width = max(900, self.root.winfo_width() or self.root.winfo_screenwidth())
            height = max(650, self.root.winfo_height() or self.root.winfo_screenheight())
            img = Image.open(wallpaper_path)
            img_w, img_h = img.size
            if img_w > 0 and img_h > 0:
                scale = max(width / img_w, height / img_h)
                new_size = (max(1, int(img_w * scale)), max(1, int(img_h * scale)))
                img = img.resize(new_size, Image.LANCZOS)
                left = max(0, (img.size[0] - width) // 2)
                top = max(0, (img.size[1] - height) // 2)
                img = img.crop((left, top, left + width, top + height))
            self._wallpaper_photo = ImageTk.PhotoImage(img)
            self._wallpaper_label = tk.Label(self.root, image=self._wallpaper_photo, bg=self._theme_color("bg"))
            self._wallpaper_label.place(x=0, y=0, relwidth=1, relheight=1)
            self._wallpaper_label.lower()
        except Exception:
            self._wallpaper_label = None
            self._wallpaper_photo = None

    def _apply_skin_music(self):
        music_path = self.skin_manager.asset_path(self.active_skin, "music")
        if not music_path:
            if self._skin_music_path:
                stop_music()
                self._skin_music_path = None
            return
        if music_path != self._skin_music_path:
            stop_music()
            play_music(music_path, loop=True)
            self._skin_music_path = music_path

    def _play_skin_sound(self, field, fallback_path=None):
        play_sound(self.skin_manager.asset_path(self.active_skin, field) or fallback_path)

    def _set_active_skin(self, skin_id, *, play_select_sound=False, allow_locked=False, persist=True):
        unlocked = set(self.student_profile.get("unlocked_skins") or [DEFAULT_SKIN_ID])
        target_id = skin_id if (allow_locked or skin_id in unlocked) else DEFAULT_SKIN_ID
        skin = self.skin_manager.get(target_id)
        self.active_skin = skin
        if persist and skin["id"] in unlocked:
            self.student_profile["selected_skin"] = skin["id"]
        if play_select_sound:
            play_sound(self.skin_manager.asset_path(skin, "select_sound"))
        self.root.configure(bg=self._theme_color("bg"))
        self._refresh_wallpaper()
        self._apply_theme()
        self._apply_skin_music()

    def _mapped_theme_color(self, value):
        if not value:
            return value
        color_map = {
            "#1e1e2f": self._theme_color("bg"),
            "#2e2e4f": self._theme_color("panel"),
            BTN_BG: self._theme_color("button"),
            BTN_BG_ACTIVE: self._theme_color("button_active"),
            "#52527a": self._theme_color("button_hover"),
            "#525280": self._theme_color("button_hover"),
            "#3bd66a": self._theme_color("button_active"),
            "#3ea96e": self._theme_color("button_active"),
            "#4caf50": self._theme_color("success"),
            "#2e7d32": self._theme_color("option_correct"),
            "#f44336": self._theme_color("danger"),
            "#c62828": self._theme_color("option_wrong"),
            "#424242": self._theme_color("option_neutral"),
            "#8e3e3e": self._theme_color("danger"),
            "#a85a5a": self._theme_color("danger"),
            "#ff7f7f": self._theme_color("danger"),
            "#cfcfe6": self._theme_color("muted"),
            "#f4f6ff": self._theme_color("text"),
            "#d9d9ee": self._theme_color("muted"),
            "white": self._theme_color("text"),
            "yellow": self._theme_color("warning"),
            "lightgreen": self._theme_color("success"),
            "tomato": self._theme_color("danger"),
            "blue": self._theme_color("link"),
        }
        value = str(value)
        if value in color_map:
            return color_map[value]
        for skin in self.skin_manager.all():
            for key, color in (skin.get("colors") or {}).items():
                if value == color and key in DEFAULT_COLORS:
                    return self._theme_color(key)
        return value

    def _apply_theme(self):
        try:
            self.root.configure(bg=self._theme_color("bg"))
        except Exception:
            pass
        self._apply_theme_to_widget(self.root)

    def _apply_theme_to_widget(self, widget):
        if getattr(widget, "_preserve_theme_colors", False):
            return
        for option in ("bg", "background", "fg", "foreground", "activebackground", "activeforeground", "selectcolor", "disabledforeground"):
            try:
                current = widget.cget(option)
            except Exception:
                continue
            mapped = self._mapped_theme_color(current)
            if mapped != current:
                try:
                    widget.configure(**{option: mapped})
                except Exception:
                    pass
        try:
            font_value = widget.cget("font")
        except Exception:
            font_value = None
        if font_value and not getattr(widget, "_skip_zoom", False):
            try:
                font = tkfont.Font(font=font_value)
                family = self._theme_font()
                if family:
                    widget.configure(font=(family, font.cget("size"), font.cget("weight"), font.cget("slant")))
                    if hasattr(widget, "_base_font_config"):
                        widget._base_font_config["family"] = family
            except Exception:
                pass
        for child in widget.winfo_children():
            if child is getattr(self, "_wallpaper_label", None):
                continue
            self._apply_theme_to_widget(child)

    def _ensure_q_folder(self, subject: str, grade: str) -> Path:
        return ensure_question_folder(subject or self.subject or "БЕЛ", grade or self.category or "Импорт от Excel")

    def _register_pdf_font(self):
        candidates = [
            os.path.join(FONTS_DIR, 'DejaVuSans.ttf'),
            os.path.join(FONTS_DIR, 'NotoSans-Regular.ttf'),
            os.path.join(FONTS_DIR, 'Arial.ttf'),
        ]
        self.pdf_font_name = 'Helvetica'
        self._pdf_font_ok = False
        for f in candidates:
            try_path = f
            if not os.path.exists(try_path):
                rel = os.path.relpath(f, APP_DIR)
                try_path = resource_path(rel)
            if os.path.exists(try_path):
                try:
                    pdfmetrics.registerFont(TTFont('CyrillicFont', try_path))
                    self.pdf_font_name = 'CyrillicFont'
                    self._pdf_font_ok = True
                    break
                except Exception:
                    pass

    def enable_kiosk(self):
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._block_close)
        for seq in ("<Escape>", "<F11>", "<Alt-Return>", "<Alt-Tab>", "<Control-f>"):
            self.root.bind_all(seq, self._ignore_key)

    def disable_kiosk_for_navigation(self):
        try:
            # self.root.attributes("-fullscreen", False)  # Keep fullscreen always
            self.root.attributes("-topmost", False)
            self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
            for seq in ("<Escape>", "<F11>", "<Alt-Return>", "<Alt-Tab>", "<Control-f>"):
                try:
                    self.root.unbind_all(seq)
                except Exception:
                    pass
        except Exception:
            pass

    def _block_close(self):
        return

    def _ignore_key(self, event=None):
        return "break"

    def _bind_zoom_shortcuts(self):
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.root.bind_all(seq, lambda event: self._change_zoom(0.1))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.root.bind_all(seq, lambda event: self._change_zoom(-0.1))
        self.root.bind_all("<Control-0>", lambda event: self._reset_zoom())
        self.root.bind_all("<Control-MouseWheel>", self._on_zoom_mousewheel)

    def _on_zoom_mousewheel(self, event=None):
        delta = 0.1 if event and event.delta > 0 else -0.1
        return self._change_zoom(delta)

    def _change_zoom(self, delta):
        self.zoom_factor = max(0.8, min(2.0, round(self.zoom_factor + delta, 2)))
        self._refresh_current_image()
        self._apply_zoom()
        return "break"

    def _reset_zoom(self):
        self.zoom_factor = 1.0
        self._refresh_current_image()
        self._apply_zoom()
        return "break"

    def _quiz_image_bounds(self):
        self.root.update_idletasks()
        win_w = max(800, self.root.winfo_width())
        screen_h = self.root.winfo_screenheight() or 720
        base_h = min(int(screen_h * 0.35), 450)
        base_w = min(win_w - 160, 1000)
        max_h = min(int(screen_h * 0.7), int(base_h * self.zoom_factor))
        max_w = min(win_w - 80, int(base_w * self.zoom_factor))
        return max_w, max_h

    def _refresh_current_image(self):
        img_label = self._current_widgets.get("image_label") if hasattr(self, "_current_widgets") else None
        image_name = self._current_widgets.get("image_name") if hasattr(self, "_current_widgets") else None
        if not img_label or not image_name:
            return
        max_w, max_h = self._quiz_image_bounds()
        img = self._load_image(image_name, max_w=max_w, max_h=max_h)
        if img is None:
            return
        try:
            img_label.config(image=img)
            img_label.image = img
        except Exception:
            pass

    def _apply_zoom(self):
        self._apply_zoom_to_widget(self.root)
        self._apply_button_effects(self.root)

    def _apply_zoom_to_widget(self, widget):
        try:
            font_value = widget.cget("font")
        except Exception:
            font_value = None
        if font_value and not getattr(widget, "_skip_zoom", False):
            try:
                if not hasattr(widget, "_base_font_config"):
                    base_font = tkfont.Font(font=font_value)
                    widget._base_font_config = {
                        "family": base_font.cget("family"),
                        "size": base_font.cget("size"),
                        "weight": base_font.cget("weight"),
                        "slant": base_font.cget("slant"),
                        "underline": base_font.cget("underline"),
                        "overstrike": base_font.cget("overstrike"),
                    }
                cfg = dict(widget._base_font_config)
                base_size = int(cfg.get("size") or 10)
                sign = -1 if base_size < 0 else 1
                cfg["size"] = sign * max(8, int(round(abs(base_size) * self.zoom_factor)))
                widget.configure(font=(cfg["family"], cfg["size"], cfg["weight"], cfg["slant"]))
            except Exception:
                pass
        for child in widget.winfo_children():
            self._apply_zoom_to_widget(child)

    def _apply_button_effects(self, widget):
        if isinstance(widget, tk.Button) and not getattr(widget, "_hover_ready", False):
            try:
                normal_bg = widget.cget("bg")
                widget._normal_bg = normal_bg
                widget._hover_bg = self._button_hover_color(normal_bg)
                widget.configure(activebackground=widget._hover_bg, relief="raised", bd=1)
                widget.bind("<Enter>", self._on_button_enter, add="+")
                widget.bind("<Leave>", self._on_button_leave, add="+")
                widget._hover_ready = True
            except Exception:
                pass
        for child in widget.winfo_children():
            self._apply_button_effects(child)

    def _button_hover_color(self, bg):
        colors = {
            BTN_BG: self._theme_color("button_hover"),
            self._theme_color("button"): self._theme_color("button_hover"),
            BTN_BG_ACTIVE: self._theme_color("button_active"),
            self._theme_color("button_active"): self._theme_color("button_hover"),
            "#8e3e3e": self._theme_color("danger"),
            "#2e7d32": self._theme_color("option_correct"),
            "#c62828": self._theme_color("option_wrong"),
            "#424242": self._theme_color("option_neutral"),
        }
        return colors.get(bg, self._theme_color("button_hover"))

    def _on_button_enter(self, event=None):
        widget = event.widget if event else None
        if not widget:
            return
        try:
            if str(widget.cget("state")) != "disabled":
                widget._pre_hover_bg = widget.cget("bg")
                widget.configure(bg=getattr(widget, "_hover_bg", widget.cget("bg")))
        except Exception:
            pass

    def _on_button_leave(self, event=None):
        widget = event.widget if event else None
        if not widget:
            return
        try:
            if str(widget.cget("state")) != "disabled":
                widget.configure(bg=getattr(widget, "_pre_hover_bg", widget.cget("bg")))
        except Exception:
            pass

    def exit_kiosk(self):
        # Stop any playing radio first
        stop_music()
        if self.ffplay_process:
            try:
                self.ffplay_process.terminate()
            except Exception:
                pass
        self.root.attributes("-fullscreen", False)
        self.root.attributes("-topmost", False)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.destroy()

    def _confirm_and_exit(self):
        if messagebox.askyesno("Изход", "Сигурни ли сте, че искате да излезете?"):
            self.exit_kiosk()

    def _add_exit_button(self):
        try:
            if hasattr(self, "_exit_btn") and self._exit_btn:
                self._exit_btn.destroy()
        except Exception:
            pass
        self._exit_btn = tk.Button(self.root, text="Изход", font=("Arial", 12, "bold"),
                                   bg="#8e3e3e", fg="white", activebackground="#a85a5a",
                                   cursor="hand2", command=self._confirm_and_exit)
        self._exit_btn.place(relx=1.0, x=-12, y=12, anchor="ne")

        for btn in getattr(self, "_zoom_buttons", []):
            try:
                btn.destroy()
            except Exception:
                pass
        self._zoom_buttons = []
        zoom_frame = tk.Frame(self.root, bg="#1e1e2f")
        zoom_frame.place(relx=1.0, x=-135, y=12, anchor="ne")
        self._zoom_buttons.append(zoom_frame)

        minus_btn = tk.Button(zoom_frame, text="-", font=("Arial", 12, "bold"),
                              bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                              cursor="hand2", relief="raised", bd=2, width=3,
                              command=lambda: self._change_zoom(-0.1))
        minus_btn._skip_zoom = True
        minus_btn.pack(side="left")

        zoom_label = tk.Label(zoom_frame, text="zoom", font=("Arial", 12, "bold"),
                              fg=BTN_FG, bg="#1e1e2f")
        zoom_label._skip_zoom = True
        zoom_label.pack(side="left", padx=6)

        plus_btn = tk.Button(zoom_frame, text="+", font=("Arial", 12, "bold"),
                             bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                             cursor="hand2", relief="raised", bd=2, width=3,
                             command=lambda: self._change_zoom(0.1))
        plus_btn._skip_zoom = True
        plus_btn.pack(side="left")
        
        # Add radio button at top left
        try:
            if hasattr(self, "_radio_btn") and self._radio_btn:
                self._radio_btn.destroy()
        except Exception:
            pass
        self._radio_btn = tk.Button(self.root, text='🎵 Радио', font=("Arial", 12, "bold"), bg=BTN_BG, fg=BTN_FG, 
                                    activebackground=BTN_BG_ACTIVE, cursor="hand2", relief="raised", bd=2,
                                    command=self._open_radio_player)
        if self.in_test:
            self._radio_btn.place(relx=0, rely=1.0, x=12, y=-12, anchor="sw")
        else:
            self._radio_btn.place(relx=0, x=12, y=12, anchor="nw")
        self._apply_theme()
        self._apply_zoom()
        self._apply_skin_music()

    def _ask_admin_password(self, title="Администратор", prompt="Въведете администраторска парола:", width_px=520):
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.configure(bg="#1e1e2f")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        frm = tk.Frame(dlg, bg="#1e1e2f")
        frm.pack(padx=16, pady=16, fill="both", expand=True)
        tk.Label(frm, text=prompt, font=("Arial", 14), fg="white", bg="#1e1e2f", anchor="w").pack(fill="x", pady=(0, 10))
        ent = tk.Entry(frm, show="*", font=("Arial", 14), width=40)
        ent.pack(fill="x")
        ent.focus_set()
        btns = tk.Frame(frm, bg="#1e1e2f")
        btns.pack(pady=(14, 0), fill="x")
        result = {"value": None}
        def on_ok(event=None):
            result["value"] = ent.get()
            dlg.destroy()
        def on_cancel(event=None):
            result["value"] = None
            dlg.destroy()
        tk.Button(btns, text="OK", font=("Arial", 12), bg=BTN_BG_ACTIVE, fg=BTN_FG, command=on_ok).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="Отказ", font=("Arial", 12), bg=BTN_BG, fg=BTN_FG, command=on_cancel).pack(side="right")
        dlg.bind("<Return>", on_ok)
        dlg.bind("<Escape>", on_cancel)
        dlg.update_idletasks()
        h = dlg.winfo_height()
        dlg.geometry(f"{int(width_px)}x{h}")
        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth(); sh = dlg.winfo_screenheight()
        x = (sw // 2) - (int(width_px) // 2); y = (sh // 2) - (h // 2)
        dlg.geometry(f"+{x}+{y}")
        dlg.wait_window()
        return result["value"]

    def _default_timer_minutes(self, category):
        if category == "НВО 4 клас":
            return 60
        if category == "НВО 7 клас":
            return 75
        return 90

    def _ask_timer_settings(self, default_minutes):
        dlg = tk.Toplevel(self.root)
        dlg.title("Таймер")
        dlg.configure(bg="#1e1e2f")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        frm = tk.Frame(dlg, bg="#1e1e2f")
        frm.pack(padx=18, pady=18, fill="both", expand=True)

        tk.Label(frm, text="Да се стартира ли таймер?", font=("Arial", 16, "bold"),
                 fg="white", bg="#1e1e2f", anchor="w").pack(fill="x", pady=(0, 12))

        entry_row = tk.Frame(frm, bg="#1e1e2f")
        entry_row.pack(fill="x")
        tk.Label(entry_row, text="Време:", font=("Arial", 13), fg="white",
                 bg="#1e1e2f").pack(side="left", padx=(0, 8))
        minutes_var = tk.StringVar(value=str(default_minutes))
        ent = tk.Entry(entry_row, textvariable=minutes_var, font=("Arial", 14), width=10)
        ent.pack(side="left")

        tk.Label(frm, text="*напишете желаното време за тест в минути",
                 font=("Arial", 10, "italic"), fg="#cfcfe6", bg="#1e1e2f",
                 anchor="w").pack(fill="x", pady=(6, 0))

        btns = tk.Frame(frm, bg="#1e1e2f")
        btns.pack(pady=(16, 0), fill="x")

        result = {"seconds": None}

        def on_yes(event=None):
            raw = minutes_var.get().strip().replace(",", ".")
            try:
                minutes = float(raw)
            except ValueError:
                messagebox.showwarning("Време", "Моля, въведете валидно време в минути.", parent=dlg)
                ent.focus_set()
                return
            if minutes <= 0:
                messagebox.showwarning("Време", "Моля, въведете време по-голямо от 0.", parent=dlg)
                ent.focus_set()
                return
            result["seconds"] = max(1, int(round(minutes * 60)))
            dlg.destroy()

        def on_no(event=None):
            result["seconds"] = 0
            dlg.destroy()

        def on_cancel(event=None):
            result["seconds"] = None
            dlg.destroy()

        tk.Button(btns, text="Да", font=("Arial", 12, "bold"), bg=BTN_BG_ACTIVE,
                  fg=BTN_FG, width=10, command=on_yes).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="Не", font=("Arial", 12, "bold"), bg=BTN_BG,
                  fg=BTN_FG, width=10, command=on_no).pack(side="right")

        dlg.bind("<Return>", on_yes)
        dlg.bind("<Escape>", on_cancel)
        dlg.protocol("WM_DELETE_WINDOW", on_cancel)
        ent.focus_set()
        ent.select_range(0, tk.END)

        dlg.update_idletasks()
        width_px = 480
        h = dlg.winfo_height()
        dlg.geometry(f"{width_px}x{h}")
        dlg.update_idletasks()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        x = (sw // 2) - (width_px // 2)
        y = (sh // 2) - (h // 2)
        dlg.geometry(f"+{x}+{y}")
        dlg.wait_window()
        return result["seconds"]

    def create_start_screen(self):
        self.disable_kiosk_for_navigation()
        self.in_test = False
        self.is_admin = False
        self.timer_enabled = False
        self.timer_running = False
        self.timer_seconds = 0
        self.timer_label = None
        self.admin_demo_unlocks = False
        self._set_active_skin(self.student_profile.get("selected_skin", DEFAULT_SKIN_ID), persist=False)
        self._clear_screen()
        tk.Label(self.root, text="Изберете профил", font=("Arial", 28, "bold"), fg="white", bg="#1e1e2f").pack(pady=30)
        tk.Label(self.root, text=self._profile_summary_text(), font=("Arial", 13), fg="#cfcfe6", bg="#1e1e2f").pack(pady=(0, 12))
        tk.Button(self.root, text="Ученик", font=("Arial", 20), width=25,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                  command=self._enter_student_mode).pack(pady=15)
        tk.Button(self.root, text="Администратор", font=("Arial", 20), width=25,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                  command=self._admin_login).pack(pady=15)
        profile_tools = tk.Frame(self.root, bg="#1e1e2f")
        profile_tools.pack(pady=(12, 4))
        tk.Button(profile_tools, text="Импорт профил", font=("Arial", 13), width=16,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                  command=self.import_profile).pack(side="left", padx=4)
        tk.Button(profile_tools, text="Експорт профил", font=("Arial", 13), width=16,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                  command=self.export_profile).pack(side="left", padx=4)
        tk.Button(profile_tools, text="Нов профил", font=("Arial", 13), width=14,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                  command=self._new_student_profile).pack(side="left", padx=4)
        self.create_footer()
        self._add_exit_button()

    def _enter_student_mode(self):
        self.is_admin = False
        self.admin_demo_unlocks = False
        self._set_active_skin(self.student_profile.get("selected_skin", DEFAULT_SKIN_ID), persist=False)
        self.create_subject_screen()

    def _admin_login(self):
        pwd = self._ask_admin_password(title="Администратор", prompt="Въведете администраторска парола:", width_px=520)
        if pwd is None:
            return
        if pwd == ADMIN_PASSWORD:
            self.is_admin = True
            self.admin_demo_unlocks = False
            self.create_subject_screen()
        else:
            messagebox.showerror("Грешна парола", "Невалидна администраторска парола.")

    def _new_student_profile(self):
        if not messagebox.askyesno("Нов профил", "Да се започне ли с нов ученически профил?"):
            return
        self.student_profile = create_profile()
        self._set_active_skin(DEFAULT_SKIN_ID)
        self.create_start_screen()

    def import_profile(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Импорт на ученически профил",
            filetypes=[("Quiz профил", f"*{PROFILE_EXTENSION}"), ("JSON файлове", "*.json"), ("Всички файлове", "*.*")],
            initialdir=PROFILES_DIR,
        )
        if not path:
            return
        try:
            profile = load_profile(path)
        except Exception as exc:
            messagebox.showerror("Грешка", f"Профилът не може да бъде зареден.\n{exc}")
            return
        known_ids = set(self.skin_manager.ids())
        profile["unlocked_skins"] = [skin_id for skin_id in profile.get("unlocked_skins", []) if skin_id in known_ids]
        if DEFAULT_SKIN_ID not in profile["unlocked_skins"]:
            profile["unlocked_skins"].insert(0, DEFAULT_SKIN_ID)
        if profile.get("selected_skin") not in profile["unlocked_skins"]:
            profile["selected_skin"] = DEFAULT_SKIN_ID
        self.student_profile = profile
        self._set_active_skin(profile.get("selected_skin", DEFAULT_SKIN_ID))
        messagebox.showinfo("Готово", f"Профилът е зареден.\nКлюч: {self._profile_short_key()}")
        self.create_start_screen()

    def export_profile(self):
        os.makedirs(PROFILES_DIR, exist_ok=True)
        initial = f"quiz_profile_{self._profile_short_key()}{PROFILE_EXTENSION}"
        path = filedialog.asksaveasfilename(
            title="Експорт на ученически профил",
            defaultextension=PROFILE_EXTENSION,
            initialfile=initial,
            initialdir=PROFILES_DIR,
            filetypes=[("Quiz профил", f"*{PROFILE_EXTENSION}"), ("JSON файлове", "*.json"), ("Всички файлове", "*.*")],
        )
        if not path:
            return
        try:
            save_profile(self.student_profile, path)
        except Exception as exc:
            messagebox.showerror("Грешка", f"Профилът не може да бъде записан.\n{exc}")
            return
        messagebox.showinfo("Готово", f"Профилът е записан тук:\n{path}")

    def open_skin_window(self):
        unlocked = set(self.student_profile.get("unlocked_skins") or [DEFAULT_SKIN_ID])
        admin_preview = bool(self.is_admin)
        dlg = tk.Toplevel(self.root)
        dlg.title("Преглед на скинове" if admin_preview else "Скинове")
        dlg.configure(bg=self._theme_color("bg"))
        dlg.geometry("760x620")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(
            dlg,
            text="Преглед на скинове" if admin_preview else "Избери скин",
            font=(self._theme_font(), 20, "bold"),
            fg=self._theme_color("text"),
            bg=self._theme_color("bg"),
        ).pack(pady=(18, 8))

        summary_text = (
            "Админ режим: всички скинове са достъпни само за преглед."
            if admin_preview
            else self._profile_summary_text()
        )
        tk.Label(
            dlg,
            text=summary_text,
            font=(self._theme_font(), 11),
            fg=self._theme_color("muted"),
            bg=self._theme_color("bg"),
        ).pack(pady=(0, 12))

        selected_var = tk.StringVar(value=self.active_skin.get("id") if admin_preview else self.student_profile.get("selected_skin", DEFAULT_SKIN_ID))

        list_outer = tk.Frame(dlg, bg=self._theme_color("bg"))
        list_outer.pack(fill="both", expand=True, padx=18)
        list_canvas = tk.Canvas(list_outer, bg=self._theme_color("bg"), highlightthickness=0)
        list_scrollbar = tk.Scrollbar(list_outer, orient="vertical", command=list_canvas.yview)
        list_frame = tk.Frame(list_canvas, bg=self._theme_color("bg"))
        list_window = list_canvas.create_window((0, 0), window=list_frame, anchor="nw")
        list_canvas.configure(yscrollcommand=list_scrollbar.set)
        list_canvas.pack(side="left", fill="both", expand=True)
        list_scrollbar.pack(side="right", fill="y")
        list_frame.bind("<Configure>", lambda event: list_canvas.configure(scrollregion=list_canvas.bbox("all")))
        list_canvas.bind("<Configure>", lambda event: list_canvas.itemconfigure(list_window, width=event.width))

        def preview_skin(skin_id):
            selected_var.set(skin_id)
            self._set_active_skin(
                skin_id,
                play_select_sound=True,
                allow_locked=True,
                persist=False,
            )
            self._apply_theme_to_widget(dlg)

        for skin in self.skin_manager.all():
            is_unlocked = admin_preview or skin["id"] in unlocked
            real_unlocked = skin["id"] in unlocked
            colors = skin.get("colors") or DEFAULT_COLORS
            row = tk.Frame(list_frame, bg=self._theme_color("panel"), padx=10, pady=8)
            row.pack(fill="x", pady=5)

            swatch = tk.Canvas(row, width=78, height=30, highlightthickness=0, bg=colors.get("bg", self._theme_color("bg")))
            swatch._preserve_theme_colors = True
            swatch.create_rectangle(0, 0, 26, 30, fill=colors.get("button", "#444"), outline="")
            swatch.create_rectangle(26, 0, 52, 30, fill=colors.get("button_active", "#777"), outline="")
            swatch.create_rectangle(52, 0, 78, 30, fill=colors.get("accent", "#aaa"), outline="")
            swatch.pack(side="left", padx=(0, 10))

            label_text = skin["name"]
            detail = skin.get("description") or ""
            if admin_preview and not real_unlocked:
                detail = f"Админ преглед: {self.skin_manager.requirement_label(skin)}"
            elif not is_unlocked:
                detail = f"Заключен: {self.skin_manager.requirement_label(skin)}"
            rb = tk.Radiobutton(
                row,
                text=f"{label_text}\n{detail}",
                variable=selected_var,
                value=skin["id"],
                indicatoron=0,
                anchor="w",
                justify="left",
                width=38,
                state=("normal" if is_unlocked else "disabled"),
                font=(self._theme_font(), 12, "bold"),
                bg=self._theme_color("button" if is_unlocked else "panel"),
                fg=self._theme_color("text" if is_unlocked else "muted"),
                activebackground=self._theme_color("button_hover"),
                activeforeground=self._theme_color("text"),
                selectcolor=self._theme_color("button_active"),
                disabledforeground=self._theme_color("muted"),
                relief="ridge",
                bd=2,
                padx=8,
                pady=5,
                command=(lambda sid=skin["id"]: preview_skin(sid)) if admin_preview else None,
            )
            rb.pack(side="left", fill="x", expand=True)
            if admin_preview:
                tk.Button(
                    row,
                    text="Преглед",
                    font=(self._theme_font(), 11, "bold"),
                    bg=self._theme_color("button_active"),
                    fg=self._theme_color("text"),
                    activebackground=self._theme_color("button_hover"),
                    command=lambda sid=skin["id"]: preview_skin(sid),
                    width=10,
                ).pack(side="left", padx=(10, 0))

        buttons = tk.Frame(dlg, bg=self._theme_color("bg"))
        buttons.pack(fill="x", padx=18, pady=16)

        def apply_skin():
            skin_id = selected_var.get()
            if skin_id not in unlocked and not admin_preview:
                return
            self._set_active_skin(
                skin_id,
                play_select_sound=True,
                allow_locked=admin_preview,
                persist=not admin_preview,
            )
            dlg.destroy()

        tk.Button(
            buttons,
            text="Прегледай" if admin_preview else "Прилагане",
            font=(self._theme_font(), 12, "bold"),
            bg=self._theme_color("button_active"),
            fg=self._theme_color("text"),
            activebackground=self._theme_color("button_hover"),
            command=apply_skin,
            width=16,
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            buttons,
            text="Затвори",
            font=(self._theme_font(), 12),
            bg=self._theme_color("button"),
            fg=self._theme_color("text"),
            activebackground=self._theme_color("button_hover"),
            command=dlg.destroy,
            width=16,
        ).pack(side="right")

        self._apply_theme_to_widget(dlg)

    def create_subject_screen(self):
        self.disable_kiosk_for_navigation()
        self.in_test = False
        self.timer_enabled = False
        self.timer_running = False
        self.timer_seconds = 0
        self.timer_label = None
        self._clear_screen()
        tk.Label(self.root, text="Избери предмет", font=("Arial", 28, "bold"), fg="white", bg="#1e1e2f").pack(pady=30)
        if not self.is_admin:
            tk.Label(
                self.root,
                text=(
                    "За да отключиш нови скинове, отговаряй правилно на въпросите от тестовете. "
                    "30 верни отговора - лесен скин, 50 - средна трудност, 100 - висока трудност"
                ),
                font=("Arial", 11),
                fg="#cfcfe6",
                bg="#1e1e2f",
                wraplength=max(520, self.root.winfo_width() - 160),
                justify="center",
            ).pack(pady=(0, 14), padx=40)
        wrap = tk.Frame(self.root, bg="#1e1e2f")
        wrap.pack()
        def select_subject(subj):
            if self.subject != subj:
                self.selected_category = None
            self.selected_subject = subj
            self.subject = subj
            for btn, val in btns:
                btn.config(bg=BTN_BG_ACTIVE if val == subj else BTN_BG)
            self.create_category_screen(subj)
        btns = []
        for subj in ("БЕЛ", "Математика"):
            b = tk.Button(wrap, text=subj, font=("Arial", 20), width=25,
                          bg=(BTN_BG_ACTIVE if self.selected_subject == subj else BTN_BG),
                          fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                          command=lambda s=subj: select_subject(s))
            b.pack(pady=15)
            btns.append((b, subj))
        if self.is_admin:
            tk.Button(self.root, text="Преглед на всички скинове", font=("Arial", 14),
                      bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                      command=self.open_skin_window).pack(pady=6)
        else:
            tk.Button(self.root, text="Разгледай скинове", font=("Arial", 14),
                      bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                      command=self.open_skin_window).pack(pady=6)
        tk.Button(self.root, text="Смяна на профил", font=("Arial", 14), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                  command=self.create_start_screen).pack(pady=10)
        self.create_footer()
        self._add_exit_button()

    def create_category_screen(self, subject):
        self.disable_kiosk_for_navigation()
        self.in_test = False
        self.timer_enabled = False
        self.timer_running = False
        self.timer_label = None
        self.subject = subject
        self._clear_screen()
        tk.Label(self.root, text=f"Избери категория ({subject})", font=("Arial", 28, "bold"), fg="white", bg="#1e1e2f").pack(pady=30)
        tk.Button(self.root, text="← Назад", font=("Arial", 16), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                  command=self.create_subject_screen).pack(pady=10)
        ctr = tk.Frame(self.root, bg="#1e1e2f")
        ctr.pack(pady=10)
        categories = ("НВО 4 клас", "НВО 7 клас", "НВО 10 клас", "НВО 12 клас")
        if self.selected_category not in categories:
            self.selected_category = None
        self.sample_size_var.set(20)
        cat_btns = []
        def style_category_buttons():
            for btn, val in cat_btns:
                selected = val == self.selected_category
                btn.config(
                    bg=self._theme_color("button_active" if selected else "button"),
                    fg=self._theme_color("text"),
                    activebackground=self._theme_color("button_hover"),
                    relief=("sunken" if selected else "raised"),
                    bd=(4 if selected else 2),
                )
        def on_select(cat):
            self.selected_category = cat
            style_category_buttons()
            start_btn.config(state="normal")
            spin.config(state="normal")
        for cat in categories:
            btn = tk.Button(ctr, text=cat, font=("Arial", 20), width=25,
                            bg=self._theme_color("button_active" if self.selected_category == cat else "button"),
                            fg=self._theme_color("text"), activebackground=self._theme_color("button_hover"),
                            relief=("sunken" if self.selected_category == cat else "raised"),
                            bd=(4 if self.selected_category == cat else 2),
                            command=lambda c=cat: on_select(c))
            btn.pack(pady=6)
            cat_btns.append((btn, cat))
        opt = tk.Frame(self.root, bg="#1e1e2f")
        opt.pack(pady=10)
        tk.Label(opt, text="Брой въпроси:", font=("Arial", 16), fg="white", bg="#1e1e2f").pack(side=tk.LEFT, padx=(0,8))
        spin = tk.Spinbox(opt, from_=1, to=999, width=5, font=("Arial", 16), textvariable=self.sample_size_var,
                          state=("normal" if self.selected_category else "disabled"))
        spin.pack(side=tk.LEFT)
        if self.is_admin:
            admin_tools = tk.Frame(self.root, bg="#1e1e2f")
            admin_tools.pack(pady=(4, 8))
            tk.Button(admin_tools, text="Преглед на всички скинове", font=("Arial", 14),
                      bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                      command=self.open_skin_window).pack(side="left", padx=5)
            demo_var = tk.BooleanVar(value=self.admin_demo_unlocks)
            def set_demo_unlocks():
                self.admin_demo_unlocks = bool(demo_var.get())
            tk.Checkbutton(admin_tools, text="Демо отключване (1/2/3 верни)", variable=demo_var,
                           command=set_demo_unlocks, indicatoron=0, font=("Arial", 14),
                           bg=(BTN_BG_ACTIVE if self.admin_demo_unlocks else BTN_BG),
                           fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                           activeforeground=BTN_FG, selectcolor=BTN_BG_ACTIVE,
                           padx=10, pady=3).pack(side="left", padx=5)
            tk.Button(self.root, text="Импорт на въпроси (Excel)", font=("Arial", 16),
                      bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                      command=self.import_questions_excel).pack(pady=10)
            tk.Button(self.root, text="Изтрий въпросите", font=("Arial", 16),
                      bg="#8e3e3e", fg="white", activebackground="#a85a5a",
                      command=self._confirm_and_delete_questions).pack(pady=6)
            tk.Button(self.root, text="Импорт на скала за оценяване (CSV)", font=("Arial", 16),
                      bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                      command=self.import_grading_scale_csv).pack(pady=6)
        start_btn = tk.Button(self.root, text="Старт", font=("Arial", 18), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                              state=("normal" if self.selected_category else "disabled"),
                              command=lambda: self.load_questions(self.selected_category, sample_size=self.sample_size_var.get()))
        start_btn.pack(pady=8)
        self.create_footer()
        self._add_exit_button()

    def import_questions_excel(self):
        filetypes = [("Excel файлове", "*.xlsx *.xls"), ("Всички файлове", "*.*")]
        path = filedialog.askopenfilename(title="Изберете Excel файл", filetypes=filetypes, initialdir=APP_DIR)
        if not path:
            return
        try:
            stats = store_excel_questions(path)
        except Exception as e:
            messagebox.showerror("Грешка", f"Неуспешен внос от Excel:\n{e}")
            return
        lines = []
        for (subject, grade), (added, total_after) in stats.items():
            lines.append(f"- {subject} / {grade}: +{added} (общо: {total_after})")
        messagebox.showinfo("Готово", "Въпросите са записани в pool.csv:\n" + "\n".join(lines))

    def import_grading_scale_csv(self):
        filetypes = [("CSV файлове", "*.csv"), ("Всички файлове", "*.*")]
        path = filedialog.askopenfilename(title="Изберете CSV файл за скала", filetypes=filetypes, initialdir=APP_DIR)
        if not path:
            return
        try:
            new_df = save_grading_scale_csv(path, GRADING_FILE)
            global grading_df
            grading_df = new_df
            messagebox.showinfo("Готово", "Скалата за оценяване е обновена.")
        except ValueError as e:
            messagebox.showerror("Грешка", str(e))
        except Exception as e:
            messagebox.showerror("Грешка", f"Неуспешен внос:\n{e}")

    # ---- Delete questions (admin) ----
    def _confirm_and_delete_questions(self):
        if not self.is_admin:
            messagebox.showwarning("Достъп", "Само администратор може да изтрива въпроси.")
            return
        if not self.subject or not (self.selected_category or self.category):
            messagebox.showwarning("Избор", "Моля, изберете предмет и категория (клас).")
            return
        pwd = self._ask_admin_password(title="Администратор", prompt="Въведете администраторска парола:", width_px=520)
        if pwd is None:
            return
        if pwd != ADMIN_PASSWORD:
            messagebox.showerror("Грешна парола", "Невалидна администраторска парола.")
            return
        subj = self.subject
        grade = (self.selected_category or self.category)
        ans = messagebox.askyesno("Потвърждение",
                                  f"Сигурни ли сте, че искате да изтриете всички въпроси за:\n\nПредмет: {subj}\nКатегория: {grade}\n\nДействието е необратимо.")
        if not ans:
            return
        deleted, folder = delete_question_csvs(self.subject, self.selected_category or self.category)
        messagebox.showinfo("Готово", f"Изтрити файлове: {deleted}\nПапка: {folder}")
        self.questions = []
        self.current_index = 0
        self.score = 0
        self.user_answers = []

    # ---- Load questions: de-duplicate & sample without replacement ----
    def load_questions(self, category, sample_size=None):
        self.category = category
        records, folder, error = load_question_records(self.subject, category, sample_size)
        if error == "missing":
            messagebox.showwarning("Липсват въпроси", f"Не са намерени CSV файлове в {folder}")
            return
        if error == "empty":
            messagebox.showwarning("Липсват въпроси", f"Файловете в {folder} са празни")
            return
        timer_seconds = self._ask_timer_settings(self._default_timer_minutes(category))
        if timer_seconds is None:
            return
        self.questions = records
        self.in_test = True
        self.quiz_skin_id = self.active_skin.get("id", DEFAULT_SKIN_ID)
        self._apply_skin_music()
        self.enable_kiosk()
        self.timer_seconds = timer_seconds
        self.timer_enabled = self.timer_seconds > 0
        self.current_index = 0
        self.score = 0
        self.user_answers = []
        if self.timer_enabled:
            self.start_timer()
        else:
            self.timer_running = False
        self.show_question()

    def start_timer(self):
        if self.timer_seconds <= 0:
            self.timer_enabled = False
            self.timer_running = False
            return
        self.timer_enabled = True
        self.timer_running = True
        t = threading.Thread(target=self.update_timer, daemon=True)
        t.start()

    def update_timer(self):
        while self.timer_seconds > 0 and self.timer_running:
            time.sleep(1)
            self.timer_seconds -= 1
            if self.timer_label:
                mins = self.timer_seconds // 60
                secs = self.timer_seconds % 60
                try:
                    self.timer_label.config(text=f"Оставащо време: {mins:02d}:{secs:02d}")
                except Exception:
                    pass
        if self.timer_running and self.timer_seconds == 0:
            self.root.after(0, self.end_quiz)

    def _load_image(self, filename: str, max_w=1200, max_h=700):
        if not filename:
            return None
        path = resource_path(os.path.join("images", filename))
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path)
            w, h = img.size
            if w > 0 and h > 0:
                scale = min(max_w / w, max_h / h, self.zoom_factor)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img = img.resize((new_w, new_h), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _open_virtual_keyboard(self, focus_widget=None):
        if focus_widget:
            try:
                focus_widget.focus_set()
                focus_widget.icursor(tk.END)
            except Exception:
                pass
        if os.name != "nt":
            messagebox.showinfo(
                "Виртуална клавиатура",
                "Виртуалната клавиатура е достъпна само под Windows.",
            )
            return

        windows_dir = os.environ.get("WINDIR", r"C:\Windows")
        common_program_files = os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files")
        candidates = [
            os.path.join(windows_dir, "Sysnative", "osk.exe"),
            os.path.join(windows_dir, "System32", "osk.exe"),
            "osk.exe",
            os.path.join(common_program_files, "microsoft shared", "ink", "TabTip.exe"),
        ]
        last_error = None
        for candidate in candidates:
            try:
                result = ctypes.windll.shell32.ShellExecuteW(None, "open", candidate, None, None, 1)
                if result > 32:
                    return
                last_error = f"ShellExecute error code: {result}"
            except Exception as exc:
                last_error = exc

        detail = f"\n{last_error}" if last_error else ""
        messagebox.showerror(
            "Виртуална клавиатура",
            f"Неуспешно стартиране на виртуалната клавиатура.{detail}",
        )

    # ---- Display question with wrapping ----
    def show_question(self):
        self._clear_screen()
        self.root.update_idletasks()
        q = self.questions[self.current_index]
        # compute wraplength based on current window width
        win_w = max(800, self.root.winfo_width())
        margin = 80
        wrap = max(400, win_w - margin)
        # Top bar: timer + back + progress
        top = tk.Frame(self.root, bg="#1e1e2f")
        top.pack(fill="x", pady=(8,0))
        self.timer_label = None
        if self.timer_enabled:
            mins = self.timer_seconds // 60
            secs = self.timer_seconds % 60
            self.timer_label = tk.Label(top, text=f"Оставащо време: {mins:02d}:{secs:02d}",
                                         font=("Arial", 16), fg="yellow", bg="#1e1e2f")
            self.timer_label.pack(side="left", padx=12)
        else:
            tk.Label(top, text="Без таймер", font=("Arial", 16), fg="#cfcfe6",
                     bg="#1e1e2f").pack(side="left", padx=12)
        tk.Button(top, text="← Назад", font=("Arial", 16), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                  command=lambda: self.create_category_screen(self.subject)).pack(side="left", padx=12)
        prog = tk.Frame(self.root, bg="#1e1e2f")
        prog.pack(fill="x")
        self.progress = ttk.Progressbar(prog, length=win_w-160, maximum=len(self.questions), value=self.current_index)
        self.progress.pack(pady=6)
        # Content area
        content = tk.Frame(self.root, bg="#1e1e2f")
        content.pack(fill="both", expand=True, padx=24, pady=10)

        bottom_frame = tk.Frame(self.root, bg="#1e1e2f")
        bottom_frame.pack(side="bottom", fill="x", pady=(4, 42))
        action_row = tk.Frame(bottom_frame, bg="#1e1e2f")
        action_row.pack(fill="x", pady=4)
        action_row.grid_columnconfigure(0, weight=1)
        action_row.grid_columnconfigure(1, weight=0)
        action_row.grid_columnconfigure(2, weight=1)
        button_stack = tk.Frame(action_row, bg="#1e1e2f")
        button_stack.grid(row=0, column=1)
        self._current_widgets = {
            "bottom_frame": bottom_frame,
            "action_row": action_row,
            "button_stack": button_stack,
        }

        # Image (if any)
        if q["type"] in ("mcq_img", "free_img"):
            img_label = tk.Label(content, bg="#1e1e2f")
            max_img_w, max_img_h = self._quiz_image_bounds()
            img = self._load_image(q["image"], max_w=max_img_w, max_h=max_img_h)
            if img is None:
                img_label.config(text=f"(Липсва изображение: {q['image']})", fg="tomato", font=("Arial", 14), wraplength=wrap, justify="left")
            else:
                img_label.config(image=img)
                img_label.image = img
                self._current_widgets["image_label"] = img_label
                self._current_widgets["image_name"] = q["image"]
            img_label.pack(pady=12)
        # Question text (wrapped)
        if q["question"]:
            tk.Label(content, text=q["question"], font=("Arial", 18, "bold"), bg="#1e1e2f", fg="white",
                     wraplength=wrap, justify="left").pack(pady=8, anchor="w")
        # Answers
        if q["type"] in ("mcq", "mcq_image", "mcq_img"):
            var = tk.StringVar(value="")
            var.set("")
            mcq_opts = []
            for opt in q["options"]:
                rb = tk.Radiobutton(content, text=opt, variable=var, value=opt, tristatevalue="",
                                    font=("Arial", 20, "bold"), bg="#1e1e2f", fg="white",
                                    selectcolor="#32bb5b", activeforeground="white",
                                    activebackground="#2e2e4f", highlightthickness=0,
                                    indicatoron=0, relief="ridge", bd=2,
                                    anchor="w", justify="left", wraplength=wrap-60, pady=8)
                rb.pack(fill="x", padx=40, pady=6)
                mcq_opts.append((opt, rb))
            self._current_widgets["mcq_var"] = var
            self._current_widgets["mcq_options"] = mcq_opts
            btn_confirm = tk.Button(button_stack, text="Потвърди", font=("Arial", 18, "bold"), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                                    padx=16, pady=8, command=lambda: self._check_mcq_single(q))
            btn_confirm.grid(row=0, column=1, padx=6, pady=4)
            self._current_widgets["confirm_button"] = btn_confirm
        elif q["type"] == "mcq_multi":
            vars_list = []
            mcq_opts = []
            for opt in q["options"]:
                v = tk.BooleanVar(value=False)
                v.set(False)
                cb = tk.Checkbutton(content, text=opt, variable=v,
                                    font=("Arial", 20, "bold"), bg="#1e1e2f", fg="white",
                                    activeforeground="white", activebackground="#2e2e4f", selectcolor="#32bb5b",
                                    highlightthickness=0, indicatoron=0, relief="ridge", bd=2,
                                    anchor="w", justify="left", wraplength=wrap-60, pady=8)
                cb.pack(fill="x", padx=40, pady=6)
                vars_list.append((opt, v))
                mcq_opts.append((opt, cb))
            self._current_widgets["mcq_multi_vars"] = vars_list
            self._current_widgets["mcq_multi_options"] = mcq_opts
            btn_confirm = tk.Button(button_stack, text="Потвърди", font=("Arial", 18, "bold"), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                                    padx=16, pady=8, command=lambda: self._check_mcq_multi(q))
            btn_confirm.grid(row=0, column=1, padx=6, pady=4)
            self._current_widgets["confirm_button"] = btn_confirm
        elif q["type"] in ("free", "free_img"):
            entry = tk.Entry(content, font=("Arial", 16), width=40)
            entry.pack(pady=10)
            self._current_widgets["free_entry"] = entry
            btn_keyboard = tk.Button(button_stack, text="Виртуална клавиатура", font=("Arial", 18, "bold"),
                                     bg=BTN_BG, fg=BTN_FG, padx=16, pady=8,
                                     command=lambda e=entry: self._open_virtual_keyboard(e))
            btn_keyboard.grid(row=0, column=0, padx=6, pady=4)
            self._current_widgets["keyboard_button"] = btn_keyboard
            btn_confirm = tk.Button(button_stack, text="Потвърди", font=("Arial", 18, "bold"), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                                     padx=16, pady=8, command=lambda: self._check_free(q))
            btn_confirm.grid(row=0, column=1, padx=6, pady=4)
            self._current_widgets["confirm_button"] = btn_confirm
        else:
            tk.Label(content, text=f"Непознат тип: {q['type']}", fg="tomato", bg="#1e1e2f").pack()
        self.create_footer()
        self._add_exit_button()

    def _after_answer(self, ok: bool, user_text: str, q: dict, selected_options=None):
        if selected_options is None:
            selected_options = []
        if ok:
            self.score += 1
            self._play_skin_sound("correct_sound", CORRECT_SOUND)
            msg = "Коректен отговор!"
            color = "#4caf50"
        else:
            self._play_skin_sound("wrong_sound", WRONG_SOUND)
            msg = "Грешен отговор"
            color = "#f44336"
        # mark options visually
        answers_set = {str(x).strip() for x in q.get('answers_set', set()) if str(x).strip()}
        answers_norm = set()
        for a in answers_set:
            a_up = a.upper()
            # support both Latin and Cyrillic letters
            a_bg = LETTER_MAP_EN_TO_BG.get(a_up, a_up)
            answers_norm.add(a_bg)
            answers_norm.add(a_up)
        # map option index to letter (BG) for mcq/multi
        option_letters = {i: LETTER_MAP_EN_TO_BG.get(letter, letter)
                          for i, letter in enumerate(BG_LETTERS_BY_COUNT.get(len(q.get('options', [])), BG_LETTERS_BY_COUNT[4]))}
        correct_options = set()
        for i, opt in enumerate(q.get('options', [])):
            text = str(opt).strip()
            if not text:
                continue
            if text in answers_set or text.upper() in answers_norm:
                correct_options.add(text)
                continue
            letter = option_letters.get(i)
            if letter and (letter.upper() in answers_norm or letter in answers_norm):
                correct_options.add(text)
        selected_set = {str(opt).strip() for opt in selected_options if str(opt).strip()}

        def _mark_widget(opt, widget):
            if opt in correct_options:
                mark_bg = "#2e7d32"
            elif opt in selected_set:
                mark_bg = "#c62828"
            else:
                mark_bg = "#424242"
            widget.config(
                bg=mark_bg,
                fg="white",
                activebackground=mark_bg,
                selectcolor=mark_bg,
                disabledforeground="white",
            )
            try:
                widget.config(state="disabled")
            except Exception:
                pass

        for opt, widget in self._current_widgets.get("mcq_options", []):
            _mark_widget(opt, widget)
        for opt, widget in self._current_widgets.get("mcq_multi_options", []):
            _mark_widget(opt, widget)

        confirm_btn = self._current_widgets.get("confirm_button")
        if confirm_btn:
            confirm_btn.config(state="disabled")
        free_entry = self._current_widgets.get("free_entry")
        if free_entry:
            free_entry.config(state="disabled")
        keyboard_btn = self._current_widgets.get("keyboard_button")
        if keyboard_btn:
            try:
                keyboard_btn.destroy()
            except Exception:
                pass

        bottom_frame = self._current_widgets.get("bottom_frame")
        action_row = self._current_widgets.get("action_row")
        button_stack = self._current_widgets.get("button_stack") or bottom_frame

        # show immediate feedback label beside the action buttons so it stays visible
        feedback_parent = action_row or self.root
        feedback_wrap = max(260, min(700, self.root.winfo_width() // 3))
        feedback = tk.Label(feedback_parent, text=f"{msg}. Верен: {', '.join(sorted(answers_set))}",
                            font=("Arial", 18, "bold"), fg=color, bg="#1e1e2f",
                            wraplength=feedback_wrap, justify="left")
        if action_row:
            feedback.grid(row=0, column=2, sticky="w", padx=(24, 12), pady=4)
        else:
            feedback.pack(pady=8)
        self._current_widgets["feedback_label"] = feedback

        q_text = q.get('question') or (f"(Изображение: {q.get('image','')})" if q.get('image') else "")
        correct_show = "; ".join(sorted(answers_set))
        self.user_answers.append((q_text, user_text, correct_show, bool(ok)))
        if button_stack:
            if self.current_index + 1 >= len(self.questions):
                next_text = "Финал"
            else:
                next_text = "Следващ въпрос"
            next_btn = tk.Button(button_stack, text=next_text, font=("Arial", 18, "bold"),
                                 bg=BTN_BG_ACTIVE, fg=BTN_FG, padx=16, pady=8,
                                 command=self.next_question)
            next_btn.grid(row=0, column=0, padx=6, pady=4)
            self._current_widgets["next_button"] = next_btn
        self._apply_theme()
        self._apply_zoom()

    def _check_mcq_single(self, q):
        var = self._current_widgets.get("mcq_var")
        selected = var.get().strip() if var else ""
        if not selected:
            messagebox.showwarning("Отговор", "Моля, изберете отговор.")
            return
        ok = selected in q["answers_set"] or (len(q["answers_set"])==1 and selected == next(iter(q["answers_set"])) )
        self._after_answer(ok, selected, q, selected_options=[selected])

    def _check_mcq_multi(self, q):
        vars_list = self._current_widgets.get("mcq_multi_vars", [])
        selected_set = {opt for opt, v in vars_list if v.get()}
        ok = selected_set == q["answers_set"]
        self._after_answer(ok, "; ".join(sorted(selected_set)), q, selected_options=list(selected_set))

    def _check_free(self, q):
        entry = self._current_widgets.get("free_entry")
        user = (entry.get() or "").strip()
        if q.get("compare") == "normalized":
            user_cmp = _normalize_answer(user)
            corrects_cmp = {_normalize_answer(c) for c in q["answers_set"]}
            ok = user_cmp in corrects_cmp
        else:
            ok = user in {c.strip() for c in q["answers_set"]}
        self._after_answer(ok, user, q)

    def next_question(self):
        self.current_index += 1
        if self.current_index < len(self.questions):
            self.show_question()
        else:
            self.end_quiz()

    def _result_image_box_size(self):
        try:
            self.root.update_idletasks()
            width = self.root.winfo_width() or self.root.winfo_screenwidth()
            height = self.root.winfo_height() or self.root.winfo_screenheight()
        except Exception:
            width, height = 900, 650
        zoom = max(1.0, float(getattr(self, "zoom_factor", 1.0) or 1.0))
        usable_width = max(RESULT_IMAGE_MIN_SIZE, int(width) - 180)
        usable_height = max(RESULT_IMAGE_MIN_SIZE, int(height) - int(RESULT_IMAGE_RESERVED_HEIGHT * zoom))
        return max(RESULT_IMAGE_MIN_SIZE, min(RESULT_IMAGE_MAX_SIZE, usable_width, usable_height))

    def _load_result_image(self, success: bool, max_size=None):
        skin_field = "win_image" if success else "fail_image"
        fallback = HAPPY_PNG if success else resource_path(os.path.join("images", "sad.png"))
        path = self.skin_manager.asset_path(self.active_skin, skin_field) or fallback
        if not os.path.exists(path):
            try:
                rel = os.path.relpath(path, APP_DIR)
                path = resource_path(rel)
            except Exception:
                pass
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path)
            target = max(1, int(max_size or RESULT_IMAGE_MAX_SIZE))
            w, h = img.size
            if w > 0 and h > 0:
                scale = min(target / w, target / h)
                new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
                if new_size != img.size:
                    img = img.resize(new_size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _show_result_image(self, photo, box_size):
        box = tk.Frame(
            self.root,
            width=box_size,
            height=box_size,
            bg=self._theme_color("bg"),
        )
        box.pack(pady=(10, 8))
        box.pack_propagate(False)
        lbl = tk.Label(box, image=photo, bg=self._theme_color("bg"))
        lbl.image = photo
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        return lbl

    def open_link_minimized(self, url: str):
        if self.in_test:
            return
        try:
            self.root.iconify()
        except Exception:
            pass
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def end_quiz(self):
        self.in_test = False
        self.disable_kiosk_for_navigation()
        self.timer_enabled = False
        self.timer_running = False
        self.timer_label = None
        self._clear_screen()
        points = (self.score / len(self.questions)) * 100 if self.questions else 0.0
        grade = self.get_grade(points)
        demo_unlocks = bool(self.is_admin and self.admin_demo_unlocks)
        updated_profile, new_skin_ids = update_profile_after_result(
            self.student_profile,
            subject=self.subject,
            category=self.category,
            correct=self.score,
            total=len(self.questions),
            points=points,
            grade=grade,
            skin_manager=self.skin_manager,
            demo_unlocks=demo_unlocks,
        )
        result_profile = updated_profile
        if not self.is_admin:
            self.student_profile = updated_profile
            result_profile = self.student_profile
        selected_result_skin = getattr(self, "quiz_skin_id", None) or result_profile.get("selected_skin", DEFAULT_SKIN_ID)
        if new_skin_ids:
            self._set_active_skin(selected_result_skin, allow_locked=self.is_admin, persist=False)
            unlock_sound = self.skin_manager.asset_path(self.active_skin, "unlock_sound")
            if unlock_sound:
                play_sound(unlock_sound)
        else:
            self._set_active_skin(selected_result_skin, allow_locked=self.is_admin, persist=False)
        result_image_box_size = self._result_image_box_size()
        if grade >= 3.00:
            self._play_skin_sound("success_sound", SUCCESS_SOUND)
            photo = self._load_result_image(success=True, max_size=result_image_box_size)
            if photo:
                self._show_result_image(photo, result_image_box_size)
        else:
            self._play_skin_sound("fail_sound", FAIL_SOUND)
            photo = self._load_result_image(success=False, max_size=result_image_box_size)
            if photo:
                self._show_result_image(photo, result_image_box_size)
        self._add_exit_button()
        tk.Label(self.root, text="Край на теста!", font=("Arial", 28, "bold"), fg="white", bg="#1e1e2f").pack(pady=30)
        tk.Label(self.root, text=f"Твоят резултат: {self.score}/{len(self.questions)}", font=("Arial", 24), fg="yellow", bg="#1e1e2f").pack(pady=10)
        tk.Label(self.root, text=f"Точки: {points:.2f}", font=("Arial", 20), fg="white", bg="#1e1e2f").pack(pady=10)
        if grade < 3.00:
            tk.Label(self.root, text="Оценка: 2.00 (под минималния праг от 30 точки)", font=("Arial", 20), fg="#ff7f7f", bg="#1e1e2f").pack(pady=5)
        else:
            tk.Label(self.root, text=f"Оценка: {grade:.2f}", font=("Arial", 24), fg="lightgreen", bg="#1e1e2f").pack(pady=20)
        if self.is_admin:
            demo_text = "Админ демо отключване: профилът на ученика не е променен." if demo_unlocks else "Админ тест: профилът на ученика не е променен."
            tk.Label(self.root, text=demo_text, font=("Arial", 14, "bold"),
                     fg=self._theme_color("muted"), bg="#1e1e2f",
                     wraplength=max(600, self.root.winfo_width()-100), justify="center").pack(pady=5)
        if new_skin_ids:
            skin_names = ", ".join(self.skin_manager.get(skin_id)["name"] for skin_id in new_skin_ids)
            unlock_prefix = "Демо отключен скин" if self.is_admin else "Нов отключен скин"
            tk.Label(self.root, text=f"{unlock_prefix}: {skin_names}", font=("Arial", 18, "bold"),
                     fg=self._theme_color("accent"), bg="#1e1e2f",
                     wraplength=max(600, self.root.winfo_width()-100), justify="center").pack(pady=8)
        if grade < 6.00:
            tk.Label(self.root, text=(
                "Тук можеш да намериш дигитални материали, с които да подобриш "
                "знанията и уменията си по предмета:"),
                font=("Arial", 16), fg="white", bg="#1e1e2f", wraplength=max(600, self.root.winfo_width()-100), justify="left").pack(pady=10)
            link = LINKS.get(self.subject, {}).get(self.category)
            if link:
                tk.Button(self.root, text="Отвори ресурси", font=("Arial", 18), fg="blue", bg=BTN_BG,
                          command=lambda l=link: self.open_link_minimized(l)).pack(pady=10)
        tk.Button(self.root, text="Експорт на отчет (PDF)", font=("Arial", 18), bg=BTN_BG_ACTIVE, fg=BTN_FG,
                  command=lambda: self.export_pdf(points, grade)).pack(pady=10)
        result_tools = tk.Frame(self.root, bg="#1e1e2f")
        result_tools.pack(pady=4)
        if not self.is_admin:
            tk.Button(result_tools, text="Експорт профил", font=("Arial", 16), bg=BTN_BG, fg=BTN_FG,
                      activebackground=BTN_BG_ACTIVE, command=self.export_profile).pack(side="left", padx=6)
        tk.Button(result_tools, text="Скинове", font=("Arial", 16), bg=BTN_BG, fg=BTN_FG,
                  activebackground=BTN_BG_ACTIVE, command=self.open_skin_window).pack(side="left", padx=6)
        tk.Button(self.root, text="Начало", font=("Arial", 20), bg=BTN_BG, fg=BTN_FG,
                  command=self.create_start_screen).pack(pady=30)
        self.create_footer()
        self._apply_theme()
        self._apply_zoom()
        self._apply_skin_music()

    def get_grade(self, points: float) -> float:
        return calculate_grade(points, grading_df)

    def _open_footer_url(self, event=None):
        if self.in_test:
            return
        self.open_link_minimized(FOOTER_URL)

    def _open_team_window(self, event=None):
        open_team_window(self.root)

    def _open_instructions_window(self, event=None):
        open_instructions_window(self.root)

    def _open_radio_player(self, event=None):
        stop_music()
        self._skin_music_path = None
        open_radio_player(self)

    def create_footer(self):
        build_footer(self)

    def export_pdf(self, points: float, grade: float):
        out_path = build_pdf_report(
            reports_dir=REPORTS_DIR,
            subject=self.subject,
            category=self.category,
            questions_count=len(self.questions),
            score=self.score,
            points=points,
            grade=grade,
            user_answers=self.user_answers,
            pdf_font_name=self.pdf_font_name,
        )
        try:
            messagebox.showinfo("Готово", f"PDF отчетът е записан тук:\n{out_path}")
        except Exception:
            pass

if __name__ == "__main__":
    os.makedirs(QUESTIONS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    os.makedirs(FONTS_DIR, exist_ok=True)
    os.makedirs(SKINS_DIR, exist_ok=True)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    os.makedirs(PROFILES_DIR, exist_ok=True)
    root = tk.Tk()
    app = QuizApp(root)
    root.mainloop()
