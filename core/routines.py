"""
Phase 43 — Macro / Routine system.

Record a named sequence of voice commands, then replay them on demand.

    "create routine morning"   -> starts recording
    "check my tasks"           -> captured (not executed)
    "what's the weather"       -> captured
    "stop recording"           -> saves routine 'morning'
    "run routine morning"      -> executes both, in order

Recording state lives here; brain.process_input(_stream) checks is_recording()
at the top and routes captured commands here instead of executing them.
Persisted to data/routines.json.
"""
import os
import json
import threading

_FILE = "data/routines.json"
_lock = threading.Lock()


class RoutineManager:
    def __init__(self):
        self._recording = None     # name currently being recorded, or None
        self._buffer = []

    # ── storage ──
    def _load(self) -> dict:
        try:
            if os.path.exists(_FILE):
                with open(_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save(self, data: dict):
        try:
            os.makedirs("data", exist_ok=True)
            with open(_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[routines] save error: {e}")

    # ── recording ──
    def is_recording(self) -> bool:
        return self._recording is not None

    def start_recording(self, name: str) -> str:
        name = (name or "").strip().lower()
        if not name:
            return "Name the routine, boss. Say 'create routine morning'."
        with _lock:
            self._recording = name
            self._buffer = []
        return f"Recording routine '{name}'. Say your commands, then 'stop recording'."

    def add_command(self, cmd: str) -> str:
        with _lock:
            self._buffer.append(cmd)
            n = len(self._buffer)
            name = self._recording
        return f"Added to '{name}' ({n} command{'s' if n != 1 else ''}). Say 'stop recording' when done."

    def stop_recording(self) -> str:
        with _lock:
            if not self._recording:
                return "Not recording anything, boss."
            name, buf = self._recording, list(self._buffer)
            self._recording = None
            self._buffer = []
        if not buf:
            return f"Stopped — routine '{name}' had no commands, nothing saved."
        data = self._load()
        data[name] = buf
        self._save(data)
        return f"Saved routine '{name}' with {len(buf)} command{'s' if len(buf) != 1 else ''}."

    def cancel_recording(self) -> str:
        with _lock:
            name = self._recording
            self._recording = None
            self._buffer = []
        return f"Cancelled recording of '{name}'." if name else "Nothing to cancel."

    # ── management ──
    def list_routines(self) -> str:
        data = self._load()
        if not data:
            return "No routines saved yet. Say 'create routine <name>' to make one."
        return "Routines: " + " | ".join(f"{k} ({len(v)} cmds)" for k, v in data.items())

    def delete_routine(self, name: str) -> str:
        name = (name or "").strip().lower()
        data = self._load()
        if name not in data:
            return f"No routine called '{name}'."
        del data[name]
        self._save(data)
        return f"Deleted routine '{name}'."

    def get(self, name: str) -> list:
        return self._load().get((name or "").strip().lower(), [])

    # ── run ──
    def run_routine(self, name: str) -> str:
        name = (name or "").strip().lower()
        cmds = self.get(name)
        if not cmds:
            return f"No routine called '{name}'. Say 'list routines' to see what you have."
        # Lazy import to avoid circular dependency (brain imports routines)
        from core.brain import process_input
        ran = 0
        for cmd in cmds:
            try:
                process_input(cmd)
                ran += 1
            except Exception as e:
                print(f"[routines] step failed ({cmd}): {e}")
        return f"Ran routine '{name}' — {ran} of {len(cmds)} step{'s' if len(cmds) != 1 else ''} done."


routine_manager = RoutineManager()
