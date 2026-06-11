import wave
import struct
import math
import os

os.makedirs("assets", exist_ok=True)

def generate_beep(filename, freq=1000, duration=0.15, volume=0.5):
    sample_rate = 44100
    total_samples = int(sample_rate * duration)

    with wave.open(filename, 'w') as wav_file:
        wav_file.setparams((1, 2, sample_rate, total_samples, "NONE", "not compressed"))

        for i in range(total_samples):
            t = float(i) / sample_rate
            sample = volume * math.sin(2 * math.pi * freq * t)
            wav_file.writeframes(struct.pack('h', int(sample * 32767)))

def generate_click(filename, duration=0.08):
    sample_rate = 44100
    total_samples = int(sample_rate * duration)

    with wave.open(filename, 'w') as wav_file:
        wav_file.setparams((1, 2, sample_rate, total_samples, "NONE", "not compressed"))

        for i in range(total_samples):
            # quick decay click
            decay = math.exp(-20 * i / total_samples)
            sample = decay * (2 * (i % 2) - 1)
            wav_file.writeframes(struct.pack('h', int(sample * 20000)))

generate_beep("assets/listen.wav", freq=1200)
generate_click("assets/speak.wav")

print("✅ Sounds generated in /assets folder")