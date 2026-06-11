"""
Wake Word Detector — Phase 16
Runs in a background thread, continuously records 2.5s audio clips,
transcribes with a dedicated Whisper tiny model, and signals on detection.

Supported wake phrases: "friday", "hey friday", "jarvis", "hey jarvis"
"""

import os
import queue
import tempfile
import threading
import time
import wave

import numpy as np

WAKE_WORDS    = {"friday", "hey friday", "jarvis", "hey jarvis"}
SAMPLE_RATE   = 16000
CLIP_DURATION = 2.5          # seconds per detection window
ENERGY_MIN    = 0.006        # skip silent clips below this RMS

_wake_queue = queue.Queue(maxsize=20)
_running    = False
_thread     = None
_model      = None           # separate Whisper instance, loaded lazily
_model_lock = threading.Lock()


def _load_wake_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print("[wake] Loading wake word model on CUDA...")
        try:
            _model = WhisperModel("tiny", device="cuda", compute_type="float16")
            print("[wake] Whisper ready (CUDA)")
        except Exception as e:
            print(f"[wake] CUDA failed ({e}), using CPU")
            _model = WhisperModel("tiny", device="cpu", compute_type="int8")
            print("[wake] Whisper ready (CPU)")
    return _model


def _save_wav(path: str, audio: np.ndarray, sr: int = 16000):
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())


def _worker():
    global _running
    try:
        import sounddevice as sd
    except ImportError:
        print("[wake] sounddevice not installed — wake word disabled")
        _running = False
        return

    model = _load_wake_model()
    print(f"[wake] Listening for: {', '.join(sorted(WAKE_WORDS))}")

    while _running:
        try:
            # Record a short clip
            audio = sd.rec(
                int(CLIP_DURATION * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='float32',
                blocking=True
            )
            if not _running:
                break

            audio = audio.flatten()

            # Skip silent clips — saves CPU
            rms = float(np.sqrt(np.mean(audio ** 2)))
            if rms < ENERGY_MIN:
                continue

            # Transcribe
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    tmp_path = f.name
                _save_wav(tmp_path, audio)

                with _model_lock:
                    segments, _ = model.transcribe(
                        tmp_path,
                        language='en',
                        vad_filter=True
                    )
                    text = ' '.join(s.text.lower().strip() for s in segments)

                if text:
                    print(f"[wake] heard: '{text}'")
                    if any(w in text for w in WAKE_WORDS):
                        print("[wake] WAKE WORD DETECTED")
                        try:
                            _wake_queue.put_nowait("triggered")
                        except queue.Full:
                            pass

            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        except Exception as e:
            print(f"[wake] error: {e}")
            time.sleep(1)

    print("[wake] Detector stopped")


def start():
    global _running, _thread
    if _running:
        return
    _running = True
    _thread  = threading.Thread(target=_worker, daemon=True)
    _thread.start()


def stop():
    global _running
    _running = False
    print("[wake] Stopping detector...")


def is_running() -> bool:
    return _running


def get_event(timeout: float = 0.4) -> str | None:
    """Returns 'triggered' if wake word detected, else None."""
    try:
        return _wake_queue.get(timeout=timeout)
    except queue.Empty:
        return None
