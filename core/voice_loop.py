"""
Phase 28 — Fully Autonomous Voice Pipeline

Wake word detected -> record command -> STT -> brain -> sentence-chunked TTS -> repeat.
No browser, no push-to-talk. Runs as a daemon thread.

Usage:
    from core.voice_loop import voice_loop
    voice_loop.start(whisper_model)   # pass the loaded WhisperModel from app.py
    voice_loop.stop()
"""

import os
import re
import tempfile
import threading
import time
import wave

import numpy as np

from core import wake_word_detector
from core.voice import speak_async, stop_speaking
from core.brain import process_input_stream

SAMPLE_RATE      = 16000
CHUNK_SECS       = 0.4          # recording chunk size
SILENCE_THRESHOLD = 0.012       # RMS below this = silence
SILENCE_AFTER    = 1.6          # seconds of silence to stop recording
MAX_RECORD_SECS  = 14           # hard cap per command

# Sentence-end markers — flush TTS at these
_SENT_END = re.compile(r'[.!?\n]+\s*$')

_MAX_SILENCE_CHUNKS = int(SILENCE_AFTER / CHUNK_SECS)   # ~4 chunks
_MAX_RECORD_CHUNKS  = int(MAX_RECORD_SECS / CHUNK_SECS)  # ~35 chunks


def _save_wav(path: str, audio: np.ndarray):
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())


