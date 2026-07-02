import os
import json
import uuid
import sqlite3
import datetime

# Phase 34 — EDITH long-term memory migrated JSON -> SQLite.
# Same public API + return shapes; durable, indexed, no full-file rewrites.
os.makedirs("data", exist_ok=True)
DB_PATH = "data/edith_memory.db"
LEGACY_JSON = "data/edith_memory.json"
MAX_ENTRIES = 200


class EdithAgent:
    """
    EDITH — Long-term Project Memory Agent (SQLite-backed).
    Stores labeled notes, research summaries, and conversation context.
    Row: (id, label, content, type, timestamp)
    """

    def __init__(self):
        self._init_db()
        self._migrate_legacy_json()

    # ── storage ──
    def _conn(self):
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        try:
            with self._conn() as c:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id        TEXT PRIMARY KEY,
                        label     TEXT,
                        content   TEXT NOT NULL,
                        type      TEXT DEFAULT 'note',
                        timestamp TEXT NOT NULL
                    )
                """)
                c.execute("CREATE INDEX IF NOT EXISTS idx_label ON memories(label)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_ts ON memories(timestamp)")
        except Exception as e:
            print(f"[edith] DB init error: {e}")

    def _migrate_legacy_json(self):
        """One-time import of the old JSON store, if present and DB is empty."""
        try:
            if not os.path.exists(LEGACY_JSON):
                return
            with self._conn() as c:
                if c.execute("SELECT COUNT(*) FROM memories").fetchone()[0] > 0:
                    return  # already populated
                with open(LEGACY_JSON, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                for e in rows:
                    c.execute(
                        "INSERT OR IGNORE INTO memories VALUES (?,?,?,?,?)",
                        (e.get("id") or str(uuid.uuid4())[:8], e.get("label"),
                         e.get("content", ""), e.get("type", "note"),
                         e.get("timestamp", datetime.datetime.now().isoformat())),
                    )
            os.replace(LEGACY_JSON, LEGACY_JSON + ".migrated")
            print(f"[edith] migrated {len(rows)} entries JSON -> SQLite")
        except Exception as e:
            print(f"[edith] legacy migration skipped: {e}")

    def _prune(self, c):
        """Keep only the newest MAX_ENTRIES rows."""
        c.execute("""
            DELETE FROM memories WHERE id NOT IN (
                SELECT id FROM memories ORDER BY timestamp DESC LIMIT ?
            )
        """, (MAX_ENTRIES,))

    def _row(self, r) -> dict:
        return {"id": r["id"], "label": r["label"], "content": r["content"],
                "type": r["type"], "timestamp": r["timestamp"]}

    # ── public API (unchanged shapes) ──
    def store_memory(self, content: str, label: str = None, memory_type: str = "note") -> dict:
        if not content or not content.strip():
            return {"success": False, "message": "Nothing to remember.", "data": {}}

        entry = {
            "id": str(uuid.uuid4())[:8],
            "label": label.strip().lower() if label else None,
            "content": content.strip(),
            "type": memory_type,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        try:
            with self._conn() as c:
                c.execute("INSERT INTO memories VALUES (?,?,?,?,?)",
                          (entry["id"], entry["label"], entry["content"],
                           entry["type"], entry["timestamp"]))
                self._prune(c)
        except Exception as e:
            return {"success": False, "message": f"EDITH save error: {e}", "data": {}}

        label_str = f' as "{label}"' if label else ""
        preview = content.strip()
        if len(preview) > 60:
            preview = preview[:57] + "..."
        return {"success": True,
                "message": f"Locked in{label_str}, boss: {preview}",
                "data": {"entry": entry}}

    def search_memory(self, query: str) -> dict:
        if not query:
            return {"success": False, "message": "No search query.", "data": {}}

        try:
            with self._conn() as c:
                rows = [self._row(r) for r in
                        c.execute("SELECT * FROM memories").fetchall()]
        except Exception as e:
            return {"success": False, "message": f"EDITH search error: {e}", "data": {}}

        if not rows:
            return {"success": True, "message": "Memory is empty, boss. Nothing stored yet.",
                    "data": {"results": []}}

        keywords = query.lower().split()
        scored = []
        for e in rows:
            text = (e["content"] + " " + (e["label"] or "")).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [e for _, e in scored[:5]]

        if not results:
            return {"success": True, "message": f"Nothing in memory about '{query}', boss.",
                    "data": {"results": []}}

        lines = []
        for e in results:
            label_str = f"{e['label'].replace('_', ' ')}: " if e.get("label") else ""
            snippet = " ".join((e["content"] or "").split())[:130]
            lines.append(f"  • {label_str}{snippet}")
        n = len(results)
        opener = "Here's what I've got" if n > 1 else "One thing I remember"
        return {"success": True,
                "message": f"{opener} on '{query}':\n" + "\n".join(lines),
                "data": {"results": results, "count": n}}

    def get_by_label(self, label: str) -> dict:
        if not label:
            return {"success": False, "message": "No label given.", "data": {}}
        ll = label.strip().lower()
        try:
            with self._conn() as c:
                exact = c.execute(
                    "SELECT * FROM memories WHERE label=? ORDER BY timestamp DESC LIMIT 1",
                    (ll,)).fetchone()
                row = exact or c.execute(
                    "SELECT * FROM memories WHERE label LIKE ? ORDER BY timestamp DESC LIMIT 1",
                    (f"%{ll}%",)).fetchone()
        except Exception as e:
            return {"success": False, "message": f"EDITH error: {e}", "data": {}}

        if not row:
            return {"success": True, "message": f"Nothing stored under '{label}', boss.", "data": {}}
        entry = self._row(row)
        return {"success": True, "message": entry["content"], "data": {"entry": entry}}

    def recall_recent(self, n: int = 5) -> dict:
        try:
            with self._conn() as c:
                rows = [self._row(r) for r in c.execute(
                    "SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?", (n,)).fetchall()]
        except Exception as e:
            return {"success": False, "message": f"EDITH error: {e}", "data": {}}

        if not rows:
            return {"success": True, "message": "Memory is empty.", "data": {"memories": []}}
        rows = rows[::-1]  # chronological, matching old behavior
        lines = []
        for e in rows:
            label_str = f"({e['label']}) " if e.get("label") else ""
            ts = (e.get("timestamp") or "")[:10]
            lines.append(f"  - {label_str}{e['content'][:200]} ({ts})")
        return {"success": True,
                "message": f"Last {len(rows)} memory entries:\n" + "\n".join(lines),
                "data": {"memories": rows}}

    def run(self, input_text: str, action: str = None, parameters: dict = None) -> dict:
        try:
            parameters = parameters or {}
            if not action:
                return {"success": False, "message": "No EDITH action specified.", "data": {}}

            if action == "store_memory":
                return self.store_memory(
                    content=parameters.get("content", input_text),
                    label=parameters.get("label"),
                    memory_type=parameters.get("type", "note"))
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
