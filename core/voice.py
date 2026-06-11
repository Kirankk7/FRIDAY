import asyncio
import edge_tts
import pygame
import os
import sys
import uuid
import time
import json
import subprocess
import threading

import config
from core.state import get_last_agent

is_speaking        = False
mixer_initialized  = False

# ─── Kokoro persistent subprocess ─────────────────────────────────────────────
_kokoro_proc  = None
_kokoro_lock  = threading.Lock()

# ─── Sequential speech queue (sentence-chunked streaming TTS) ─────────────────
import queue as _queue
_speech_q              = _queue.Queue()
_speech_worker_started = False
_speech_worker_lock    = threading.Lock()

# ─── Agent → edge-tts voice mapping ───────────────────────────────────────────
AGENT_VOICES = {
    "friday":   "en-US-JennyNeural",    # FRIDAY — warm, natural
    "athena":   "en-US-AriaNeural",     # ATHENA — clear, analytical
    "ultron":   "en-US-DavisNeural",    # ULTRON — deep male
    "veronica": "en-GB-SoniaNeural",    # VERONICA — British female
    "vision":   "en-US-NancyNeural",    # VISION — calm news reader
    "file":     "en-US-JennyNeural",
    "edith":    "en-US-MichelleNeural", # EDITH — crisp memory voice
    "personal": "en-US-JennyNeural",
    "chat":     "en-US-JennyNeural",
    "default":  "en-US-JennyNeural",
}

DEFAULT_VOICE = "en-US-JennyNeural"


def _get_agent() -> str:
    return get_last_agent() or "default"


# ─── Per-agent earcons (Phase 51 #11) ─────────────────────────────────────────
_last_earcon_agent = None
_last_earcon_ts    = 0.0

def _play_earcon(agent: str):
    """Play a short distinct cue for the agent (async, non-blocking).
    Plays once per response, not per streamed sentence: skipped when the same
    agent spoke within the last 6s (mid-response continuation)."""
    global _last_earcon_agent, _last_earcon_ts
    if not getattr(config, "EARCONS_ENABLED", True):
        return
    agent = (agent or "default").lower()
    now = time.time()
    if agent == _last_earcon_agent and (now - _last_earcon_ts) < 6.0:
        _last_earcon_ts = now   # keep extending while the same agent streams
        return
    _last_earcon_agent = agent
    _last_earcon_ts = now
    try:
        path = os.path.join("assets", "earcons", f"{agent}.wav")
        if not os.path.exists(path):
            path = os.path.join("assets", "earcons", "default.wav")
        if not os.path.exists(path):
            return
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


def _get_edge_voice() -> str:
    return AGENT_VOICES.get(_get_agent(), DEFAULT_VOICE)


# ─── Audio generation — edge-tts ──────────────────────────────────────────────
async def _generate_edge(text: str, filename: str, voice: str):
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(filename)


