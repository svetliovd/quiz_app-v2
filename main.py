
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

from answer_utils import normalize_answer as _normalize_answer
from audio import play_sound
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
    QUESTIONS_DIR,
    REPORTS_DIR,
    SOUNDS_DIR,
    SUCCESS_SOUND,
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

grading_df = load_grading_scale(GRADING_FILE)

# ---------- App class ----------
class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz система")
        self.root.configure(bg="#1e1e2f")
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
            BTN_BG: "#52527a",
            BTN_BG_ACTIVE: "#3bd66a",
            "#8e3e3e": "#a94f4f",
            "#2e7d32": "#3a9840",
            "#c62828": "#df3434",
            "#424242": "#555555",
        }
        return colors.get(bg, "#52527a")

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
        self._apply_zoom()

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
        self._clear_screen()
        tk.Label(self.root, text="Изберете профил", font=("Arial", 28, "bold"), fg="white", bg="#1e1e2f").pack(pady=30)
        tk.Button(self.root, text="Ученик", font=("Arial", 20), width=25,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                  command=self._enter_student_mode).pack(pady=15)
        tk.Button(self.root, text="Администратор", font=("Arial", 20), width=25,
                  bg=BTN_BG, fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                  command=self._admin_login).pack(pady=15)
        self.create_footer()
        self._add_exit_button()

    def _enter_student_mode(self):
        self.is_admin = False
        self.create_subject_screen()

    def _admin_login(self):
        pwd = self._ask_admin_password(title="Администратор", prompt="Въведете администраторска парола:", width_px=520)
        if pwd is None:
            return
        if pwd == ADMIN_PASSWORD:
            self.is_admin = True
            self.create_subject_screen()
        else:
            messagebox.showerror("Грешна парола", "Невалидна администраторска парола.")

    def create_subject_screen(self):
        self.disable_kiosk_for_navigation()
        self.in_test = False
        self.timer_enabled = False
        self.timer_running = False
        self.timer_seconds = 0
        self.timer_label = None
        self._clear_screen()
        tk.Label(self.root, text="Избери предмет", font=("Arial", 28, "bold"), fg="white", bg="#1e1e2f").pack(pady=30)
        wrap = tk.Frame(self.root, bg="#1e1e2f")
        wrap.pack()
        def select_subject(subj):
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
        self.selected_category = None
        self.sample_size_var.set(20)
        cat_btns = []
        def on_select(cat):
            self.selected_category = cat
            for btn, val in cat_btns:
                btn.config(bg=BTN_BG_ACTIVE if val == cat else BTN_BG)
            start_btn.config(state="normal")
            spin.config(state="normal")
        for cat in ("НВО 4 клас", "НВО 7 клас", "НВО 10 клас", "НВО 12 клас"):
            btn = tk.Button(ctr, text=cat, font=("Arial", 20), width=25,
                            bg=(BTN_BG_ACTIVE if self.selected_category == cat else BTN_BG),
                            fg=BTN_FG, activebackground=BTN_BG_ACTIVE,
                            command=lambda c=cat: on_select(c))
            btn.pack(pady=6)
            cat_btns.append((btn, cat))
        opt = tk.Frame(self.root, bg="#1e1e2f")
        opt.pack(pady=10)
        tk.Label(opt, text="Брой въпроси:", font=("Arial", 16), fg="white", bg="#1e1e2f").pack(side=tk.LEFT, padx=(0,8))
        spin = tk.Spinbox(opt, from_=1, to=999, width=5, font=("Arial", 16), textvariable=self.sample_size_var, state="disabled")
        spin.pack(side=tk.LEFT)
        if self.is_admin:
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
                              state="disabled",
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
            play_sound(CORRECT_SOUND)
            msg = "Коректен отговор!"
            color = "#4caf50"
        else:
            play_sound(WRONG_SOUND)
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

    def _load_happy_image(self):
        path = HAPPY_PNG
        if not os.path.exists(path):
            rel = os.path.relpath(path, APP_DIR)
            path = resource_path(rel)
        if os.path.exists(path):
            try:
                img = Image.open(path).resize((100, 100))
                return ImageTk.PhotoImage(img)
            except Exception:
                return None
        return None

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
        if grade >= 3.00:
            play_sound(SUCCESS_SOUND)
            photo = self._load_happy_image()
            if photo:
                lbl = tk.Label(self.root, image=photo, bg="#1e1e2f")
                lbl.image = photo
                lbl.pack(pady=10)
        else:
            play_sound(FAIL_SOUND)
            sad_path = resource_path(os.path.join("images", "sad.png"))
            if os.path.exists(sad_path):
                try:
                    img = Image.open(sad_path).resize((100, 100))
                    ph = ImageTk.PhotoImage(img)
                    lbl = tk.Label(self.root, image=ph, bg="#1e1e2f")
                    lbl.image = ph
                    lbl.pack(pady=10)
                except Exception:
                    pass
        self._add_exit_button()
        tk.Label(self.root, text="Край на теста!", font=("Arial", 28, "bold"), fg="white", bg="#1e1e2f").pack(pady=30)
        tk.Label(self.root, text=f"Твоят резултат: {self.score}/{len(self.questions)}", font=("Arial", 24), fg="yellow", bg="#1e1e2f").pack(pady=10)
        tk.Label(self.root, text=f"Точки: {points:.2f}", font=("Arial", 20), fg="white", bg="#1e1e2f").pack(pady=10)
        if grade < 3.00:
            tk.Label(self.root, text="Оценка: 2.00 (под минималния праг от 30 точки)", font=("Arial", 20), fg="#ff7f7f", bg="#1e1e2f").pack(pady=5)
        else:
            tk.Label(self.root, text=f"Оценка: {grade:.2f}", font=("Arial", 24), fg="lightgreen", bg="#1e1e2f").pack(pady=20)
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
        tk.Button(self.root, text="Начало", font=("Arial", 20), bg=BTN_BG, fg=BTN_FG,
                  command=self.create_start_screen).pack(pady=30)
        self.create_footer()

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
    root = tk.Tk()
    app = QuizApp(root)
    root.mainloop()
