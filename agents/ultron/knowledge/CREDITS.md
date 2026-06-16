# Knowledge Pack — sources & attribution

Ultron's bug-bounty/OSINT methodology notes and wordlists are vendored from these
public repositories for local, offline reference (RAG-indexed by `core/security_kb.py`).
All credit to the original authors.

**Notes (`notes/`)**
- Bug bounty playbooks/notes — github.com/hack-with-rohit/Bug_bounty_Notes
- OSINT resource list (`awesome_osint.md`) — github.com/jivoi/awesome-osint
- Tool catalog (`hacking_tools_catalog.md`) — (hacking-tools learning catalog)

**Wordlists / payloads (`wordlists/`)**
- ssrf / lfi / ssti / fuzz / permutations / headers — github.com/sidhusec/Rudrascan

To extend: drop more `.md`/`.txt` into `notes/` (e.g. SnailSploit/Claude-Red's
`Skills/*.md`), then run `python -c "from core import security_kb; security_kb.build_index()"`.

For educational / authorized security testing use only.
