import sys
# Force UTF-8 stdout/stderr — prevents crashes from emoji in print() on Windows cp1252
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Phase 51 #4 — structured logging: capture all print() to rotating jarvis.log
from core.logger import install_tee, log
install_tee()

from flask import Flask, request, jsonify, render_template, Response
import json
import time
import threading
import os
import glob
import tempfile

import re as _re
from core.brain import process_input, process_input_stream
from core.voice import speak_async, stop_speaking, enqueue_speech, kokoro_status
from core.state import get_last_agent

# Sentence boundary: terminal punctuation followed by space/end
_SENTENCE_SPLIT = _re.compile(r'(.+?[.!?]+["\')\]]?)(\s+|$)', _re.DOTALL)
from agents.friday.friday_agent import check_reminders, _load as _load_friday
from core import wake_word_detector
from core.scheduler import scheduler as _scheduler
from core.voice_loop import voice_loop as _voice_loop

app = Flask(__name__)


# =====================================
# STARTUP CLEANUP
# =====================================
def startup_cleanup():

    # 1. Delete orphaned temp MP3s
    mp3_files = glob.glob("temp_*.mp3")
    deleted = 0
    for f in mp3_files:
        try:
            os.remove(f)
            deleted += 1
        except Exception:
            pass
    if deleted:
        print(f"[startup] Cleaned {deleted} orphaned temp MP3s")

    # 2. Prune reflection_memory (keep last 100)
    reflection_file = "reflection_memory.json"
    try:
        if os.path.exists(reflection_file):
            with open(reflection_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if len(data) > 100:
                data = data[-100:]
                with open(reflection_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"[startup] Pruned reflection_memory to 100 entries")
    except Exception as e:
        print(f"[startup] Reflection prune error: {e}")


startup_cleanup()
_scheduler.start()  # Phase 26 — autonomous background task runner


# =====================================
# WHISPER MODEL — GPU (Phase 17)
# =====================================
from config import VOICE_LOOP_AUTO_START

print("[whisper] Loading model on CUDA...")
from faster_whisper import WhisperModel

from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_DTYPE, STT_BACKEND
try:
    _whisper_model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_DTYPE)
    print(f"[whisper] Ready ({WHISPER_DEVICE} {WHISPER_DTYPE} {WHISPER_MODEL})")
except Exception as _cuda_err:
    print(f"[whisper] {WHISPER_DEVICE} failed ({_cuda_err}), falling back to CPU")
    _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print("[whisper] Ready (CPU fallback)")


def get_whisper():
    return _whisper_model


# Phase 17b — Parakeet STT boot load
if STT_BACKEND == "parakeet":
    from core import parakeet_stt as _parakeet
    print("[parakeet] Pre-loading model (STT_BACKEND=parakeet)...")
    _parakeet_ok = _parakeet.load()
    if not _parakeet_ok:
        print("[parakeet] Load failed — falling back to Whisper for this session")
        STT_BACKEND = "whisper"
else:
    _parakeet = None


# Phase 28 — auto-start voice loop after Whisper ready
if VOICE_LOOP_AUTO_START:
    _voice_loop.start(_whisper_model)
    print("[voice_loop] Auto-started (VOICE_LOOP_AUTO_START=True)")


@app.route("/")
def home():
    return render_template("index.html")


# Phase 45 — HUD prototypes (Command-Center finale). Pick a winner → Command Mode.
@app.route("/hud/a")
def hud_proto_a():
    return render_template("hud_proto_a.html")


@app.route("/hud/b")
def hud_proto_b():
    return render_template("hud_proto_b.html")


@app.route("/hud/c")
def hud_command():
    return render_template("hud_command.html")


