from core.voice import listen, speak_async


def ask_confirmation(action):
    speak_async(f"This action '{action}' requires approval. Should I proceed?")

    response = listen()

    if not response:
        return False

    response = response.lower()

    if "yes" in response or "go ahead" in response:
        return True

    return False