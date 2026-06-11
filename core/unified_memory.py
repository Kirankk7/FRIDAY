"""
Phase 52 #2 — Unified memory facade.

One read interface over the project's fragmented stores:
  · vector_memory   — TF-IDF similarity over conversation text
  · edith           — project / long-term notes
  · tool_memory     — recent tool-result ring buffer
  · personal_memory — user facts/profile

Callers get a single search() across all of them (source-tagged, deduped) and
context() — a prompt-injection-ready string. Writes still go to the specific
store that owns the data; this facade is deliberately read-first to avoid
duplicating the same fact into four places.
"""


def search(query: str, per_source: int = 3) -> dict:
    """Aggregate matches across all memory stores. Returns source-tagged results."""
    q = (query or "").strip()
    results = []
    if not q:
        return {"query": q, "count": 0, "results": []}

    # ── vector (conversation similarity) ──
    try:
        from core.vector_memory import search_similar
        for text in search_similar(q, top_k=per_source):
            results.append({"source": "vector", "text": text})
    except Exception:
        pass

    # ── edith (project memory) ──
    try:
        from agents.edith.edith_agent import edith_agent
        r = edith_agent.search_memory(q)
        if r.get("success"):
            for item in (r.get("data", {}).get("results", []) or [])[:per_source]:
                txt = item.get("content") if isinstance(item, dict) else str(item)
                if txt:
                    results.append({"source": "edith", "text": txt})
    except Exception:
        pass

    # ── tool results ──
    try:
        from core.tool_memory import search_results
        for item in (search_results(q) or [])[:per_source]:
            msg = item.get("message") if isinstance(item, dict) else str(item)
            tool = item.get("tool", "") if isinstance(item, dict) else ""
            if msg:
                results.append({"source": "tool", "text": f"[{tool}] {msg}"})
    except Exception:
        pass

    # ── personal facts ──
    try:
        from core.personal_memory import get_relevant_context
        ctx = get_relevant_context(q)
        if ctx and ctx.strip():
            results.append({"source": "personal", "text": ctx.strip()})
    except Exception:
        pass

    # dedupe on text, keep first (source order = priority)
    seen, deduped = set(), []
    for r in results:
        key = r["text"][:120]
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return {"query": q, "count": len(deduped), "results": deduped}


def context(query: str, limit: int = 6) -> str:
    """Prompt-ready context block aggregated from every store. '' if nothing."""
    hits = search(query)["results"][:limit]
    if not hits:
        return ""
    lines = [f"- ({h['source']}) {h['text']}" for h in hits]
    return "Relevant memory:\n" + "\n".join(lines)


def stores() -> list:
    """Which backing stores the facade currently spans."""
    return ["vector", "edith", "tool", "personal"]
