"""
Phase 35 — Terminator: Windows desktop control.

Controls any Windows app via the UI-Automation accessibility API (pywinauto).
Pure-Python — no Rust build needed (pivoted from mediar-ai/terminator which
required a Rust toolchain).

Capabilities: list/focus/read windows, type text, press key combos, launch apps,
click named buttons. Read/launch/focus are safe; type/click affect the focused
app — used deliberately via voice commands.
"""
import os
import re
import subprocess


class TerminatorAgent:
    """Standardized Windows desktop-control agent. run(input, action, params)."""

    def _desktop(self):
        from pywinauto import Desktop
        return Desktop(backend="uia")

    # ── List open windows ──────────────────────────────────────────────────
    def list_windows(self) -> dict:
        try:
            titles = []
            for w in self._desktop().windows():
                try:
                    t = w.window_text().strip()
                    if t and t not in titles:
                        titles.append(t)
                except Exception:
                    continue
            if not titles:
                return {"success": True, "message": "No titled windows open.", "data": {"windows": []}}
            shown = titles[:12]
            msg = f"{len(titles)} open windows: " + " | ".join(shown)
            return {"success": True, "message": msg, "data": {"windows": titles}}
        except Exception as e:
            return {"success": False, "message": f"Couldn't list windows: {e}", "data": {}}

    # ── Find a window by partial title ─────────────────────────────────────
    def _find(self, title: str):
        title_l = title.lower().strip()
        best = None
        for w in self._desktop().windows():
            try:
                t = w.window_text().strip()
                if not t:
                    continue
                if title_l == t.lower():
                    return w                      # exact match wins
                if title_l in t.lower() and best is None:
                    best = w                      # first partial match
            except Exception:
                continue
        return best

    # ── Focus / bring to front ─────────────────────────────────────────────
    def focus_window(self, title: str) -> dict:
        if not title:
            return {"success": False, "message": "Which window? Give a title.", "data": {}}
        try:
            w = self._find(title)
            if not w:
                return {"success": False, "message": f"No open window matching '{title}'.", "data": {}}
            w.set_focus()
            return {"success": True, "message": f"Focused '{w.window_text()}'.", "data": {"title": w.window_text()}}
        except Exception as e:
            return {"success": False, "message": f"Couldn't focus '{title}': {e}", "data": {}}

    # ── Read a window's visible text ───────────────────────────────────────
    def get_window_text(self, title: str, max_chars: int = 2000) -> dict:
        if not title:
            return {"success": False, "message": "Which window?", "data": {}}
        try:
            w = self._find(title)
            if not w:
                return {"success": False, "message": f"No window matching '{title}'.", "data": {}}
            texts = []
            for d in w.descendants():
                try:
                    t = d.window_text().strip()
                    if t and t not in texts:
                        texts.append(t)
                except Exception:
                    continue
            blob = "\n".join(texts)[:max_chars]
            if not blob.strip():
                return {"success": True, "message": f"'{w.window_text()}' has no readable text.", "data": {}}
            return {"success": True, "message": blob, "data": {"title": w.window_text(), "chars": len(blob)}}
        except Exception as e:
            return {"success": False, "message": f"Couldn't read '{title}': {e}", "data": {}}

    # ── Type text into the focused window ──────────────────────────────────
    def type_text(self, text: str) -> dict:
        if not text:
            return {"success": False, "message": "Nothing to type.", "data": {}}
        try:
            from pywinauto.keyboard import send_keys
            # escape pywinauto special chars so plain text types literally
            safe = text.replace("{", "{{").replace("}", "}}")
            for ch in "+^%~()[]":
                safe = safe.replace(ch, "{" + ch + "}")
            send_keys(safe, with_spaces=True, pause=0.01)
            return {"success": True, "message": f"Typed {len(text)} characters.", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Couldn't type: {e}", "data": {}}

    # ── Press a key combo (ctrl+s, alt+f4, enter...) ───────────────────────
    def press_keys(self, keys: str) -> dict:
        if not keys:
            return {"success": False, "message": "Which keys?", "data": {}}
        try:
            from pywinauto.keyboard import send_keys
            mod = {"ctrl": "^", "control": "^", "alt": "%", "shift": "+"}
            named = {"enter": "{ENTER}", "tab": "{TAB}", "esc": "{ESC}", "escape": "{ESC}",
                     "space": "{SPACE}", "backspace": "{BACKSPACE}", "delete": "{DELETE}",
                     "up": "{UP}", "down": "{DOWN}", "left": "{LEFT}", "right": "{RIGHT}",
                     "home": "{HOME}", "end": "{END}", "f4": "{F4}", "f5": "{F5}"}
            parts = re.split(r"[+\s]+", keys.lower().strip())
            seq = ""
            for p in parts:
                if p in mod:
                    seq += mod[p]
                elif p in named:
                    seq += named[p]
                else:
                    seq += p
            send_keys(seq)
            return {"success": True, "message": f"Pressed {keys}.", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Couldn't press '{keys}': {e}", "data": {}}

    # ── Launch an app ──────────────────────────────────────────────────────
    def launch_app(self, name: str) -> dict:
        if not name:
            return {"success": False, "message": "Which app?", "data": {}}
        shortcuts = {
            "notepad": "notepad", "calculator": "calc", "calc": "calc",
            "paint": "mspaint", "explorer": "explorer", "cmd": "cmd",
            "terminal": "wt", "task manager": "taskmgr", "settings": "ms-settings:",
            "vs code": "code", "vscode": "code", "code": "code", "chrome": "chrome",
            "edge": "msedge", "word": "winword", "excel": "excel",
        }
        cmd = shortcuts.get(name.lower().strip(), name.strip())
        try:
            os.startfile(cmd) if not cmd.endswith(":") else os.system(f"start {cmd}")
            return {"success": True, "message": f"Launching {name}.", "data": {"app": name}}
        except Exception:
            try:
                subprocess.Popen(cmd, shell=True)
                return {"success": True, "message": f"Launching {name}.", "data": {"app": name}}
            except Exception as e:
                return {"success": False, "message": f"Couldn't launch '{name}': {e}", "data": {}}

    # ── Click a named button within a window ───────────────────────────────
    def click_element(self, window: str, element: str) -> dict:
        if not window or not element:
            return {"success": False, "message": "Need a window and an element name.", "data": {}}
        try:
            w = self._find(window)
            if not w:
                return {"success": False, "message": f"No window matching '{window}'.", "data": {}}
            el_l = element.lower().strip()
            for d in w.descendants():
                try:
                    if el_l in d.window_text().strip().lower():
                        d.click_input()
                        return {"success": True, "message": f"Clicked '{d.window_text()}' in '{w.window_text()}'.", "data": {}}
                except Exception:
                    continue
            return {"success": False, "message": f"No element '{element}' found in '{window}'.", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Click failed: {e}", "data": {}}

    # ── Dispatch ───────────────────────────────────────────────────────────
    def run(self, input_text: str = "", action: str = None, parameters: dict = None) -> dict:
        parameters = parameters or {}
        try:
            if action == "list_windows":
                return self.list_windows()
            elif action == "focus_window":
                return self.focus_window(parameters.get("title", ""))
            elif action == "get_window_text":
                return self.get_window_text(parameters.get("title", ""))
            elif action == "type_text":
                return self.type_text(parameters.get("text", ""))
            elif action == "press_keys":
                return self.press_keys(parameters.get("keys", ""))
            elif action == "launch_app":
                return self.launch_app(parameters.get("name", parameters.get("app", "")))
            elif action == "click_element":
                return self.click_element(parameters.get("window", ""), parameters.get("element", ""))
            return {"success": False, "message": f"Unsupported terminator action: {action}", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Terminator error: {e}", "data": {}}


terminator_agent = TerminatorAgent()
