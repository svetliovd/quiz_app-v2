import os
import threading

import pygame


try:
    pygame.mixer.init()
    AUDIO_READY = True
except Exception:
    AUDIO_READY = False

_music_active = False
_music_pause_count = 0
_music_lock = threading.Lock()


def play_sound(path: str):
    if AUDIO_READY and path and os.path.exists(path):
        try:
            sound = pygame.mixer.Sound(path)
            _pause_music_for(sound.get_length())
            sound.play()
        except Exception:
            pass


def play_music(path: str, loop: bool = True):
    global _music_active
    if AUDIO_READY and path and os.path.exists(path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1 if loop else 0)
            _music_active = True
        except Exception:
            pass


def stop_music():
    global _music_active, _music_pause_count
    if AUDIO_READY:
        try:
            pygame.mixer.music.stop()
            with _music_lock:
                _music_active = False
                _music_pause_count = 0
        except Exception:
            pass


def _pause_music_for(seconds: float):
    global _music_pause_count
    if not AUDIO_READY or not _music_active:
        return
    try:
        with _music_lock:
            _music_pause_count += 1
            if _music_pause_count == 1:
                pygame.mixer.music.pause()
        delay = max(0.05, float(seconds or 0.0) + 0.05)
        timer = threading.Timer(delay, _resume_music_after_sound)
        timer.daemon = True
        timer.start()
    except Exception:
        pass


def _resume_music_after_sound():
    global _music_pause_count
    if not AUDIO_READY:
        return
    try:
        with _music_lock:
            if _music_pause_count > 0:
                _music_pause_count -= 1
            should_resume = _music_active and _music_pause_count == 0
        if should_resume:
            pygame.mixer.music.unpause()
    except Exception:
        pass
