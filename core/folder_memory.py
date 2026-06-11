import json
import os

FOLDER_MEMORY_FILE = "data/folder_memory.json"

os.makedirs("data", exist_ok=True)


def _load() -> dict:
    if not os.path.exists(FOLDER_MEMORY_FILE):
        return {"folder": None, "files": [], "last_match": None}
    try:
        with open(FOLDER_MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"folder": None, "files": [], "last_match": None}


def _save(data: dict):
    try:
        with open(FOLDER_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[folder_memory] save error: {e}")


def save_folder_context(folder_path, files):
    data = _load()
    data["folder"] = folder_path
    data["files"] = files
    _save(data)


def save_last_match(file_path):
    data = _load()
    data["last_match"] = file_path
    _save(data)


def get_last_match():
    return _load().get("last_match")


def get_folder_context() -> dict:
    data = _load()
    return {
        "folder": data.get("folder"),
        "files": data.get("files", [])
    }
