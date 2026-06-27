"""
Kokoro TTS — local neural TTS via hexgrad/Kokoro-82M.
Replaces cloud edge-tts when TTS_BACKEND = "kokoro" in config.
"""

import io
import os
import threading
import numpy as np

# Force CPU — prevents PyTorch from attempting CUDA/cuDNN init inside Flask process.
# Flask already has CTranslate2 (Whisper) using CUDA; dual CUDA init causes SIGSEGV.
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

_pipeline_a = None   # lang_code='a' — American English
_pipeline_b = None   # lang_code='b' — British English
_lock_a = threading.Lock()
_lock_b = threading.Lock()

SAMPLE_RATE = 24000

# Agent -> (voice_id, lang_code)
KOKORO_VOICES = {
    "friday":   ("af_heart",   "a"),   # warm American female
    "athena":   ("af_sky",     "a"),   # clear analytical female
    "ultron":   ("am_adam",    "a"),   # deep American male
    "veronica": ("bf_emma",    "b"),   # British female
    "vision":   ("af_nova",    "a"),   # calm news voice
    "edith":    ("af_bella",   "a"),   # crisp memory voice
    "personal": ("af_heart",   "a"),
    "chat":     ("af_heart",   "a"),
    "file":     ("af_heart",   "a"),
    "default":  ("af_heart",   "a"),
}

DEFAULT_VOICE  = ("af_heart", "a")


def _get_pipeline(lang_code: str):
    global _pipeline_a, _pipeline_b
    if lang_code == "b":
        if _pipeline_b is None:
            with _lock_b:
                if _pipeline_b is None:
                    from kokoro import KPipeline
                    _pipeline_b = KPipeline(lang_code="b")
                    print("[kokoro] British pipeline ready")
        return _pipeline_b
    else:
        if _pipeline_a is None:
            with _lock_a:
                if _pipeline_a is None:
                    from kokoro import KPipeline
                    _pipeline_a = KPipeline(lang_code="a")
                    print("[kokoro] American pipeline ready")
        return _pipeline_a


def synthesize(text: str, agent: str = "default") -> bytes:
    """
    Synthesize text to WAV bytes.
    Returns raw WAV bytes (24 kHz mono float32 -> 16-bit PCM).
    """
    voice_id, lang_code = KOKORO_VOICES.get(agent, DEFAULT_VOICE)

    pipeline = _get_pipeline(lang_code)

    chunks = []
    for _, _, audio in pipeline(text, voice=voice_id, speed=1.0):
        if audio is not None and len(audio) > 0:
            chunks.append(audio)

    if not chunks:
        return b""

    audio_np = np.concatenate(chunks)

    # Convert float32 -> int16 PCM WAV in-memory
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, audio_np, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()


def synthesize_to_file(text: str, filename: str, agent: str = "default") -> bool:
    """Synthesize text and write WAV file. Returns True on success."""
    try:
        wav_bytes = synthesize(text, agent)
        if not wav_bytes:
            return False
        with open(filename, "wb") as f:
            f.write(wav_bytes)
        return True
    except Exception as e:
        print(f"[kokoro] synthesis error: {e}")
        return False


def is_available() -> bool:
    try:
        import kokoro  # noqa
        return True
    except ImportError:
        return False
