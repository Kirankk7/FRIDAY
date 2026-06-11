import pygame
import threading

pygame.mixer.init()

class SoundEngine:
    def __init__(self):
        self.enabled = True

    def play(self, file):
        if not self.enabled:
            return

        def _play():
            try:
                pygame.mixer.Sound(file).play()
            except:
                pass

        threading.Thread(target=_play).start()


sound_engine = SoundEngine()