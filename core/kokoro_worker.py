#!/usr/bin/env python
"""
Persistent Kokoro TTS worker process.
Spawned by voice.py as a subprocess — completely isolated from CTranslate2 (Whisper).
Reads JSON requests from stdin, writes JSON results to stdout.

Protocol:
  startup -> prints {"status":"ready"}
  request -> {"text":"...", "filename":"...", "agent":"..."}
  response<- {"ok": true/false}
"""

import os
import sys
import json

# Force CPU — avoids cuDNN / CUDA runtime init entirely
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Remove Python's auto-added script directory from sys.path.
# When spawned from a parent that loaded faster-whisper/ctranslate2, having
# D:\JARVIS\core as sys.path[0] causes AlbertModel import to fail inside kokoro.
_this_dir = os.path.dirname(os.path.abspath(__file__))
if sys.path and os.path.normcase(sys.path[0]) == os.path.normcase(_this_dir):
    sys.path.pop(0)

# Add JARVIS root to path (worker is in core/, root is one level up)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


if __name__ == "__main__":
    try:
        from core.kokoro_tts import synthesize_to_file  # loads Kokoro pipeline once
    except Exception as e:
        print(json.dumps({"status": "error", "msg": str(e)}), flush=True)
        sys.exit(1)

    # Signal parent that model is loaded and ready
    print(json.dumps({"status": "ready"}), flush=True)

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
            ok = synthesize_to_file(req["text"], req["filename"], req["agent"])
            print(json.dumps({"ok": ok}), flush=True)
        except Exception as ex:
            print(json.dumps({"ok": False, "error": str(ex)}), flush=True)
