import os
import datetime
import feedparser
import requests
from urllib.parse import quote_plus

from core.browser_agent import browser_agent
from core.llm import ask_llm

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
    # FETCH GITHUB
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

        # ── Source 2: GitHub ──
        print("[ATHENA] Fetching GitHub...")
        github_text = self.fetch_github(query)

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

        # ── LLM synthesis ──
        print("[ATHENA] Synthesizing with LLM...")

        prompt = f"""You are Athena, an expert research analyst. Using the sources below, write a comprehensive research report.

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

        report_body = ask_llm(prompt)

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

        # ── Save to EDITH memory ──
        try:
            from agents.edith.edith_agent import edith_agent
            edith_agent.store_memory(
                content=summary,
                label=query.lower().replace(" ", "_")[:40],
                memory_type="research"
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

        summary = report_body[:400] + "..." if len(report_body) > 400 else report_body

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
