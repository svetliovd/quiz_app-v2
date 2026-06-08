import os
import re
import tkinter as tk

from config import APP_DIR, BTN_BG, BTN_BG_ACTIVE, BTN_FG


TEAM_PARTICIPANTS = [
    "РЕГИОНАЛНА МРЕЖА „ОТ ДИРЕКТОРИ ЗА ДИРЕКТОРИ“",
    "ПЛАН ЗА РАБОТА НА ГРУПА ЗА МЕЖДУИНСТИТУЦИОНАЛНА ПОДКРЕПА И СЪТРУДНИЧЕСТВО „ЗАЕДНО УСПЯВАМЕ“",
    "Училища, работещи за повишаване на образователните резултати",
    "Състав на групата:",
    "1. ГПЧЕ \"Й.Радичков\", гр. Видин",
    "координатор",
    "2. СУ \"Св.Св. Кирил и Методий\", гр. Видин",
    "координатор",
    "3. СУ \"Св.Св.Кирил и Методий\", с. Ново село",
    "4. СУ \"Христо Ботев\", с. Арчар",
    "5. СУ \"Н.Й.Вапцаров\", с. Ружинци",
    "6. СУ \"Св.Св.Кирил и Методий\", гр. Димово",
    "7. СУ \"Св.Св. Кирил и Методий\", гр. Брегово",
    "8. СУ \"Васил Левски\", гр. Кула",
    "9. ОУ \"Любен Каравелов\", гр. Видин",
    "10. СУ \"Христо Ботев\", гр. Белоградчик",
    "11. СУ \"Н.Й.Вапцаров\", с. Дреновец",
    "12. СУ \"Ц.С.Велики\", гр.Видин",
    "13. ППМГ \"Екзарх Антим I\", гр. Видин",
    "Отговорни експерти от РУО Видин:",
    "Галя Павлова старши експерт по български език и литература",
    "Ирена Водова старши експерт по математика",
]


def _scrollable_window(root, title: str):
    window = tk.Toplevel(root)
    window.title(title)
    window.configure(bg="#1e1e2f")
    window.geometry("900x700")
    window.resizable(True, True)
    window.transient(root)
    window.grab_set()

    canvas = tk.Canvas(window, bg="#1e1e2f", highlightthickness=0)
    scrollbar = tk.Scrollbar(window, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#1e1e2f")
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    return window, scrollable_frame


def open_team_window(root):
    team_window, scrollable_frame = _scrollable_window(root, "Екип и партньори")

    tk.Label(
        scrollable_frame,
        text="Екип работил по задачите",
        font=("Arial", 16, "bold"),
        fg="white",
        bg="#1e1e2f",
    ).pack(pady=10)

    for i, participant in enumerate(TEAM_PARTICIPANTS):
        anchor = "center" if i < 4 else "w"
        justify = "center" if i < 4 else "left"
        tk.Label(
            scrollable_frame,
            text=participant,
            font=("Arial", 12),
            fg="white",
            bg="#1e1e2f",
            anchor=anchor,
            justify=justify,
            wraplength=800,
        ).pack(fill="x", padx=20, pady=2)

    tk.Button(
        team_window,
        text="Затвори",
        font=("Arial", 12),
        bg=BTN_BG,
        fg=BTN_FG,
        activebackground=BTN_BG_ACTIVE,
        command=team_window.destroy,
    ).pack(pady=10)


def _load_instructions_text():
    instructions_file = os.path.join(APP_DIR, "instructions.txt")
    instructions_docx = os.path.join(APP_DIR, "instructions.docx")
    if os.path.exists(instructions_file):
        try:
            with open(instructions_file, "r", encoding="utf-8") as file:
                return file.read()
        except Exception:
            return "Грешка при зареждане на инструкциите."
    if os.path.exists(instructions_docx):
        try:
            from docx import Document
            doc = Document(instructions_docx)
            return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        except ImportError:
            return "За да се заредят инструкциите от .docx файл, инсталирайте python-docx библиотеката."
        except Exception:
            return "Грешка при зареждане на инструкциите от .docx."
    return "Инструкциите ще бъдат добавени скоро."


def _add_text(parent, text, font, fg="#f4f6ff", pady=(2, 2), padx=28, wraplength=790):
    tk.Label(
        parent,
        text=text,
        font=font,
        fg=fg,
        bg="#1e1e2f",
        anchor="w",
        justify="left",
        wraplength=wraplength,
    ).pack(fill="x", padx=padx, pady=pady)


def _add_bullet(parent, text):
    row = tk.Frame(parent, bg="#1e1e2f")
    row.pack(fill="x", padx=38, pady=2)
    tk.Label(row, text="•", font=("Arial", 13, "bold"), fg=BTN_BG_ACTIVE, bg="#1e1e2f").pack(side="left", anchor="n")
    tk.Label(
        row,
        text=text,
        font=("Arial", 12),
        fg="#f4f6ff",
        bg="#1e1e2f",
        anchor="w",
        justify="left",
        wraplength=730,
    ).pack(side="left", fill="x", expand=True, padx=(10, 0))


def _add_numbered_heading(parent, number, text):
    row = tk.Frame(parent, bg="#1e1e2f")
    row.pack(fill="x", padx=28, pady=(14, 4))
    tk.Label(
        row,
        text=f"{number}.",
        font=("Arial", 13, "bold"),
        fg=BTN_BG_ACTIVE,
        bg="#1e1e2f",
        width=3,
        anchor="w",
    ).pack(side="left", anchor="n")
    tk.Label(
        row,
        text=text,
        font=("Arial", 13, "bold"),
        fg="white",
        bg="#1e1e2f",
        anchor="w",
        justify="left",
        wraplength=740,
    ).pack(side="left", fill="x", expand=True)


def _render_instructions(parent, text):
    content = tk.Frame(parent, bg="#1e1e2f")
    content.pack(fill="both", expand=True, padx=18, pady=(0, 8))

    lines = [line.rstrip() for line in text.splitlines()]
    first_content_line = True
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        numbered_heading = re.match(r"^(\d+)\.\s+(.+):$", stripped)
        if first_content_line:
            _add_text(content, stripped, font=("Arial", 19, "bold"), fg="white", pady=(4, 12), padx=18)
            first_content_line = False
        elif numbered_heading:
            _add_numbered_heading(content, numbered_heading.group(1), numbered_heading.group(2))
        elif stripped.startswith("-"):
            _add_bullet(content, stripped.lstrip("-").strip())
        elif stripped.endswith(":"):
            _add_text(content, stripped, font=("Arial", 14, "bold"), fg=BTN_BG_ACTIVE, pady=(16, 5))
        else:
            _add_text(content, stripped, font=("Arial", 12), fg="#d9d9ee", pady=(3, 7))


def open_instructions_window(root):
    instructions_window, scrollable_frame = _scrollable_window(root, "Инструкции за употреба")

    tk.Label(
        scrollable_frame,
        text="Инструкции за употреба",
        font=("Arial", 16, "bold"),
        fg="white",
        bg="#1e1e2f",
    ).pack(pady=10)

    _render_instructions(scrollable_frame, _load_instructions_text())

    tk.Button(
        instructions_window,
        text="Затвори",
        font=("Arial", 12),
        bg=BTN_BG,
        fg=BTN_FG,
        activebackground=BTN_BG_ACTIVE,
        command=instructions_window.destroy,
    ).pack(pady=10)
