import re
import requests
import feedparser
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

OLLAMA_URL = "http://localhost:11434/api/generate"

# Google News RSS — free, no API key, supports search queries
_GNEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Fallback general feeds (keyword filter applied)
_FEEDS = [
    "http://feeds.bbci.co.uk/news/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://feeds.reuters.com/reuters/topNews",
]


class VisionAgent:
    """
    Vision Agent — news search + summarize.
    Uses free RSS feeds. No API key required.
    """

    def __init__(self):
        self.articles = []

    def call_llm(self, prompt: str, max_tokens: int = 200) -> str:
        """Use configured OLLAMA_MODEL (qwen2.5:7b) — not hardcoded gemma:2b."""
        try:
            from config import OLLAMA_MODEL, OLLAMA_HOST
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.4,
                    "num_predict": max_tokens,
                },
                timeout=30,
            )
            return response.json().get("response", "").strip()
        except Exception:
            return ""

    # Keep old name as alias so summarize_news() still works
    def call_gemma(self, prompt: str) -> str:
        return self.call_llm(prompt, max_tokens=200)

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\*\*?", "", text)
        text = re.sub(r"- ", "", text)
        for junk in [
            "Sure, here's a summary of the news you provided:",
            "Sure, here's a summary:",
            "Here's what's happening:",
            "Here is the summary:",
            "Alright, here's what's going on.",
            "Let me break it down."
        ]:
            text = text.replace(junk, "")
        return text.strip()

    def _feedparser_safe(self, url: str, timeout_sec: int = 8):
        """feedparser.parse with a hard timeout (runs in thread)."""
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(feedparser.parse, url)
            try:
                return future.result(timeout=timeout_sec)
            except (FuturesTimeout, Exception):
                return type("Feed", (), {"entries": []})()

    def _fetch_google_news_rss(self, query: str) -> list:
        """Primary source — Google News RSS search. Returns up to 10 entries sorted by date."""
        try:
            url = _GNEWS_RSS.format(query=quote_plus(query))
            feed = self._feedparser_safe(url)
            articles = []
            for entry in feed.entries[:10]:
                articles.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", ""),
                    "source": entry.get("source", {}).get("title", "Google News") if isinstance(entry.get("source"), dict) else "Google News",
                    "published": entry.get("published", ""),
                })
            return articles
        except Exception:
            return []

    def _fetch_fallback_feeds(self, query: str) -> list:
        """Fallback — parse BBC/AJ/Reuters and filter by keyword."""
        keywords = query.lower().split()
        articles = []
        for feed_url in _FEEDS:
            try:
                feed = self._feedparser_safe(feed_url)
                for entry in feed.entries[:20]:
                    title = entry.get("title", "").lower()
                    summary = entry.get("summary", "").lower()
                    if any(kw in title or kw in summary for kw in keywords):
                        articles.append({
                            "title": entry.get("title", ""),
                            "description": entry.get("summary", ""),
                            "source": feed.feed.get("title", feed_url),
                        })
                if len(articles) >= 5:
                    break
            except Exception:
                continue
        return articles[:5]

    def search_news(self, query: str) -> dict:
        if not query:
            return {"success": False, "message": "Search query missing.", "data": {}}

        self.articles = self._fetch_google_news_rss(query)

        if not self.articles:
            self.articles = self._fetch_fallback_feeds(query)

        if not self.articles:
            return {"success": False, "message": "No news found.", "data": {}}

        headlines = [a.get("title", "") for a in self.articles]

        return {
            "success": True,
            "message": f"Found {len(self.articles)} news articles.",
            "data": {
                "query": query,
                "headlines": headlines,
                "article_count": len(self.articles),
            }
        }

    def summarize_news(self) -> dict:
        if not self.articles:
            return {"success": False, "message": "No articles to summarize.", "data": {}}

        combined = " ".join(
            a.get("title", "") + ". " + a.get("description", "") + ". "
            for a in self.articles
        )

        prompt = f"""Explain this news in simple spoken English.
STRICT: No introductions. No "Sure"/"Here's". No headings or bullets. Just explain directly.

Content:
{combined}

Answer:"""

        raw = self.call_gemma(prompt)
        cleaned = self.clean_text(raw)

        if not cleaned:
            return {"success": False, "message": "Couldn't generate a summary.", "data": {}}

        return {
            "success": True,
            "message": cleaned,
            "data": {"article_count": len(self.articles)}
        }

    def quick_answer(self, query: str) -> dict:
        """
        Fast factual lookup: RSS headlines only, no LLM call.
        Target: 1-3 seconds. Cognitive loop LLM handles spoken formatting.
        """
        if not query:
            return {"success": False, "message": "Query missing.", "data": {}}

        # Two parallel RSS searches for better coverage
        import datetime
        today_str = datetime.date.today().strftime("%B %Y")
        # First noun (likely team/person) — used for specific matchup articles
        _stopwords = {"when", "is", "are", "next", "the", "a", "an", "what", "will", "does", "did"}
        _words = [w for w in query.lower().split() if w not in _stopwords]
        subject = _words[0] if _words else query.split()[0]
        alt_query = f"{subject} match {today_str}"

        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(self._fetch_google_news_rss, query)
            f2 = ex.submit(self._fetch_google_news_rss, alt_query)
            arts1 = f1.result()
            arts2 = f2.result()

        # Merge, deduplicate by title, keep top 10
        seen = set()
        articles = []
        for a in arts1 + arts2:
            t = a.get("title", "")[:60]
            if t not in seen:
                seen.add(t)
                articles.append(a)
        articles = articles[:10]

        if not articles:
            articles = self._fetch_fallback_feeds(query)

        if not articles:
            return {
                "success": False,
                "message": f"I couldn't find recent news on '{query}'.",
                "data": {},
            }

        # Strip HTML entities and tags from all article text
        def _clean(s: str) -> str:
            s = re.sub(r"<[^>]+>", "", s)           # HTML tags
            s = re.sub(r"&nbsp;", " ", s)            # &nbsp;
            s = re.sub(r"&amp;", "&", s)
            s = re.sub(r"&lt;", "<", s)
            s = re.sub(r"&gt;", ">", s)
            s = re.sub(r"&#\d+;", "", s)             # numeric entities
            s = re.sub(r"\s+", " ", s).strip()
            return s

        import datetime
        today = datetime.date.today().strftime("%B %d, %Y")

        # Build clean headline list with publication dates
        context_lines = []
        for a in articles[:8]:
            title = _clean(a.get("title", ""))
            pub   = a.get("published", "").strip()
            line  = f"- {title}" + (f" ({pub})" if pub else "")
            context_lines.append(line)

        # Pack as __NEWS_CONTEXT__ block — cognitive_loop passes to LLM for spoken answer
        headline_block = "\n".join(context_lines)
        message = (
            f"__NEWS_CONTEXT__\nToday: {today}\nQuery: {query}\n"
            f"Headlines:\n{headline_block}"
        )

        return {
            "success": True,
            "message": message,
            "data": {"query": query, "sources": len(articles)},
        }

    def hackernews(self, n: int = 5) -> dict:
        """
        Phase 42 — Top N stories from Hacker News front page.
        Scrapes news.ycombinator.com — no API key needed.
        """
        try:
            import requests as _req
            from html.parser import HTMLParser

            r = _req.get("https://news.ycombinator.com/", timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return {"success": False, "message": f"HN fetch failed: HTTP {r.status_code}", "data": {}}

            # Parse titles from HN HTML (titleline spans)
            stories = []
            import re as _re
            # Match: <span class="titleline"><a href="...">TITLE</a>
            for m in _re.finditer(r'class="titleline"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', r.text):
                url, title = m.group(1), m.group(2)
                if title and title.strip():
                    stories.append({"title": title.strip(), "url": url})
                if len(stories) >= n:
                    break

            if not stories:
                return {"success": False, "message": "Could not parse HN stories.", "data": {}}

            lines = [f"{i+1}. {s['title']}" for i, s in enumerate(stories)]
            return {
                "success": True,
                "message": "Top Hacker News stories: " + " | ".join(lines),
                "data": {"stories": stories, "count": len(stories)}
            }
        except Exception as e:
            return {"success": False, "message": f"HackerNews error: {e}", "data": {}}

    def web_search(self, query: str, n: int = 5) -> dict:
        """
        Phase 32 — live web search via DuckDuckGo (ddgs). Free, no API key.
        Returns a __NEWS_CONTEXT__ block so cognitive_loop summarizes it for speech.
        """
        if not query:
            return {"success": False, "message": "Search query missing.", "data": {}}

        try:
            from ddgs import DDGS
        except ImportError:
            print("[vision] ddgs not installed — falling back to RSS quick_answer")
            return self.quick_answer(query)

        try:
            results = list(DDGS().text(query, max_results=n))
        except Exception as e:
            print(f"[vision] ddgs error ({e}) — falling back to RSS")
            return self.quick_answer(query)

        if not results:
            return self.quick_answer(query)

        import datetime
        today = datetime.date.today().strftime("%B %d, %Y")

        def _clean(s: str) -> str:
            s = re.sub(r"<[^>]+>", "", s or "")
            s = re.sub(r"\s+", " ", s).strip()
            return s

        lines = []
        for r in results[:n]:
            title = _clean(r.get("title", ""))
            body = _clean(r.get("body", ""))[:160]
            line = f"- {title}" + (f": {body}" if body else "")
            lines.append(line)

        message = (
            f"__NEWS_CONTEXT__\nToday: {today}\nQuery: {query}\n"
            f"Web results:\n" + "\n".join(lines)
        )
        return {
            "success": True,
            "message": message,
            "data": {"query": query, "results": len(results)},
        }

    def sports_query(self, query: str) -> dict:
        """
        Phase 39 — Real match data from football-data.org API.
        Falls back to quick_answer (RSS) if no API key or team not found.
        """
        try:
            from config import FOOTBALL_API_KEY
            from agents.vision.sports_api import get_next_match, get_recent_results, get_standings
        except ImportError:
            return self.quick_answer(query)

        if not FOOTBALL_API_KEY:
            print("[vision] FOOTBALL_API_KEY not set — falling back to RSS")
            return self.quick_answer(query)

        # Detect intent
        is_results = bool(re.search(
            r"\b(?:results?|scores?|recent|latest|last\s+match)\b", query, re.IGNORECASE
        ))
        is_standings = bool(re.search(r"\bstandings?\b", query, re.IGNORECASE))

        # Extract team/competition name — strip sports stopwords
        _stop = {
            "next", "match", "game", "fixture", "fixtures", "result", "results",
            "schedule", "football", "soccer", "playing", "play", "upcoming",
            "recent", "latest", "last", "standings", "when", "is", "are", "will",
            "does", "the", "a", "an", "vs", "against", "score", "scores",
            "who", "what", "their", "in"
        }
        words = query.lower().split()
        # Strip possessives: "portugal's" -> "portugal", "man's" -> "man"
        clean_words = [re.sub(r"'s?$", "", w) for w in words]
        name_words = [w for w in clean_words if w and w not in _stop]
        subject = " ".join(name_words).strip()

        if not subject:
            return self.quick_answer(query)

        print(f"[vision] sports_query: subject={subject!r} results={is_results} standings={is_standings}")

        if is_standings:
            result = get_standings(subject, FOOTBALL_API_KEY)
        elif is_results:
            result = get_recent_results(subject, FOOTBALL_API_KEY)
        else:
            result = get_next_match(subject, FOOTBALL_API_KEY)

        if not result["success"]:
            print(f"[vision] sports_api miss ({result['message']}) — falling back to RSS")
            return self.quick_answer(query)

        return {
            "success": True,
            "message": result["message"],
            "data": result.get("data", {})
        }

    # =====================================
    # PHASE 41 — NEW CAPABILITIES BATCH
    # =====================================
    def crypto_price(self, coins: str = "bitcoin") -> dict:
        """Live crypto prices via CoinGecko (free, no key)."""
        _alias = {
            "btc": "bitcoin", "eth": "ethereum", "bnb": "binancecoin",
            "sol": "solana", "xrp": "ripple", "ada": "cardano",
            "doge": "dogecoin", "dot": "polkadot", "matic": "matic-network",
            "ltc": "litecoin", "link": "chainlink", "avax": "avalanche-2",
        }
        ids = [_alias.get(c.strip().lower(), c.strip().lower())
               for c in re.split(r"[,\s]+", coins) if c.strip()]
        ids = ids[:8] or ["bitcoin"]
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ",".join(ids), "vs_currencies": "usd",
                        "include_24hr_change": "true"},
                timeout=10,
            )
            data = r.json()
            if not data:
                return {"success": False, "message": f"No price data for {coins}.", "data": {}}
            parts = []
            for cid, vals in data.items():
                price = vals.get("usd")
                chg = vals.get("usd_24h_change")
                chg_s = f" ({chg:+.1f}% 24h)" if isinstance(chg, (int, float)) else ""
                parts.append(f"{cid.replace('-', ' ').title()}: ${price:,}{chg_s}")
            return {"success": True, "message": " · ".join(parts), "data": data}
        except Exception as e:
            return {"success": False, "message": f"Crypto lookup failed: {e}", "data": {}}

    def currency_convert(self, amount: float, frm: str, to: str) -> dict:
        """Live FX conversion via open.er-api.com (free, no key)."""
        frm, to = frm.upper().strip(), to.upper().strip()
        try:
            r = requests.get(f"https://open.er-api.com/v6/latest/{frm}", timeout=10)
            data = r.json()
            if data.get("result") != "success":
                return {"success": False, "message": f"Unknown currency '{frm}'.", "data": {}}
            rate = data.get("rates", {}).get(to)
            if rate is None:
                return {"success": False, "message": f"Unknown currency '{to}'.", "data": {}}
            converted = amount * rate
            return {
                "success": True,
                "message": f"{amount:,.2f} {frm} = {converted:,.2f} {to} (rate {rate:.4f})",
                "data": {"amount": amount, "from": frm, "to": to, "rate": rate, "result": converted},
            }
        except Exception as e:
            return {"success": False, "message": f"Currency conversion failed: {e}", "data": {}}

    def translate(self, text: str, target: str = "en") -> dict:
        """Translate text via deep-translator (Google backend, no key)."""
        if not text:
            return {"success": False, "message": "Nothing to translate.", "data": {}}
        _lang = {
            "french": "fr", "spanish": "es", "german": "de", "italian": "it",
            "portuguese": "pt", "japanese": "ja", "chinese": "zh-CN", "korean": "ko",
            "russian": "ru", "arabic": "ar", "hindi": "hi", "english": "en",
            "dutch": "nl", "turkish": "tr", "tamil": "ta", "telugu": "te",
        }
        tgt = _lang.get(target.lower().strip(), target.lower().strip())
        try:
            from deep_translator import GoogleTranslator
            out = GoogleTranslator(source="auto", target=tgt).translate(text)
            if not out or not out.strip():
                return {"success": False,
                        "message": f"Couldn't translate '{text}' to {tgt} — got an empty result back.",
                        "data": {"target": tgt, "original": text}}
            return {"success": True,
                    "message": f"In {tgt}, that's: {out}",
                    "data": {"target": tgt, "original": text, "translation": out}}
        except Exception as e:
            msg = str(e)
            # deep-translator dumps the full 100+ supported-languages dict on any error.
            # Keep just the first line (the cause), drop the catalog after it.
            msg = msg.split("\n", 1)[0]
            if "supported languages" in msg.lower():
                msg = msg.rstrip(": .") + " (unsupported language code)"
            if len(msg) > 200:
                msg = msg[:200] + "..."
            return {"success": False, "message": f"Translation failed: {msg}", "data": {}}

    def track_flight(self, flight_no: str) -> dict:
        """Live flight tracking via FlightRadar24 (no key)."""
        if not flight_no:
            return {"success": False, "message": "Flight number missing.", "data": {}}
        flight_no = flight_no.upper().replace(" ", "")
        try:
            try:
                from flightradar24 import FlightRadar24API   # FlightRadarAPI >=1.5
            except ImportError:
                from FlightRadar24 import FlightRadar24API    # older versions
            api = FlightRadar24API()
            flights = api.get_flights()
            match = next((f for f in flights if getattr(f, "callsign", "") == flight_no
                          or getattr(f, "number", "") == flight_no), None)
            if not match:
                return {"success": False,
                        "message": f"Flight {flight_no} not currently airborne / not found.", "data": {}}
            details = (
                f"Flight {flight_no}: {getattr(match,'origin_airport_iata','?')} -> "
                f"{getattr(match,'destination_airport_iata','?')}, "
                f"alt {getattr(match,'altitude','?')}ft, "
                f"speed {getattr(match,'ground_speed','?')}kts, "
                f"heading {getattr(match,'heading','?')}°"
            )
            return {"success": True, "message": details, "data": {"flight": flight_no}}
        except Exception as e:
            return {"success": False, "message": f"Flight tracking failed: {e}", "data": {}}

    def run(self, input_text: str, action: str = None, parameters: dict = None) -> dict:
        try:
            parameters = parameters or {}
            if not action:
                return {"success": False, "message": "No vision action specified.", "data": {}}
            if action == "search_news":
                return self.search_news(parameters.get("query", ""))
            elif action == "summarize_news":
                return self.summarize_news()
            elif action == "quick_answer":
                return self.quick_answer(parameters.get("query", input_text))
            elif action == "sports_query":
                return self.sports_query(parameters.get("query", input_text))
            elif action == "web_search":
                return self.web_search(parameters.get("query", input_text), parameters.get("n", 5))
            elif action == "hackernews":
                return self.hackernews(parameters.get("n", 5))
            elif action == "crypto_price":
                return self.crypto_price(parameters.get("coins", parameters.get("coin", "bitcoin")))
            elif action == "currency_convert":
                return self.currency_convert(
                    float(parameters.get("amount", 1)),
                    parameters.get("from", "USD"),
                    parameters.get("to", "EUR"),
                )
            elif action == "translate":
                return self.translate(parameters.get("text", ""), parameters.get("target", "en"))
            elif action == "track_flight":
                return self.track_flight(parameters.get("flight", parameters.get("flight_no", "")))
            elif action == "describe_image":
                from core.vision_model import describe_image
                return describe_image(parameters.get("path", input_text),
                                      parameters.get("question", ""))
            elif action == "screenshot_describe":
                from core.vision_model import screenshot_describe
                return screenshot_describe(parameters.get("question", ""))
            return {"success": False, "message": f"Unsupported vision action: {action}", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Vision agent error: {str(e)}", "data": {}}


vision_agent = VisionAgent()