@app.route("/chat_stream")
def chat_stream():

    user_input = request.args.get(
        "message",
        ""
    )

    def generate():
        # Fire due reminders before processing — send as toast events
        try:
            fired = check_reminders()
            for r in fired:
                yield f"data: {json.dumps({'type': 'reminder', 'value': r})}\n\n"
        except Exception:
            pass

        yield f"data: {json.dumps({'type': 'status', 'value': 'thinking'})}\n\n"

        full_response = []
        speak_buf = ""          # accumulates text until a full sentence is ready
        speak_agent = None      # locked on first spoken sentence for voice consistency
        spoke_anything = False

        def _flush_sentences(buf, agent, final=False):
            """Emit complete sentences from buf to the TTS queue. Returns leftover buf."""
            nonlocal spoke_anything
            while True:
                m = _SENTENCE_SPLIT.match(buf)
                if not m:
                    break
                sentence = m.group(1).strip()
                buf = buf[m.end():]
                if sentence:
                    enqueue_speech(sentence, agent=agent)
                    spoke_anything = True
            if final and buf.strip():
                enqueue_speech(buf.strip(), agent=agent)
                spoke_anything = True
                buf = ""
            return buf

        yield f"data: {json.dumps({'type': 'status', 'value': 'speaking'})}\n\n"

        for chunk in process_input_stream(user_input):
            full_response.append(chunk)
            yield f"data: {json.dumps({'type': 'chunk', 'value': chunk})}\n\n"

            if speak_agent is None:
                speak_agent = get_last_agent()
            speak_buf += chunk
            speak_buf = _flush_sentences(speak_buf, speak_agent)

        # Flush trailing partial sentence
        _flush_sentences(speak_buf, speak_agent or get_last_agent(), final=True)

        response = "".join(full_response)

        # Send active agent for UI indicator
        yield f"data: {json.dumps({'type': 'agent', 'value': get_last_agent()})}\n\n"

        # Fallback: if nothing was queued (e.g. empty/punctuation-less), speak whole thing
        if not spoke_anything and response.strip():
            enqueue_speech(response.strip(), agent=get_last_agent())

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream"
    )


