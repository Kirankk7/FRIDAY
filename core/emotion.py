class EmotionState:
    def __init__(self):
        self.mode = "calm"

    def set_mode(self, mode):
        if mode in ["calm", "alert", "excited"]:
            self.mode = mode

    def get_mode(self):
        return self.mode


emotion_state = EmotionState()