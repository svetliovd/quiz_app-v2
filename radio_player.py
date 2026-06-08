import subprocess
import tkinter as tk
from tkinter import ttk

from config import BTN_BG, BTN_BG_ACTIVE, BTN_FG


RADIO_STATIONS = {
    "БНР Хоризонт": "http://stream.bnr.bg:8011/horizont.aac",
    "БНР София": "http://stream.bnr.bg:8030/radio-sofia.aac",
    "Radio 1 (Класически хитове)": "http://149.13.0.81/radio1.ogg",
    "City Bulgaria": "http://31.13.223.148:8000/city.mp3",
    "Radio Fresh!": "http://31.13.223.148:8000/fresh.mp3",
    "1 Rock Bulgaria": "http://31.13.223.148:8000/1_rock.mp3",
    "Jazz FM": "https://cdn.bweb.bg/radio/jazz-fm.mp3",
    "bTV Radio": "https://cdn.bweb.bg/radio/btv-radio.mp3",
    "Nova Bulgaria": "http://31.13.223.148:8000/nova.mp3",
    "Веселина": "https://bss1.neterra.tv/veselina/veselina.m3u8",
}


def open_radio_player(app):
    radio_window = tk.Toplevel(app.root)
    radio_window.title(" 🎵 Радио")
    radio_window.configure(bg="#1e1e2f")
    radio_window.geometry("500x280")
    radio_window.resizable(False, False)
    radio_window.transient(app.root)
    radio_window.grab_set()

    tk.Label(
        radio_window,
        text="Избери радиостанция",
        font=("Arial", 16, "bold"),
        fg="white",
        bg="#1e1e2f",
    ).pack(pady=15)

    control_frame = tk.Frame(radio_window, bg="#1e1e2f")
    control_frame.pack(pady=15, padx=20, fill="x")
    tk.Label(control_frame, text="Станция:", font=("Arial", 12), fg="white", bg="#1e1e2f").pack(side="left", padx=(0, 10))

    station_var = tk.StringVar(value=list(RADIO_STATIONS.keys())[0])
    dropdown = ttk.Combobox(
        control_frame,
        textvariable=station_var,
        values=list(RADIO_STATIONS.keys()),
        state="readonly",
        width=30,
        font=("Arial", 11),
    )
    dropdown.pack(side="left", fill="x", expand=True)

    status_label = tk.Label(radio_window, text="Спрян", font=("Arial", 12), fg="#cfcfe6", bg="#1e1e2f")
    status_label.pack(pady=10)

    buttons_frame = tk.Frame(radio_window, bg="#1e1e2f")
    buttons_frame.pack(pady=10)

    def stop_radio():
        if app.ffplay_process:
            try:
                app.ffplay_process.terminate()
                app.ffplay_process = None
            except Exception:
                pass
        app.radio_playing = False
        status_label.config(text="Спрян")

    def play_radio():
        station_name = station_var.get()
        station_url = RADIO_STATIONS[station_name]
        app.current_radio_stream = station_url
        app.radio_playing = True
        status_label.config(text=f"Пуска се: {station_name}")
        try:
            if app.ffplay_process:
                try:
                    app.ffplay_process.terminate()
                except Exception:
                    pass
            app.ffplay_process = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", station_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            status_label.config(text="FFmpeg не е инсталиран")
            app.radio_playing = False
        except Exception as e:
            status_label.config(text=f"Грешка: {str(e)[:30]}")
            app.radio_playing = False

    tk.Button(
        buttons_frame,
        text="▶ Пусни",
        font=("Arial", 12),
        bg=BTN_BG_ACTIVE,
        fg=BTN_FG,
        activebackground="#3ea96e",
        cursor="hand2",
        command=play_radio,
        width=15,
    ).pack(side="left", padx=5)

    tk.Button(
        buttons_frame,
        text="⏹ Спри",
        font=("Arial", 12),
        bg=BTN_BG,
        fg=BTN_FG,
        activebackground="#525280",
        cursor="hand2",
        command=stop_radio,
        width=15,
    ).pack(side="left", padx=5)

    tk.Button(
        radio_window,
        text="Затвори",
        font=("Arial", 12),
        bg="#8e3e3e",
        fg=BTN_FG,
        activebackground="#a85a5a",
        command=lambda: (stop_radio(), radio_window.destroy()),
        width=20,
    ).pack(pady=10)
