"""Per-CALL-SITE exceptions to the network boundary. P0, 2026-09-27.

Read this before adding an entry.

A module is never exempt. Each entry authorises ONE call site and must carry a
justification, an owner and the destination it is allowed to reach. Blanket
module exemptions were rejected during design: they are a bypass around the
control being built.

The classification that matters is the DESTINATION, not the module name. An
earlier pass labelled 12 modules "target-facing" from their names and was wrong
— nine of them talk to Ollama on localhost, a local Burp bridge, the GitHub
API, threat-intel providers or an OAST listener. None of those is the target,
and routing them through a target scope would only break them.

Only three call sites can reach a bug-bounty target, and those are the ones the
boundary exists for. They are NOT in this file — they go through `core.net`.
"""

from __future__ import annotations

# key: "<path>::<symbol-or-line-hint>"
# value: (destination, justification, owner)
EXCEPTIONS: dict[str, tuple[str, str, str]] = {
    "core/autonomous.py::_ollama_generate": (
        "http://localhost:11434",
        "Local Ollama inference. Never leaves the machine; not a target destination.",
        "kiran",
    ),
    "core/planner.py::_ollama_generate": (
        "http://localhost:11434",
        "Local Ollama inference. Never leaves the machine; not a target destination.",
        "kiran",
    ),
    "core/tools.py::_ollama_generate": (
        "http://localhost:11434",
        "Local Ollama inference. Never leaves the machine; not a target destination.",
        "kiran",
    ),
    "core/burp_ingest.py::BURP_MCP_URL": (
        "local Burp MCP bridge",
        "Reads OUR OWN proxy's captured traffic. Local bridge, not a target fetch.",
        "kiran",
    ),
    "core/github_hunt.py::api.github.com": (
        "https://api.github.com",
        "GitHub code search on target IDENTIFIERS. The destination is GitHub, a "
        "third party we are a normal API consumer of — never the target's hosts.",
        "kiran",
    ),
    "core/threat_intel.py::_intel_fetch": (
        "abuseipdb / otx.alienvault / isc.sans",
        "Third-party intel lookups ABOUT an indicator. Passive, and the target is "
        "the subject of the query, not the destination of the request.",
        "kiran",
    ),
    "core/oast.py::listener": (
        "interactsh provider + 127.0.0.1 local listener",
        "OAST infrastructure. The target reaches US here; we do not reach the target. "
        "core/oast.py must never fall back to loopback for a real OOB test.",
        "kiran",
    ),
    "core/scope_guard.py::request": (
        "whatever the guarded scope allows",
        "THIS IS THE GUARD. Its urllib/socket use is the implementation of the "
        "boundary itself and cannot route through the adapter that wraps it.",
        "kiran",
    ),
    "core/url_guard.py::fetch": (
        "news / docs / research URLs",
        "The SSRF guard for NON-security fetches, explicitly marked 'do NOT apply "
        "to the security agent'. Different product surface, different threat model. "
        "Kept separate deliberately — merging the two guards is not a casual change.",
        "kiran",
    ),
}

# Modules whose target-reaching calls MUST go through core.net. Not exceptions —
# the opposite: this is the list the static test holds to the boundary.
TARGET_FACING = (
    "core/takeover.py",
    "core/live_capture.py",
    "scripts/vdp_sweep.py",
)
