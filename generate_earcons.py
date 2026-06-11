"""Phase 51 #11 — generate per-agent earcons (short 2-tone signatures).
Run once: python generate_earcons.py  → writes assets/earcons/<agent>.wav"""
import wave
import struct
import math
import os

os.makedirs("assets/earcons", exist_ok=True)
SR = 44100

# agent → (tone1 Hz, tone2 Hz) — a quick rising/falling signature
SIGNATURES = {
    "friday":    (660, 880),    # warm, rising — the default assistant
    "ultron":    (196, 147),    # low, descending — menacing
    "athena":    (784, 1047),   # bright, analytical
    "vision":    (523, 659),    # mid, calm
    "veronica":  (740, 988),    # crisp, browser
    "edith":     (587, 740),    # soft, memory
    "echo":      (700, 700),    # flat, digital
    "personal":  (622, 831),
    "system":    (466, 587),    # neutral
    "file":      (554, 698),
    "scheduler": (494, 740),
    "terminator":(165, 220),    # low, robotic
    "chat":      (660, 880),
    "default":   (660, 880),
}


def _env(i, n, attack=0.15, release=0.4):
    """Fade-in/out envelope (0..1) to avoid clicks."""
    a = int(n * attack); r = int(n * release)
    if i < a:
        return i / a
    if i > n - r:
        return max(0.0, (n - i) / r)
    return 1.0


def make_earcon(path, f1, f2, dur=0.22, vol=0.22):
    n = int(SR * dur)
    half = n // 2
    with wave.open(path, "w") as w:
        w.setparams((1, 2, SR, n, "NONE", "not compressed"))
        for i in range(n):
            t = i / SR
            freq = f1 if i < half else f2
            s = vol * _env(i, n) * math.sin(2 * math.pi * freq * t)
            w.writeframes(struct.pack("h", int(s * 32767)))


for agent, (f1, f2) in SIGNATURES.items():
    make_earcon(f"assets/earcons/{agent}.wav", f1, f2)

print(f"Generated {len(SIGNATURES)} earcons in assets/earcons/")
