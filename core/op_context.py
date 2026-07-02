"""
Deterministic follow-up state — a typed operation stack.

The last operation of each TYPE is remembered (translation, search, scan, …) plus
the single most-recent op overall. Follow-ups resolve against it WITHOUT the LLM:
  "now to spanish"  -> re-run the last translation with a new target
  "do it again"     -> re-dispatch the last operation verbatim
This is conversation *state*, not conversation memory — plumbing, zero model calls.

Recorded by the cognitive loop after each tool runs; read by the router to resolve
a follow-up into a concrete {tool, action, parameters} decision.
"""
import time

_ops = {}     # op_type -> op dict
_last = None  # most-recent op overall


def record(op_type: str, tool: str, action: str, parameters: dict, result=None) -> None:
    global _last
    op = {
        "type": op_type, "tool": tool, "action": action,
        "parameters": dict(parameters or {}), "result": result, "ts": time.time(),
    }
    _ops[op_type] = op
    _last = op


def last(op_type: str = None, max_age: float = 300.0):
    """Most-recent op (of a type, or overall) if it's fresh enough — else None.
    Staleness guard stops a 10-minutes-ago translate from hijacking a bare word."""
    op = _ops.get(op_type) if op_type else _last
    if not op:
        return None
    if max_age and (time.time() - op.get("ts", 0)) > max_age:
        return None
    return op


def clear() -> None:
    global _last
    _ops.clear()
    _last = None