@app.route(
    "/transcribe",
    methods=["POST"]
)
def transcribe():
    try:
        audio_file = request.files.get("audio")

        if not audio_file:
            return jsonify({"success": False, "text": "", "error": "No audio received"})

        # Save to temp file
        suffix = ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        try:
            print(f"[stt] Audio saved: {tmp_path} ({os.path.getsize(tmp_path)} bytes) backend={STT_BACKEND}")

            if STT_BACKEND == "parakeet" and _parakeet and _parakeet.is_ready():
                # ── Parakeet path ──
                # Convert webm → wav if needed (Parakeet needs WAV)
                wav_path = tmp_path.replace(".webm", ".wav")
                try:
                    import subprocess as _sp
                    _sp.run(
                        ["ffmpeg", "-i", tmp_path, "-ar", "16000", "-ac", "1", "-y", wav_path],
                        capture_output=True, timeout=15
                    )
                    text = _parakeet.transcribe(wav_path)
                finally:
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                print(f"[parakeet] Text: '{text}'")
            else:
                # ── Whisper path (default) ──
                model = get_whisper()
                segments, info = model.transcribe(
                    tmp_path,
                    language="en",
                    vad_filter=False
                )
                segments_list = list(segments)
                text = " ".join(seg.text.strip() for seg in segments_list).strip()
                print(f"[whisper] Text: '{text}' | dur={info.duration:.1f}s | segs={len(segments_list)}")

            if not text:
                return jsonify({"success": False, "text": "", "error": "No speech detected"})

            return jsonify({"success": True, "text": text})

        except Exception as transcribe_err:
            print(f"[whisper] Transcribe error: {transcribe_err}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "text": "", "error": str(transcribe_err)})

        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    except Exception as e:
        return jsonify({"success": False, "text": "", "error": str(e)})


@app.route("/voice_loop_toggle", methods=["POST"])
def voice_loop_toggle():
    """Start/stop fully autonomous voice pipeline (Phase 28)."""
    data    = request.get_json() or {}
    enabled = data.get("enabled", False)
    if enabled:
        if not _voice_loop.is_running():
            _voice_loop.start(_whisper_model)
    else:
        _voice_loop.stop()
    return jsonify({"enabled": enabled, "running": _voice_loop.is_running()})


@app.route("/wake_toggle", methods=["POST"])
def wake_toggle():
    data    = request.get_json() or {}
    enabled = data.get("enabled", False)
    if enabled:
        wake_word_detector.start()
    else:
        wake_word_detector.stop()
    return jsonify({"enabled": enabled, "running": wake_word_detector.is_running()})


@app.route("/wake_stream")
def wake_stream():
    """SSE endpoint — pushes 'triggered' event when wake word detected."""
    def generate():
        while True:
            event = wake_word_detector.get_event(timeout=0.4)
            if event == "triggered":
                yield f"data: {json.dumps({'type': 'wake', 'value': 'triggered'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    return Response(generate(), mimetype="text/event-stream")


@app.route("/status")
def status():
    try:
        friday_data = _load_friday()
        tasks_pending = len([t for t in friday_data.get("tasks", []) if not t.get("done")])
        reminders_pending = len([r for r in friday_data.get("reminders", []) if not r.get("fired")])
        events_today = 0
        try:
            import datetime
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            events_today = len([e for e in friday_data.get("events", []) if e.get("date") == today])
        except Exception:
            pass
        ollama_online = False
        try:
            import requests as _req
            r = _req.get("http://localhost:11434/api/version", timeout=2)
            ollama_online = r.status_code == 200
        except Exception:
            pass
        return jsonify({
            "last_agent": get_last_agent(),
            "ollama_online": ollama_online,
            "tasks_pending": tasks_pending,
            "reminders_pending": reminders_pending,
            "events_today": events_today,
        })
    except Exception as e:
        return jsonify({"error": str(e), "last_agent": "friday", "ollama_online": False})


@app.route("/feedback", methods=["POST"])
def feedback():
    """Phase 56 — 👍/👎 on the last response feeds AutoTune's EMA learner."""
    from core import autotune
    data = request.get_json(silent=True) or {}
    raw = data.get("rating", 0)
    rating = 1 if str(raw) in ("1", "up", "+1", "good") else \
             -1 if str(raw) in ("-1", "down", "bad") else 0
    return jsonify(autotune.record_feedback(rating))


@app.route("/cyber_status")
def cyber_status():
    """Phase 45 Cyber mode — CVE watchlist size + last nmap scan target."""
    import json as _json
    out = {"cve_tracked": 0, "last_scan": None}
    try:
        with open("data/cve_watchlist.json", "r", encoding="utf-8") as f:
            d = _json.load(f)
            out["cve_tracked"] = len(d) if isinstance(d, (list, dict)) else 0
    except Exception:
        pass
    try:
        with open("data/scan_history.json", "r", encoding="utf-8") as f:
            hist = _json.load(f)
            if isinstance(hist, dict) and hist:
                last = sorted(hist.items(), key=lambda kv: kv[1].get("ts", ""))[-1]
                out["last_scan"] = last[0]
    except Exception:
        pass
    return jsonify(out)


@app.route("/health")
def health():
    """Full system health snapshot — one call to diagnose subsystems."""
    import shutil
    from config import OLLAMA_HOST, OLLAMA_MODEL, TTS_BACKEND
    from core.runtime_flags import is_browser_enabled

    health = {}

    # Ollama up + target model present
    ollama_up = False
    model_loaded = False
    try:
        import requests as _req
        r = _req.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code == 200:
            ollama_up = True
            models = [m.get("name", "") for m in r.json().get("models", [])]
            model_loaded = any(OLLAMA_MODEL in m for m in models)
    except Exception:
        pass
    health["ollama"] = {"up": ollama_up, "model": OLLAMA_MODEL, "model_loaded": model_loaded}

    # Whisper STT
    health["whisper"] = {"loaded": _whisper_model is not None, "model": WHISPER_MODEL}

    # Kokoro TTS worker
    health["tts"] = {"backend": TTS_BACKEND, "kokoro_worker_alive": kokoro_status()}

    # Browser
    health["browser"] = {"enabled": is_browser_enabled()}

    # Scheduler
    try:
        health["scheduler"] = {"running": getattr(_scheduler, "_running", None)}
    except Exception:
        health["scheduler"] = {"running": None}

    # Disk
    try:
        usage = shutil.disk_usage(os.getcwd())
        health["disk"] = {
            "free_gb": round(usage.free / 1e9, 1),
            "total_gb": round(usage.total / 1e9, 1),
            "pct_used": round(100 * usage.used / usage.total, 1),
        }
    except Exception:
        health["disk"] = {}

    # Overall verdict
    ok = ollama_up and model_loaded and health["whisper"]["loaded"]
    health["ok"] = ok
    return jsonify(health)


@app.route(
    "/stop",
    methods=["POST"]
)
def stop():

    try:

        stop_speaking()

        return jsonify({

            "status":
            "stopped"
        })

    except Exception as e:

        return jsonify({

            "status":
            "error",

            "message":
            str(e)
        })


if __name__ == "__main__":

    # Phase 52 #4 — boot-time config validation (loud, never fatal)
    try:
        from core.config_validator import validate
        validate(print_summary=True)
    except Exception as _e:
        print(f"[config] validator error (non-fatal): {_e}")

    app.run(

        host="127.0.0.1",

        port=5000,

        debug=False,

        use_reloader=False,

        threaded=True
    )