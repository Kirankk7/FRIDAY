import os
import datetime
import feedparser
import requests
from urllib.parse import quote_plus

from core.browser_agent import browser_agent
from core.llm import ask_llm
from core.critic import refine as _critic_refine

# Google News RSS — free, no key, supports search
_GNEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Finance-specific RSS feeds
_FINANCE_FEEDS = [
    "https://news.google.com/rss/search?q={query}+finance+market&hl=en-US&gl=US&ceid=US:en",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
]


class AthenaAgent:
    """
    Athena - Deep Research Agent

    Purpose:
    - Multi-source research (GitHub + News + Google)
    - LLM synthesis
    - Structured report generation
    - Auto-save to Desktop

    Commands:
    deep research <query>
    """

    # =====================================
    # FETCH NEWS (RSS — no API key)
    # =====================================
    def fetch_news(self, query: str) -> str:
        try:
            url = _GNEWS_RSS.format(query=quote_plus(query))
            feed = feedparser.parse(url)
            if not feed.entries:
                return ""
            combined = ""
            for entry in feed.entries[:6]:
                title = entry.get("title", "")
                desc = entry.get("summary", "")
                source = (
                    entry.get("source", {}).get("title", "")
                    if isinstance(entry.get("source"), dict) else ""
                )
                combined += f"[{source}] {title}. {desc}\n"
            return combined.strip()
        except Exception:
            return ""

    # =====================================
    # FETCH FINANCE NEWS (RSS)
    # =====================================
    def fetch_finance_news(self, query: str) -> str:
        try:
            url = _FINANCE_FEEDS[0].format(query=quote_plus(query))
            feed = feedparser.parse(url)
            if not feed.entries:
                # fallback to Reuters business feed
                feed = feedparser.parse(_FINANCE_FEEDS[1])
            combined = ""
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                desc = entry.get("summary", "")
                combined += f"{title}. {desc}\n"
            return combined.strip()
        except Exception:
            return ""

    # =====================================
    # GITHUB API (Phase 33) — direct REST, no browser
    # =====================================
    def _gh_headers(self) -> dict:
        h = {"Accept": "application/vnd.github+json", "User-Agent": "JARVIS-Athena/1.0"}
        try:
            from config import GITHUB_TOKEN
            if GITHUB_TOKEN:
                h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        except Exception:
            pass
        return h

    def github_repos(self, query: str, n: int = 5) -> dict:
        """Search GitHub repositories (works without token at 60/hr)."""
        if not query:
            return {"success": False, "message": "Search query missing.", "data": {}}
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": n},
                headers=self._gh_headers(), timeout=12,
            )
            if r.status_code == 403:
                return {"success": False, "message": "GitHub rate limit hit (60/hr without token). Set GITHUB_TOKEN for 5000/hr.", "data": {}}
            if r.status_code != 200:
                return {"success": False, "message": f"GitHub API error {r.status_code}.", "data": {}}
            items = r.json().get("items", [])
            if not items:
                return {"success": True, "message": f"No repos found for '{query}'.", "data": {}}
            lines = []
            for it in items[:n]:
                lines.append(f"{it['full_name']} ⭐{it['stargazers_count']:,} — {(it.get('description') or '')[:80]}")
            return {"success": True,
                    "message": f"Top GitHub repos for '{query}':\n" + "\n".join(lines),
                    "data": {"repos": [it["full_name"] for it in items]}}
        except Exception as e:
            return {"success": False, "message": f"GitHub repo search failed: {e}", "data": {}}

    def github_code(self, query: str, language: str = "", n: int = 5) -> dict:
        """Search GitHub code content (REQUIRES a token)."""
        if not query:
            return {"success": False, "message": "Search query missing.", "data": {}}
        try:
            from config import GITHUB_TOKEN
        except Exception:
            GITHUB_TOKEN = ""
        if not GITHUB_TOKEN:
            return {"success": False,
                    "message": "Code search needs a GitHub token. Set GITHUB_TOKEN in .env (github.com/settings/tokens).",
                    "data": {}}
        q = query + (f" language:{language}" if language else "")
        try:
            r = requests.get(
                "https://api.github.com/search/code",
                params={"q": q, "per_page": n}, headers=self._gh_headers(), timeout=12,
            )
            if r.status_code != 200:
                return {"success": False, "message": f"GitHub code search error {r.status_code}.", "data": {}}
            items = r.json().get("items", [])
            if not items:
                return {"success": True, "message": f"No code found for '{query}'.", "data": {}}
            lines = [f"{it['repository']['full_name']}: {it['path']}" for it in items[:n]]
            return {"success": True,
                    "message": f"Code matches for '{query}':\n" + "\n".join(lines),
                    "data": {"matches": lines}}
        except Exception as e:
            return {"success": False, "message": f"GitHub code search failed: {e}", "data": {}}

    def github_file(self, owner: str, repo: str, path: str) -> dict:
        """Read a file from a public GitHub repo."""
        if not (owner and repo and path):
            return {"success": False, "message": "Need owner, repo, and file path.", "data": {}}
        try:
            r = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                headers=self._gh_headers(), timeout=12,
            )
            if r.status_code == 404:
                return {"success": False, "message": f"File not found: {owner}/{repo}/{path}", "data": {}}
            if r.status_code != 200:
                return {"success": False, "message": f"GitHub API error {r.status_code}.", "data": {}}
            data = r.json()
            import base64
            content = base64.b64decode(data.get("content", "")).decode("utf-8", "replace")
            return {"success": True, "message": content[:4000],
                    "data": {"path": path, "size": data.get("size")}}
        except Exception as e:
            return {"success": False, "message": f"Couldn't read file: {e}", "data": {}}

    def _github_api_text(self, query: str) -> str:
        """Quick GitHub context for deep_research — top repos via API (no browser)."""
        r = self.github_repos(query, n=5)
        return r.get("message", "") if r.get("success") else ""

    # =====================================
    # FETCH GITHUB (legacy browser-based — kept for deep_research fallback)
    # =====================================
    def fetch_github(self, query: str) -> str:

        try:
            result = browser_agent.search_github(query)

            if not result.get("success"):
                return ""

            results = result.get("data", {}).get("results", [])

            if not results:
                return ""

            # Open top result + read README
            open_result = browser_agent.open_result(0)

            if not open_result.get("success"):
                return ""

            readme = browser_agent.read_readme()

            if readme.get("success"):
                return readme.get("message", "")

            # Fallback to page text
            page = browser_agent.get_page_text()
            return page.get("message", "")

        except Exception:
            return ""

    # =====================================
    # FETCH GOOGLE
    # =====================================
    def fetch_google(self, query: str) -> str:

        try:
            result = browser_agent.search_google(query)

            if not result.get("success"):
                return ""

            # Get page text from search results
            page = browser_agent.get_page_text()
            text = page.get("message", "")

            # Trim — just need snippets not full page
            return text[:2000]

        except Exception:
            return ""

    # =====================================
    # SAVE REPORT
    # =====================================
    def save_report(self, name: str, content: str) -> str:

        try:
            desktop = os.path.join(
                os.path.expanduser("~"),
                "Desktop"
            )

            date_str = datetime.datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            safe_name = (
                name.lower()
                .replace(" ", "_")
                .replace("/", "_")
                .replace(":", "")
            )

            filename = f"athena_{safe_name}_{date_str}.md"
            filepath = os.path.join(desktop, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return filepath

        except Exception:
            return None

    # =====================================
    # DEEP RESEARCH
    # =====================================
    def deep_research(self, query: str) -> dict:

        if not query:
            return {
                "success": False,
                "message": "No research query provided.",
                "data": {}
            }

        print(f"[ATHENA] Starting deep research: {query}")

        sources = {}

        # ── Source 1: News ──
        print("[ATHENA] Fetching news...")
        news_text = self.fetch_news(query)

        if news_text:
            sources["news"] = news_text
            print(f"[ATHENA] News: {len(news_text)} chars")
        else:
            print("[ATHENA] No news found.")

        # ── Source 1b: Finance News ──
        finance_keywords = ["stock", "market", "finance", "crypto", "invest", "economy", "etf", "fund"]
        if any(kw in query.lower() for kw in finance_keywords):
            print("[ATHENA] Fetching finance news...")
            finance_text = self.fetch_finance_news(query)
            if finance_text:
                sources["finance"] = finance_text
                print(f"[ATHENA] Finance: {len(finance_text)} chars")

        # ── Source 2: GitHub (direct API — no browser, Phase 33) ──
        print("[ATHENA] Fetching GitHub...")
        github_text = self._github_api_text(query)

        if github_text:
            sources["github"] = github_text
            print(f"[ATHENA] GitHub: {len(github_text)} chars")
        else:
            print("[ATHENA] No GitHub content.")

        # ── Source 3: Google ──
        print("[ATHENA] Fetching Google...")
        google_text = self.fetch_google(query)

        if google_text:
            sources["google"] = google_text
            print(f"[ATHENA] Google: {len(google_text)} chars")
        else:
            print("[ATHENA] No Google content.")

        if not sources:
            return {
                "success": False,
                "message": "Could not gather any sources.",
                "data": {}
            }

        # ── Build context for LLM ──
        context_block = f"Research Query: {query}\n\n"

        if "news" in sources:
            context_block += f"=== NEWS SOURCES ===\n{sources['news'][:1500]}\n\n"

        if "finance" in sources:
            context_block += f"=== FINANCE NEWS ===\n{sources['finance'][:1000]}\n\n"

        if "github" in sources:
            context_block += f"=== GITHUB / TECHNICAL ===\n{sources['github'][:2000]}\n\n"

        if "google" in sources:
            context_block += f"=== WEB SEARCH ===\n{sources['google'][:1000]}\n\n"

        # ── reasoning scratchpad (Phase 40a think(), now wired) ──
        from core.think import think
        plan = think(f"Plan a research report on: {query}",
                     context=context_block[:1200])
        plan_block = f"\nInternal plan (follow this):\n{plan}\n" if plan else ""

        # ── LLM synthesis ──
        print("[ATHENA] Synthesizing with LLM...")

        prompt = f"""You are Athena, an expert research analyst. Using the sources below, write a comprehensive research report.{plan_block}

{context_block}

Write a structured report with these sections:
1. Executive Summary
2. Key Findings
3. Technical Details
4. Current Landscape / Recent Developments
5. Implications / Use Cases
6. Conclusion

Write in clear English. No markdown headers with #. Use plain section labels. Be thorough and analytical.

Report:"""

        report_body = ask_llm(prompt, agent="athena")
        report_body = _critic_refine(query, report_body, agent="athena")  # Phase 57 (gated)

        if not report_body:
            return {
                "success": False,
                "message": "LLM failed to synthesize report.",
                "data": {}
            }

        # ── Build full report ──
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        sources_used = ", ".join(sources.keys())

        full_report = f"""# Athena Research Report: {query}

**Query:** {query}
**Sources:** {sources_used}
**Generated:** {date_str}

---

{report_body}

---
*Generated by JARVIS Athena Research Agent*
"""

        summary = report_body[:400] + "..." if len(report_body) > 400 else report_body

        # ── Save to EDITH memory ──
        try:
            from agents.edith.edith_agent import edith_agent
            edith_agent.store_memory(
                content=summary,
                label=query.lower().replace(" ", "_")[:40],
            )
        except Exception:
            pass

        # ── Save to Desktop ──
        saved_path = self.save_report(query, full_report)

        save_msg = (
            f"Report saved to Desktop: athena_{query.replace(' ', '_')}..."
            if saved_path
            else "Could not save report."
        )

        return {
            "success": True,
            "message": f"{summary}\n\n{save_msg}",
            "data": {
                "query": query,
                "sources_used": list(sources.keys()),
                "saved_path": saved_path,
                "full_report": full_report
            }
        }

    # =====================================
    # RUN
    # =====================================
    def run(
        self,
        input_text: str,
        action: str = None,
        parameters: dict = None
    ) -> dict:

        try:
            parameters = parameters or {}

            if not action:
                return {
                    "success": False,
                    "message": "No Athena action specified.",
                    "data": {}
                }

            if action == "deep_research":
                return self.deep_research(
                    parameters.get("query", input_text)
                )

            elif action == "github_repos":
                return self.github_repos(parameters.get("query", input_text), parameters.get("n", 5))

            elif action == "github_code":
                return self.github_code(parameters.get("query", input_text), parameters.get("language", ""))

            elif action == "github_file":
                return self.github_file(parameters.get("owner", ""), parameters.get("repo", ""), parameters.get("path", ""))

            return {
                "success": False,
                "message": f"Unsupported Athena action: {action}",
                "data": {}
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Athena agent error: {str(e)}",
                "data": {}
            }


athena_agent = AthenaAgent()
