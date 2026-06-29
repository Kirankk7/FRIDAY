#!/usr/bin/env python
"""Local dogfood target roster — reachability check + start-commands.

Quick "what's up, what should I start" for the dogfood targets used by chat
battery (Flask on :5000), security pipeline (probe_lab / DVWA / Juice Shop),
and the LLM (Ollama). Read-only.

Run:  python scripts/roster.py
"""
import os, sys, urllib.request

TARGETS = [
    ("JARVIS app (Flask)", "http://127.0.0.1:5000/health",
     "python app.py", "live-server chat_battery, /chat_stream"),
    ("Ollama LLM",         "http://127.0.0.1:11434/api/tags",
     "ollama serve  (then ensure qwen2.5:7b)", "all LLM-routed inputs + autotune + critic"),
    ("probe_lab (TP/FP)",  "http://127.0.0.1:7000/",
     "python labs/probe_lab/app.py", "scripts/dogfood.py security bench"),
    ("OWASP Juice Shop",   "http://127.0.0.1:3000/",
     "node build/app.js (in juice-shop repo)", "Cycle-2 R1-R10 SPA+API hunts"),
    ("DVWA (PHP+MariaDB)", "http://127.0.0.1:8080/",
     "bash scripts/dvwa_setup.sh  (WSL2)", "classic SQLi/XSS/LFI/CSRF"),
    ("OWASP WebGoat",      "http://127.0.0.1:8081/WebGoat/",
     "java -jar webgoat.jar (port 8081)", "IDOR/deserialization labs"),
]


def reach(url, timeout=2):
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def main():
    print(f"\n=== JARVIS dogfood target roster ===\n")
    up = 0
    for name, url, start, why in TARGETS:
        ok = reach(url)
        if ok:
            up += 1
        mark = "UP  " if ok else "down"
        print(f"  [{mark}] {name:24} {url}")
        if not ok:
            print(f"          start:  {start}")
            print(f"          for:    {why}")
    print(f"\n{up}/{len(TARGETS)} reachable")
    sys.exit(0 if up else 2)


if __name__ == "__main__":
    main()
