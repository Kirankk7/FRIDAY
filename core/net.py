"""The single network chokepoint for target-facing code. P0, 2026-09-27.

Why this file exists
--------------------
`core/scope_guard.py` was written on 2026-09-17, tested, committed, and cited as
evidence that the engine was safe. On 2026-09-27 a measurement showed it had
**zero callers**: 26 network-capable modules, 12 of them target-facing, and not
one imported it. Existence is not enforcement (EVAL_SET C-10).

This module is deliberately THIN. It owns no scope logic, no redirect logic and
no header policy — all of that stays in `scope_guard`, which already had it
right. A second implementation of any of those is a second guard, and two
guards with similar names is exactly how `url_guard`/`scope_guard` drifted into
one being unused.

Contract
--------
1. FAIL CLOSED. Every entry point raises `ScopeError` when scope is missing,
   invalid, or unverifiable. There is no fallback to a raw request, ever.
2. Subprocesses are mediated too. `run_tool` validates the executable and every
   URL-shaped argument, and never uses a shell.
3. Direct `requests`/`urllib`/`socket` use in a target-facing module is a test
   failure, not a style comment. Exceptions are declared per CALL SITE in
   `core/net_exceptions.py` — never per module.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from core.scope_guard import Scope, ScopeGuard

__all__ = [
    "ScopeError",
    "configure",
    "is_configured",
    "current_scope",
    "get",
    "post",
    "run_tool",
    "ALLOWED_TOOLS",
]


from core.scope_guard import TransportError  # noqa: F401  re-exported for callers


class ScopeError(RuntimeError):
    """Raised when a request is denied, or attempted before scope is set.

    This is an exception and not a `None` return on purpose: a caller that
    ignores a return value would sail past a DENY, and the whole point of P0 is
    that bypassing the boundary must be loud.
    """


# Executables `run_tool` may launch. An unlisted binary is refused outright —
# the caller cannot smuggle one in via the argv it happens to build.
ALLOWED_TOOLS = frozenset({"mitmdump", "mitmproxy", "interactsh-client", "curl"})

# Anything that looks like a destination gets guarded, whether or not the caller
# remembered to declare it. Callers are not trusted to list their own targets.
_URLISH = re.compile(r"\bhttps?://[^\s'\"]+", re.I)

_GUARD: ScopeGuard | None = None


def configure(
    scope: Scope,
    audit_path: Path | None = None,
    run_id: str | None = None,
    max_redirects: int = 5,
) -> None:
    """Install the scope for this process. Call once, at hunt start."""
    global _GUARD
    if not isinstance(scope, Scope) or not scope.in_scope:
        raise ScopeError("refusing to configure: scope is empty or not a Scope")
    _GUARD = ScopeGuard(
        scope=scope, audit_path=audit_path, run_id=run_id, max_redirects=max_redirects
    )


def is_configured() -> bool:
    return _GUARD is not None


def current_scope() -> Scope:
    return _require().scope


def _require() -> ScopeGuard:
    if _GUARD is None:
        raise ScopeError(
            "no scope configured — call core.net.configure(Scope(...)) first. "
            "Failing closed rather than sending an unscoped request."
        )
    return _GUARD


def get(url: str, headers: dict[str, str] | None = None, timeout: float = 20.0,
        context=None):
    """Guarded GET. Returns (final_url, status, body, chain).

    Raises ScopeError on a scope DENY and TransportError when the request never
    completed. These must stay separate: a ScopeError means the BOUNDARY stopped
    us and is always worth stopping for, while a dead host is ordinary. When both
    raised ScopeError, the alarm fired for the ordinary case, and an alarm that
    fires for the ordinary case gets ignored.
    """
    g = _require()
    out = g.get(url, headers=headers, timeout=timeout, context=context)
    if out is None:
        raise ScopeError(f"DENY: {url}")
    return out


def post(
    url: str,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
):
    """Guarded POST. ScopeError on DENY, TransportError if it never completed."""
    g = _require()
    out = g.post(url, data=data, headers=headers, timeout=timeout)
    if out is None:
        raise ScopeError(f"DENY: {url}")
    return out


def run_tool(argv: list[str], timeout: float = 120.0, **kwargs):
    """Run an external tool with its destinations checked against scope.

    `argv` must be a list — a string would invite a shell, and `shell=True` is
    never used here. Every URL-shaped argument is guarded, so a caller cannot
    reach an out-of-scope host simply by not mentioning it.
    """
    g = _require()

    if isinstance(argv, str) or not argv:
        raise ScopeError("run_tool needs a non-empty argv LIST (a string implies a shell)")
    if kwargs.pop("shell", False):
        raise ScopeError("shell=True is not available at this boundary")

    exe = Path(str(argv[0])).name.lower()
    exe = exe[:-4] if exe.endswith(".exe") else exe
    if exe not in ALLOWED_TOOLS:
        raise ScopeError(
            f"executable not allowed: {argv[0]!r}. Add it to core.net.ALLOWED_TOOLS "
            f"with a reason if it is genuinely needed."
        )
    if shutil.which(str(argv[0])) is None and not Path(str(argv[0])).exists():
        raise ScopeError(f"executable not found: {argv[0]!r}")

    for arg in argv[1:]:
        for url in _URLISH.findall(str(arg)):
            d = g.check(url)
            if not d.allowed:
                raise ScopeError(f"tool argument out of scope: {url} ({d.reason})")
            if urlsplit(url).scheme.lower() not in ("http", "https"):
                raise ScopeError(f"tool argument scheme not allowed: {url}")

    return subprocess.run(argv, shell=False, timeout=timeout, **kwargs)
