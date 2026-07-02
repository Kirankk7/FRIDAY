"""
D — unified "find anything". One query fans out across friday tasks/notes/goals +
vector memory + edith memory + file-RAG docs. Each source graceful. Does NOT touch
the existing filename-only `find` router path (that fires only when a folder is set).
"""


def _match_items(items, q):
    out = []
    for it in items:
        text = it.get("text") if isinstance(it, dict) else str(it)
        if text and q in str(text).lower():
            out.append(str(text))
    return out


def find(query: str) -> dict:
    q = (query or "").strip().lower()
    if not q:
        return {"success": False, "message": "Find what, boss?", "data": {}}

    groups = {}

    def _safe(label, fn):
        try:
            hits = fn()
            if hits:
                groups[label] = hits[:5]
        except Exception:
            pass

    def _friday(kind):
        from agents.friday import friday_agent as fa
        data = fa._load()
        return _match_items(data.get(kind, []), q)

    _safe("Tasks", lambda: _friday("tasks"))
    _safe("Notes", lambda: _friday("notes"))
    _safe("Goals", lambda: _friday("goals"))

    def _mem():
        from core import vector_memory
        return [str(x) for x in vector_memory.search_similar(query, top_k=3) if q in str(x).lower()]
    _safe("Memory", _mem)

    def _edith():
        from agents.edith.edith_agent import edith_agent
        r = edith_agent.search_memory(query)
        d = r.get("data", {}) if isinstance(r, dict) else {}
        rows = d.get("results") or d.get("memories") or []
        return [str(x.get("content", x) if isinstance(x, dict) else x) for x in rows]
    _safe("Project memory", _edith)

    def _docs():
        from core import rag
        return [str(x.get("text", x) if isinstance(x, dict) else x)[:120] for x in rag.search(query, top_k=3)]
    _safe("Docs", _docs)

    if not groups:
        return {"success": True, "message": f"Nothing found for '{query}', boss.", "data": {}}

    lines = []
    for label, hits in groups.items():
        lines.append(f"{label}: " + "; ".join(h[:80] for h in hits))
    return {"success": True, "message": f"Found matches for '{query}':\n" + "\n".join(lines),
            "data": groups}
