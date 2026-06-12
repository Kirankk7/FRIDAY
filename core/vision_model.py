"""
Phase 59 — local multimodal vision.

Sends an image to an Ollama vision model (llava / llama3.2-vision / qwen2-vl /
moondream) and returns a description or answer. Pure local, no cloud. Degrades
gracefully with install instructions if no vision model is pulled.

    from core.vision_model import describe_image, screenshot_describe
    describe_image("photo.jpg", "what's in this picture?")
    screenshot_describe("is there an error on screen?")
"""

import os
import base64
import tempfile

try:
    from config import OLLAMA_HOST, VISION_MODEL
except Exception:
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    VISION_MODEL = os.getenv("VISION_MODEL", "llava")

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_PULL_HINT = (f"I need a vision model for that, boss. Pull one first: "
              f"`ollama pull {VISION_MODEL}`.")


def _has_vision_model() -> bool:
    try:
        import requests
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=4)
        names = [m.get("name", "") for m in r.json().get("models", [])]
        base = VISION_MODEL.split(":")[0]
        return any(base in n for n in names)
    except Exception:
        return False


def describe_image(path: str, question: str = "") -> dict:
    """Describe / answer about an image file via the local vision model."""
    path = os.path.expanduser(path or "")
    if not path or not os.path.exists(path):
        return {"success": False, "message": "I couldn't find that image, boss.", "data": {}}
    if os.path.splitext(path)[1].lower() not in _IMG_EXTS:
        return {"success": False, "message": "That doesn't look like an image file, boss.", "data": {}}
    if not _has_vision_model():
        return {"success": False, "message": _PULL_HINT, "data": {"need_model": VISION_MODEL}}

    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return {"success": False, "message": f"Couldn't read that image: {e}", "data": {}}

    prompt = question.strip() or "Describe this image in 2-3 natural sentences."
    try:
        import requests
        r = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": VISION_MODEL, "prompt": prompt, "images": [b64],
                  "stream": False, "options": {"temperature": 0.3, "num_predict": 300}},
            timeout=120,
        )
        if r.status_code != 200:
            return {"success": False, "message": _PULL_HINT, "data": {}}
        answer = (r.json().get("response") or "").strip()
        return {"success": True, "message": answer or "I couldn't make sense of that image.",
                "data": {"model": VISION_MODEL, "path": path}}
    except Exception as e:
        return {"success": False, "message": f"Vision model error: {str(e)[:60]}", "data": {}}


def screenshot_describe(question: str = "") -> dict:
    """Grab the desktop screenshot and describe / answer about it."""
    try:
        from PIL import ImageGrab
    except Exception:
        return {"success": False, "message": "Screenshot needs Pillow installed, boss.", "data": {}}
    if not _has_vision_model():
        return {"success": False, "message": _PULL_HINT, "data": {"need_model": VISION_MODEL}}
    try:
        img = ImageGrab.grab()
        tmp = os.path.join(tempfile.gettempdir(), "jarvis_screen.png")
        img.save(tmp)
    except Exception as e:
        return {"success": False, "message": f"Couldn't capture the screen: {str(e)[:60]}", "data": {}}
    return describe_image(tmp, question or "What is shown on this screen?")
