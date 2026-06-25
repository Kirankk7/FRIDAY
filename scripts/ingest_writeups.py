#!/usr/bin/env python
"""
Seed the playbook from public, content-first methodology writeups (Option A).

Source: KathanP19/HowToHunt — per-class bug-bounty methodology in raw markdown
(no JS, no bot-block, no ToS scrape problem, unlike HackerOne report pages). Each
file is full technique text → ingest_writeup distils it into data/playbook.json
(gitignored, local) with source="writeup", verify=True.

Re-runnable: playbook.add novelty-dedups, so repeat runs only add what's new.
Usage:  python scripts/ingest_writeups.py
"""
import os, sys, time
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.ultron.ultron_agent import ultron_agent as U
from core import playbook as pb

RAW = "https://raw.githubusercontent.com/KathanP19/HowToHunt/master/"

# one or two primary methodology files per class we carry in the playbook
PATHS = [
    "API_Testing/Reverse_Engineer_an_API.md",
    "Account_Takeovers_Methodologies/Account_Takeovers_Methods.md",
    "Authentication_Bypass/2FA_Bypasses.md",
    "CORS/CORS.md",
    "CORS/CORS_Bypasses.md",
    "CSRF/CSRF.md",
    "File_Upload/file_upload.md",
    "GraphQL/GraphQL.md",
    "Host-Header/Host-Header.md",
    "HTTP_Desync/http_desync.md",
    "IDOR/IDOR.md",
    "JWT/JWT.md",
    "OAuth/OAuth 2.0 Hunting Methodology.md",
    "Open_Redirection/Open_Redirection_Bypass.md",
    "Parameter_Pollution/Parameter_Pollution_in_social_sharing_buttons.md",
    "Password_Reset_Functionality/Top_5_Password_Reset_Bugs.md",
    "Race_Condition/race_conditions.md",
    "SQLi/SQL_Injection.md",
    "SSRF/SSRF.md",
    "SSRF/Blind_SSRF.md",
    "SSTI/SSTI.md",
    "Subdomain_Takeover/Sub_or_top_level_domain_takeover.md",
    "XSS/XSS_Bypass.md",
]


def main():
    before = pb.stats()["total"]
    total_added = ok = 0
    for i, p in enumerate(PATHS, 1):
        url = RAW + quote(p)
        try:
            r = U.ingest_writeup(url)
        except Exception as e:
            print(f"[{i:2}/{len(PATHS)}] ERR {p}: {str(e)[:60]}")
            continue
        d = r.get("data", {})
        added = d.get("added", 0)
        if r.get("success") and added is not None:
            ok += 1
            total_added += added or 0
            print(f"[{i:2}/{len(PATHS)}] +{added or 0:2}  {p}")
        else:
            print(f"[{i:2}/{len(PATHS)}] --  {p}  ({r.get('message','')[:50]})")
        time.sleep(1.0)        # be polite to raw.githubusercontent
    s = pb.stats()
    print(f"\nDONE: {ok}/{len(PATHS)} pages ingested, +{total_added} techniques.")
    print(f"PLAYBOOK: {before} -> {s['total']} | validated {s['validated']} | "
          f"verify {s['verify_needed']} | classes {s['classes']}")


if __name__ == "__main__":
    main()
