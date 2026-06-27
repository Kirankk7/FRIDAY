import sys
# cp1252 console guard — never let a non-ASCII char (emoji, arrow, a target's accented
# title/payload/writeup text) crash output on a Windows console. The root fix.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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