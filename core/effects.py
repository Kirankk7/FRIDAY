import time
import sys
import random

def thinking_delay():
    delays = [0.5, 0.8, 1.2, 1.5]
    time.sleep(random.choice(delays))


def typing_effect(text):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.02)  # typing speed
    print()