def _record_command() -> str | None:
    """
    Record until SILENCE_AFTER seconds of silence after speech begins.
    Returns path to temp WAV or None if no speech detected.
    """
    try:
        import sounddevice as sd
    except ImportError:
        print("[voice_loop] sounddevice not installed")
        return None

    chunks = []
    speech_started  = False
    silence_chunks  = 0

    for _ in range(_MAX_RECORD_CHUNKS):
        try:
            audio = sd.rec(
                int(CHUNK_SECS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='float32',
                blocking=True
            )
            chunk = audio.flatten()
        except Exception as e:
            print(f"[voice_loop] record error: {e}")
            break

        rms = float(np.sqrt(np.mean(chunk ** 2)))

        if rms >= SILENCE_THRESHOLD:
            speech_started = True
            silence_chunks = 0
            chunks.append(chunk)
        elif speech_started:
            chunks.append(chunk)
            silence_chunks += 1
            if silence_chunks >= _MAX_SILENCE_CHUNKS:
                break
        # No speech yet — keep waiting, don't accumulate

    if not chunks:
        return None

    all_audio = np.concatenate(chunks)
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp_path = tmp.name
    tmp.close()
    _save_wav(tmp_path, all_audio)
    return tmp_path


def _transcribe(model, wav_path: str) -> str:
    """Transcribe wav. Uses Parakeet if configured, else Whisper."""
    try:
        from config import STT_BACKEND
        if STT_BACKEND == "parakeet":
            from core import parakeet_stt
            if parakeet_stt.is_ready():
                return parakeet_stt.transcribe(wav_path)
            # fallthrough to Whisper if parakeet not ready
        if model is None:
            return ""
        segments, _ = model.transcribe(wav_path, language='en', vad_filter=True)
        return ' '.join(s.text.strip() for s in segments).strip()
    except Exception as e:
        print(f"[voice_loop] STT error: {e}")
        return ""


def _speak_streaming(token_gen, barge_event=None) -> str:
    """
    Consume token stream. Speak each sentence as it completes.
    If barge_event is set mid-stream (user interrupted), stop speaking early.
    Returns full response text.
    """
    buffer   = ""
    full     = []
    MIN_CHARS = 25  # don't speak tiny fragments

    for token in token_gen:
        if barge_event is not None and barge_event.is_set():
            break
        buffer += token
        full.append(token)

        # Flush on sentence boundary if buffer long enough
        if _SENT_END.search(buffer) and len(buffer.strip()) >= MIN_CHARS:
            chunk = buffer.strip()
            if chunk:
                speak_async(chunk)
            buffer = ""
        if barge_event is not None and barge_event.is_set():
            break

    # Speak remainder (unless interrupted)
    if (barge_event is None or not barge_event.is_set()) and buffer.strip() and len(buffer.strip()) >= 3:
        speak_async(buffer.strip())

    return "".join(full)


class VoiceLoop:
    def __init__(self):
        self._running  = False
        self._thread   = None
        self._model    = None
        self._barge    = threading.Event()   # set when user interrupts speech
        self._speaking = False

    # ── Barge-in monitor (Phase 51 #10) ────────────────────────────────────
    def _monitor_barge(self):
        """Run while JARVIS speaks. Sustained mic speech -> trip barge + stop TTS."""
        try:
            import sounddevice as sd
            from config import BARGE_RMS_THRESHOLD, BARGE_SUSTAIN_CHUNKS
        except Exception:
            return
        loud = 0
        # brief grace period so the start of our own TTS doesn't self-trigger
        time.sleep(0.5)
        while self._speaking and self._running and not self._barge.is_set():
            try:
                audio = sd.rec(int(0.2 * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                               channels=1, dtype='float32', blocking=True)
                rms = float(np.sqrt(np.mean(audio.flatten() ** 2)))
            except Exception:
                return
            if rms >= BARGE_RMS_THRESHOLD:
                loud += 1
                if loud >= BARGE_SUSTAIN_CHUNKS:
                    print("[voice_loop] Barge-in detected — stopping speech")
                    self._barge.set()
                    stop_speaking()
                    return
            else:
                loud = 0

    def start(self, whisper_model=None):
        if self._running:
            return
        self._model   = whisper_model
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop,
            name="VoiceLoop",
            daemon=True
        )
        self._thread.start()
        print("[voice_loop] Started")

    def stop(self):
        self._running = False
        wake_word_detector.stop()
        print("[voice_loop] Stopped")

    def is_running(self) -> bool:
        return self._running

    def _loop(self):
        wake_word_detector.start()
        print("[voice_loop] Listening for wake word...")

        while self._running:
            # Wait for wake word
            event = wake_word_detector.get_event(timeout=0.5)
            if event != "triggered":
                continue

            print("[voice_loop] Wake word — recording command...")

            # Pause wake detector so mic is free + no echo false-triggers
            wake_word_detector.stop()

            try:
                # Brief acknowledgement beep via speak
                # (short enough to not feel laggy)
                # speak_async("Yes?")   <- optional, uncomment if desired

                wav_path = _record_command()
                if not wav_path:
                    print("[voice_loop] No speech detected")
                    continue

                try:
                    # STT
                    if self._model:
                        text = _transcribe(self._model, wav_path)
                    else:
                        # Fallback: load wake model (tiny) if no main model
                        from core.wake_word_detector import _load_wake_model
                        m = _load_wake_model()
                        text = _transcribe(m, wav_path)

                    print(f"[voice_loop] Heard: '{text}'")

                    if not text.strip():
                        speak_async("Didn't catch that, boss.")
                        continue

                    # Process -> speak, with barge-in (interrupt + relisten loop)
                    try:
                        from config import BARGE_IN_ENABLED
                    except Exception:
                        BARGE_IN_ENABLED = False

                    current_text = text
                    while current_text and self._running:
                        self._barge.clear()
                        self._speaking = True
                        monitor = None
                        if BARGE_IN_ENABLED:
                            monitor = threading.Thread(target=self._monitor_barge, daemon=True)
                            monitor.start()

                        token_gen = process_input_stream(current_text)
                        response  = _speak_streaming(
                            token_gen, self._barge if BARGE_IN_ENABLED else None
                        )
                        self._speaking = False
                        if monitor:
                            monitor.join(timeout=0.5)

                        print(f"[voice_loop] Response: {response[:80]}...")

                        if self._barge.is_set():
                            # User talked over JARVIS — record their follow-up now
                            print("[voice_loop] Listening to interruption...")
                            time.sleep(0.2)
                            wav2 = _record_command()
                            if wav2:
                                current_text = _transcribe(self._model, wav2)
                                try:
                                    os.unlink(wav2)
                                except Exception:
                                    pass
                                print(f"[voice_loop] Heard (barge): '{current_text}'")
                                if current_text.strip():
                                    continue
                        break

                finally:
                    try:
                        os.unlink(wav_path)
                    except Exception:
                        pass

            except Exception as e:
                print(f"[voice_loop] Pipeline error: {e}")
                try:
                    speak_async("Hit a snag, boss. Try again.")
                except Exception:
                    pass

            finally:
                # Always resume wake detection
                if self._running:
                    time.sleep(0.3)  # brief gap before relisten
                    wake_word_detector.start()
                    print("[voice_loop] Back to listening...")

        print("[voice_loop] Loop ended")


voice_loop = VoiceLoop()
