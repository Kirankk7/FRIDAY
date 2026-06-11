from core.brain import process_input
from core.voice import listen, speak_async
from core.personality import get_intro, get_ack

print("JARVIS v5 online (Task-Aware System)")

WAKE_WORD = "friday"

while True:
    print("🟢 Listening for wake word...")

    text = listen()

    if not text:
        continue

    print(f"Heard: {text}")

    if WAKE_WORD in text:
        print("🔔 Wake word detected!")

        speak_async(get_intro())

        while True:
            user_input = listen()

            if not user_input:
                continue

            print(f"You: {user_input}")

            speak_async(get_ack())

            response = process_input(user_input)

            print(f"FRIDAY: {response}")
            speak_async(response)

            if "stop" in user_input or "sleep" in user_input:
                speak_async("Going silent.")
                break