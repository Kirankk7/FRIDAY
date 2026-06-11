"""
Phase 52 #4 - Startup config validator.

Boot-time sanity check: surfaces missing keys, unreachable Ollama, absent
security tools, and backend gaps - loudly, once, instead of failing silently
mid-request. Never raises; returns a structured report and prints a summary.

Call validate(print_summary=True) once at app boot.
"""

import os
import shutil

# Optional API keys -> the feature they unlock. Absent = graceful degrade (INFO).
_OPTIONAL_KEYS = {
    "NVD_API_KEY":        "CVE search faster quota (5->50 req/30s)",
    "VIRUSTOTAL_API_KEY": "VirusTotal file/url/domain reputation",
    "FOOTBALL_API_KEY":   "live football match data",
    "GITHUB_TOKEN":       "GitHub code search + 60->5000 req/hr",
}

# Security CLI tools Ultron's native fast-path uses (HackingTool fleet covers the rest).
_SECURITY_TOOLS = ["nmap", "subfinder", "httpx", "nuclei", "katana"]


def _ollama_status():
    try:
        import requests
        import config
        r = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code != 200:
            return False, False
        models = [m.get("name", "") for m in r.json().get("models", [])]
        return True, any(config.OLLAMA_MODEL in m for m in models)
    except Exception:
        return False, False


def _ht_backend():
    """What backend the HackingTool fleet will use (docker/wsl/native/none)."""
    try:
        if shutil.which("wsl"):
            return "wsl"
        if shutil.which("docker"):
            return "docker"
        if os.name != "nt":
            return "native"
    except Exception:
        pass
    return "none"


def validate(print_summary: bool = True) -> dict:
    """Run all checks. Returns {ok, errors, warnings, info}. Never raises."""
    import config
    errors, warnings, info = [], [], []

    # ── Ollama (the one true hard dependency) ──
    up, model_loaded = _ollama_status()
    if not up:
        errors.append(f"Ollama unreachable at {config.OLLAMA_HOST} - start it: `ollama serve`")
    elif not model_loaded:
        errors.append(f"Ollama up but model '{config.OLLAMA_MODEL}' not pulled - `ollama pull {config.OLLAMA_MODEL}`")
    else:
        info.append(f"Ollama OK - {config.OLLAMA_MODEL}")

    # ── per-agent model routing: warn if a mapped model isn't pulled ──
    try:
        mapped = getattr(config, "AGENT_MODELS", {}) or {}
        if mapped and up:
            import requests
            tags = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=3).json()
            have = [m.get("name", "") for m in tags.get("models", [])]
            for agent, mdl in mapped.items():
                if not any(mdl in h for h in have):
                    warnings.append(f"AGENT_MODELS['{agent}'] = '{mdl}' not pulled - falls back to {config.OLLAMA_MODEL}")
    except Exception:
        pass

    # ── optional API keys ──
    for key, feature in _OPTIONAL_KEYS.items():
        if not getattr(config, key, ""):
            info.append(f"no {key} - {feature} disabled (optional)")

    # ── security tools (native fast-path) ──
    missing_tools = [t for t in _SECURITY_TOOLS if not shutil.which(t)]
    if missing_tools:
        ht = _ht_backend()
        if ht == "none":
            warnings.append(f"security tools missing ({', '.join(missing_tools)}) and no Docker/WSL - Ultron recon limited")
        else:
            info.append(f"native tools missing ({', '.join(missing_tools)}) - HackingTool fleet will use {ht}")

    # ── backend / TTS sanity ──
    if getattr(config, "TTS_BACKEND", "") == "kokoro":
        info.append("TTS: kokoro (local)")
    if getattr(config, "AUTOTUNE_ENABLED", False):
        info.append("AutoTune: enabled")

    report = {"ok": not errors, "errors": errors, "warnings": warnings, "info": info}
    if print_summary:
        _print(report)
    return report


def _print(r: dict) -> None:
    line = "-" * 54
    print(f"\n{line}\n[config] startup validation")
    for e in r["errors"]:
        print(f"  [ERROR] {e}")
    for w in r["warnings"]:
        print(f"  [WARN]  {w}")
    for i in r["info"]:
        print(f"  - {i}")
    verdict = "READY" if r["ok"] else "DEGRADED - see errors above"
    print(f"[config] {verdict}\n{line}")
