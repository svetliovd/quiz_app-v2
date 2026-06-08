import os
import tkinter as tk

from PIL import Image, ImageTk

from config import resource_path


def build_footer(app):
    try:
        if app.footer_frame:
            app.footer_frame.destroy()
    except Exception:
        pass

    app.footer_frame = tk.Frame(app.root, bg="#1e1e2f")

    left_frame = tk.Frame(app.footer_frame, bg="#1e1e2f")
    left_frame.pack(side="left", fill="x", expand=True)

    logo_candidates = [
        resource_path("logo.png"),
        resource_path(os.path.join("images", "logo.png")),
    ]
    logo_path = next((path for path in logo_candidates if os.path.exists(path)), None)
    if logo_path:
        try:
            img = Image.open(logo_path)
            target_h = 14
            w, h = img.size
            target_w = max(14, int(w * (target_h / h)))
            img = img.resize((target_w, target_h), Image.LANCZOS)
            app.logo_image_small = ImageTk.PhotoImage(img)
            logo_lbl = tk.Label(
                left_frame,
                image=app.logo_image_small,
                bg="#1e1e2f",
                cursor=("hand2" if not app.in_test else "arrow"),
            )
            logo_lbl.pack(side=tk.LEFT, padx=(0, 6))
            if not app.in_test:
                logo_lbl.bind("<Button-1>", app._open_footer_url)
        except Exception:
            pass

    txt_lbl = tk.Label(
        left_frame,
        text='ППМГ "Екзарх Антим I" © 2026',
        font=("Arial", 10),
        fg="#cfcfe6",
        bg="#1e1e2f",
        cursor=("hand2" if not app.in_test else "arrow"),
    )
    txt_lbl.pack(side=tk.LEFT)
    if not app.in_test:
        txt_lbl.bind("<Button-1>", app._open_footer_url)

    instructions_frame = tk.Frame(app.footer_frame, bg="#1e1e2f")
    instructions_frame.pack(side="right")
    instructions_link = tk.Label(
        instructions_frame,
        text="Инструкции за употреба",
        font=("Arial", 10),
        fg="#cfcfe6",
        bg="#1e1e2f",
        cursor="hand2",
    )
    instructions_link.pack(side=tk.LEFT)
    instructions_link.bind("<Button-1>", app._open_instructions_window)

    right_frame = tk.Frame(app.footer_frame, bg="#1e1e2f")
    right_frame.pack(side="right")
    team_link = tk.Label(
        right_frame,
        text="Екип и партньори",
        font=("Arial", 10),
        fg="#cfcfe6",
        bg="#1e1e2f",
        cursor="hand2",
    )
    team_link.pack(side=tk.LEFT)
    team_link.bind("<Button-1>", app._open_team_window)

    app.footer_frame.place(relx=1.0, rely=1.0, x=-8, y=-6, anchor="se")