# ─── Audio generation — kokoro (via isolated subprocess) ─────────────────────
def _get_kokoro_proc():
    """Return (or start) the persistent Kokoro worker subprocess."""
    global _kokoro_proc
    with _kokoro_lock:
        if _kokoro_proc is None or _kokoro_proc.poll() is not None:
            worker = os.path.join(os.path.dirname(__file__), "kokoro_worker.py")
            _kokoro_proc = subprocess.Popen(
                [sys.executable, worker],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Wait for "ready" — drain non-JSON lines (e.g. "[kokoro] pipeline ready")
            # until we get {"status":"ready"} or {"status":"error"} or timeout.
            import time as _t
            deadline = _t.time() + 30
            while _t.time() < deadline:
                try:
                    ready_raw = _kokoro_proc.stdout.readline()
                    if not ready_raw:
                        break
                    ready = json.loads(ready_raw)
                    if ready.get("status") == "ready":
                        break
                    if ready.get("status") == "error":
                        print(f"[voice] kokoro worker error: {ready.get('msg')}")
                        _kokoro_proc = None
                        return None
                except json.JSONDecodeError:
                    pass  # non-JSON line (torch warnings etc.) — keep reading
                except Exception as inner_e:
                    print(f"[voice] kokoro init read error: {inner_e}")
                    break
        return _kokoro_proc


def _generate_kokoro(text: str, filename: str, agent: str) -> bool:
    """Send synthesis request to persistent worker subprocess."""
    global _kokoro_proc
    try:
        import time as _t
        proc = _get_kokoro_proc()
        if proc is None:
            return False
        abs_filename = os.path.abspath(filename)
        req = json.dumps({"text": text, "filename": abs_filename, "agent": agent})
        proc.stdin.write((req + "\n").encode("utf-8"))
        proc.stdin.flush()
        # Drain non-JSON lines — first synthesis triggers "[kokoro] pipeline ready" print
        deadline = _t.time() + 60
        while _t.time() < deadline:
            try:
                resp_raw = proc.stdout.readline()
                if not resp_raw:
                    break
                resp = json.loads(resp_raw)
                return resp.get("ok", False)
            except json.JSONDecodeError:
                pass  # non-JSON (pipeline messages) — keep reading
            except Exception as inner_e:
                print(f"[voice] kokoro read error: {inner_e}")
                break
        return False
    except Exception as e:
        print(f"[voice] kokoro subprocess error: {e}")
        with _kokoro_lock:
            _kokoro_proc = None   # force restart on next call
        return False


# ─── Mixer init ───────────────────────────────────────────────────────────────
def ensure_mixer() -> bool:
    global mixer_initialized
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        mixer_initialized = True
        return True
    except Exception as e:
        print(f"[voice] mixer init error: {e}")
        mixer_initialized = False
        return False


# ─── Sequential speech queue ──────────────────────────────────────────────────
def _speech_worker():
    """Single worker — speaks queued sentences in order (no overlap)."""
    while True:
        item = _speech_q.get()
        try:
            if item is not None:
                text, agent = item
                speak_async(text, agent=agent)
        except Exception as e:
            print(f"[voice] queue speak error: {e}")
        finally:
            _speech_q.task_done()


def enqueue_speech(text: str, agent: str = None):
    """Queue a sentence for sequential playback. Starts worker on first use."""
    global _speech_worker_started
    text = (text or "").strip()
    if not text:
        return
    with _speech_worker_lock:
        if not _speech_worker_started:
            threading.Thread(target=_speech_worker, daemon=True).start()
            _speech_worker_started = True
    _speech_q.put((text, agent))


def kokoro_status() -> bool:
    """True if the Kokoro worker subprocess is alive."""
    proc = _kokoro_proc
    return bool(proc is not None and proc.poll() is None)


# ─── Stop ─────────────────────────────────────────────────────────────────────
def stop_speaking():
    global is_speaking
    is_speaking = False
    # Drain any queued sentences so they don't keep playing after stop
    try:
        while True:
            _speech_q.get_nowait()
            _speech_q.task_done()
    except _queue.Empty:
        pass
    try:
        import winsound
        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass


# ─── Speak ────────────────────────────────────────────────────────────────────
def speak_async(text: str, agent: str = None):
    global is_speaking
    is_speaking = True

    # Sanitize text: strip, remove non-printable chars
    text = text.strip()
    if not text:
        is_speaking = False
        return
    # Truncate very long responses — TTS works best under ~500 chars
    if len(text) > 500:
        text = text[:497] + "..."

    agent    = agent or _get_agent()
    backend  = getattr(config, "TTS_BACKEND", "edge").lower()
    print(f"[voice] speak({backend}/{agent}): {text[:80]!r}...")

    # Per-agent earcon — plays now (async) while TTS generates below
    _play_earcon(agent)

    if backend == "kokoro":
        filename = f"temp_{uuid.uuid4().hex}.wav"
        ok = _generate_kokoro(text, filename, agent)
        if not ok:
            print("[voice] kokoro failed, falling back to edge-tts")
            backend = "edge"

    if backend != "kokoro":
        voice    = _get_edge_voice()
        filename = f"temp_{uuid.uuid4().hex}.mp3"
        try:
            asyncio.run(_generate_edge(text, filename, voice))
        except Exception as e:
            print(f"[voice] edge-tts error ({voice}, {len(text)} chars): {e}")
            return

    # WAV (Kokoro) → winsound: native Windows MM API, works in any process context
    if filename.endswith(".wav"):
        try:
            import winsound
            winsound.PlaySound(filename, winsound.SND_FILENAME)
        except Exception as e:
            print(f"[voice] winsound error: {e}")
        finally:
            try:
                os.remove(filename)
            except Exception:
                pass
        return

    # MP3 (edge-tts fallback) → pygame
    if not ensure_mixer():
        print("[voice] retrying audio init...")
        time.sleep(1)
        if not ensure_mixer():
            print("[voice] could not initialize audio")
            try:
                os.remove(filename)
            except Exception:
                pass
            return

    try:
        pygame.mixer.music.load(filename)
        pygame.mixer.music.set_volume(1.0)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if not is_speaking:
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)

    except Exception as e:
        print(f"[voice] playback error: {e}")
        try:
            pygame.mixer.quit()
            time.sleep(1)
            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.set_volume(1.0)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
        except Exception as recovery_error:
            print(f"[voice] recovery failed: {recovery_error}")
    finally:
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        time.sleep(0.05)
        try:
            os.remove(filename)
        except Exception:
            pass
