#!/usr/bin/env python
"""
JARVIS onboarding / doctor — run `python scripts/setup.py` after cloning.

Checks the environment and tells you exactly what to fix. Read-only by default;
pass --fix to create .env from .env.example. ASCII-only output (Windows cp1252).
"""
import os
import sys
import shutil
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OK, WARN, BAD = "[ OK ]", "[WARN]", "[FAIL]"
_issues = []


def check(label, ok, detail="", fatal=False):
    tag = OK if ok else (BAD if fatal else WARN)
    print(f"  {tag} {label}" + (f" - {detail}" if detail else ""))
    if not ok:
        _issues.append((fatal, label, detail))


def _py():
    v = sys.version_info
    check(f"Python {v.major}.{v.minor}", v >= (3, 10),
          "need 3.10+ (3.12 recommended)", fatal=v < (3, 10))


def _reqs():
    need = ["flask", "requests", "bs4", "dotenv", "psutil"]
    missing = []
    for m in need:
        try:
            __import__(m)
        except Exception:
            missing.append(m)
    check("core Python deps importable", not missing,
          f"missing: {', '.join(missing)} -> pip install -r requirements.txt" if missing else "")


def _ollama():
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=4) as r:
            import json
            tags = [m["name"] for m in json.loads(r.read()).get("models", [])]
        check("Ollama running", True, host)
        has = any(model.split(":")[0] in t for t in tags)
        check(f"model '{model}' pulled", has,
              f"run: ollama pull {model}" if not has else "", fatal=not has)
    except Exception:
        check("Ollama running", False, f"start Ollama, then `ollama pull {model}`", fatal=True)


def _tools():
    # offensive tools are optional (native recon); note what's present
    for t in ["nmap", "httpx", "subfinder", "nuclei", "ffuf"]:
        check(f"recon tool: {t}", shutil.which(t) is not None,
              "optional (Go install) - native recon needs it")


def _playwright():
    try:
        import playwright  # noqa: F401
        check("playwright installed", True, "browser + spa_crawl ready")
    except Exception:
        check("playwright installed", False,
              "optional: pip install playwright && playwright install chromium")


def _env(fix):
    ex = os.path.join(ROOT, ".env.example")
    env = os.path.join(ROOT, ".env")
    if os.path.exists(env):
        check(".env present", True)
        return
    if fix and os.path.exists(ex):
        shutil.copy(ex, env)
        check(".env created from .env.example", True, "fill in optional keys")
    else:
        check(".env present", False,
              "run with --fix to create from .env.example (all keys optional)")


def main():
    fix = "--fix" in sys.argv
    print("\nJARVIS setup check\n" + "-" * 40)
    _py(); _reqs(); _ollama(); _tools(); _playwright(); _env(fix)
    print("-" * 40)
    fatals = [i for i in _issues if i[0]]
    if fatals:
        print(f"{len(fatals)} blocking issue(s) — fix the [FAIL] lines above, then re-run.")
        sys.exit(1)
    warns = len(_issues)
    print("Ready to run: python app.py" if not warns
          else f"Runnable. {warns} optional item(s) above are nice-to-have, not required.")


if __name__ == "__main__":
    main()
