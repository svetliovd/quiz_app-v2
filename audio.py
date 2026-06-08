import os

import pygame


try:
    pygame.mixer.init()
    AUDIO_READY = True
except Exception:
    AUDIO_READY = False


def play_sound(path: str):
    if AUDIO_READY and path and os.path.exists(path):
        try:
            pygame.mixer.Sound(path).play()
        except Exception:
            pass
