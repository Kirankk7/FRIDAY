
import sys, os, json

# Print sys.path BEFORE any modifications
print("SYS_PATH_BEFORE:" + json.dumps(sys.path), flush=True)

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

print("SYS_PATH_AFTER:" + json.dumps(sys.path[:8]), flush=True)
print("ROOT:" + _root, flush=True)
print(json.dumps({"status": "ready"}), flush=True)

from core.kokoro_tts import synthesize_to_file

for raw in sys.stdin:
    raw = raw.strip()
    if not raw: continue
    import traceback
    try:
        req = json.loads(raw)
        ok = synthesize_to_file(req["text"], req["filename"], req["agent"])
        print(json.dumps({"ok": ok}), flush=True)
    except Exception as ex:
        tb = traceback.format_exc()
        print(json.dumps({"ok": False, "error": str(ex), "tb": tb}), flush=True)
    break
