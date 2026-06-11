import json
import os
import datetime
import uuid

MEMORY_DB = "data/edith_memory.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(MEMORY_DB):
    with open(MEMORY_DB, "w", encoding="utf-8") as f:
        json.dump([], f)

MAX_ENTRIES = 200


class EdithAgent:
    """
    EDITH — Long-term Project Memory Agent.
    Stores labeled notes, research summaries, and conversation context.
    Format: [{id, label, content, type, timestamp}, ...]
    """

    def _load(self) -> list:
        try:
            with open(MEMORY_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, data: list):
        try:
            with open(MEMORY_DB, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[edith] Save error: {e}")

    def store_memory(self, content: str, label: str = None, memory_type: str = "note") -> dict:
        if not content or not content.strip():
            return {"success": False, "message": "Nothing to remember.", "data": {}}

        data = self._load()
        entry = {
            "id": str(uuid.uuid4())[:8],
            "label": label.strip().lower() if label else None,
            "content": content.strip(),
            "type": memory_type,
            "timestamp": datetime.datetime.now().isoformat()
        }
        data.append(entry)
        if len(data) > MAX_ENTRIES:
            data = data[-MAX_ENTRIES:]
        self._save(data)

        label_str = f' as "{label}"' if label else ""
        return {
            "success": True,
            "message": f"Locked in{label_str}, boss.",
            "data": {"entry": entry}
        }

    def search_memory(self, query: str) -> dict:
        if not query:
            return {"success": False, "message": "No search query.", "data": {}}

        data = self._load()
        if not data:
            return {
                "success": True,
                "message": "Memory is empty, boss. Nothing stored yet.",
                "data": {"results": []}
            }

        keywords = query.lower().split()
        scored = []
        for entry in data:
            text = (entry.get("content", "") + " " + (entry.get("label") or "")).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [e for _, e in scored[:5]]

        if not results:
            return {
                "success": True,
                "message": f"Nothing in memory about '{query}', boss.",
                "data": {"results": []}
            }

        lines = []
        for e in results:
            label_str = f'[{e["label"]}] ' if e.get("label") else ""
            ts = e.get("timestamp", "")[:10]
            lines.append(f"{label_str}{e['content'][:300]} ({ts})")

        return {
            "success": True,
            "message": "\n\n".join(lines),
            "data": {"results": results, "count": len(results)}
        }

    def get_by_label(self, label: str) -> dict:
        if not label:
            return {"success": False, "message": "No label given.", "data": {}}

        data = self._load()
        label_lower = label.strip().lower()

        # Exact match first
        matches = [e for e in data if e.get("label") == label_lower]
        # Fuzzy fallback — contains
        if not matches:
            matches = [e for e in data if e.get("label") and label_lower in e["label"]]

        if not matches:
            return {
                "success": True,
                "message": f"Nothing stored under '{label}', boss.",
                "data": {}
            }

        latest = matches[-1]
        return {
            "success": True,
            "message": latest["content"],
            "data": {"entry": latest}
        }

    def recall_recent(self, n: int = 5) -> dict:
        data = self._load()
        if not data:
            return {"success": True, "message": "Memory is empty.", "data": {"memories": []}}

        recent = data[-n:]
        lines = []
        for e in recent:
            label_str = f'[{e["label"]}] ' if e.get("label") else ""
            ts = e.get("timestamp", "")[:10]
            lines.append(f"{label_str}{e['content'][:200]} ({ts})")

        return {
            "success": True,
            "message": "\n\n".join(lines),
            "data": {"memories": recent}
        }

    def run(self, input_text: str, action: str = None, parameters: dict = None) -> dict:
        try:
            parameters = parameters or {}
            if not action:
                return {"success": False, "message": "No EDITH action specified.", "data": {}}

            if action == "store_memory":
                return self.store_memory(
                    content=parameters.get("content", input_text),
                    label=parameters.get("label"),
                    memory_type=parameters.get("type", "note")
                )
            elif action == "search_memory":
                return self.search_memory(parameters.get("query", input_text))
            elif action == "get_by_label":
                return self.get_by_label(parameters.get("label", ""))
            elif action == "recall_memory":
                return self.recall_recent(parameters.get("n", 5))

            return {"success": False, "message": f"Unsupported EDITH action: {action}", "data": {}}

        except Exception as e:
            return {"success": False, "message": f"EDITH error: {str(e)}", "data": {}}


edith_agent = EdithAgent()
