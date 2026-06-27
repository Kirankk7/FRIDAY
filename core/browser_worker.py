from playwright.sync_api import sync_playwright
from queue import Queue
from threading import Thread
import traceback
import time


class BrowserWorker:

    def __init__(self):

        self.queue = Queue()

        self.worker_thread = None

        self.playwright = None
        self.browser = None
        self.page = None

        self.running = False

        self.last_results = []

        # Phase 20 — tab registry
        self.pages = {}        # label (str) -> Page
        self.active_label = None

    def start(self):

        if self.running:
            return

        self.running = True

        self.worker_thread = Thread(
            target=self._worker_loop,
            daemon=True
        )

        self.worker_thread.start()

        print(
            "[web] Browser Worker Started"
        )

    def stop(self):

        self.running = False

        try:

            if self.browser:
                self.browser.close()

            if self.playwright:
                self.playwright.stop()

        except Exception:
            pass

    def _ensure_browser(self):

        if self.page:
            return

        try:
            self.playwright = sync_playwright().start()

            # Try system Chrome first, fall back to Chromium bundled with Playwright
            try:
                self.browser = self.playwright.chromium.launch(
                    channel="chrome",
                    headless=False
                )
            except Exception:
                self.browser = self.playwright.chromium.launch(headless=False)

            self.page = self.browser.new_page()

            # Register as "main" tab
            self.pages["main"] = self.page
            self.active_label = "main"

            print("[browser] Playwright ready")

        except Exception as e:
            print(f"[browser] Failed to launch browser: {e}")
            self.playwright = None
            self.browser = None
            self.page = None

    def _worker_loop(self):

        self._ensure_browser()

        while self.running:

            job = self.queue.get()

            if job is None:
                continue

            action = job["action"]

            data = job["data"]

            callback = job["callback"]

            # Browser failed to init — return graceful error instead of crashing
            if not self.page:
                self._ensure_browser()  # retry once
            if not self.page:
                if callback:
                    callback({"success": False, "message": "Browser unavailable. Make sure Chrome is installed.", "data": {}})
                continue

            try:

                result = self._execute(
                    action,
                    data
                )

            except Exception:

                print(
                    traceback.format_exc()
                )

                result = {

                    "success": False,

                    "message":
                    "Browser action failed.",

                    "data": {}
                }

            callback(
                result
            )

    def _execute(
        self,
        action,
        data
    ):

        # =====================
        # GOOGLE
        # =====================
        if action == "google_search":

            query = data["query"]

            self.page.goto(
                "https://www.google.com"
            )

            self.page.fill(
                'textarea[name="q"]',
                query
            )

            self.page.press(
                'textarea[name="q"]',
                "Enter"
            )

            self.page.wait_for_timeout(
                 2000
            )

            return {

                "success": True,

                "message":
                f"Searching Google for {query}",

                "data": {}
            }

        # =====================
        # GITHUB
        # =====================
        elif action == "github_search":

            query = data["query"]

            self.page.goto(
                "https://github.com/search"
            )

            self.page.wait_for_load_state(
                "domcontentloaded"
            )

            search_box = self.page.locator(
                'input[placeholder*="Search"]'
            ).first

            search_box.click()

            search_box.fill(
                query
            )

            search_box.press(
                "Enter"
            )

            self.page.wait_for_timeout(
                2000
            )

            # Store results
            self.last_results = []

            try:
                repo_links = self.page.locator("a")
                count = repo_links.count()

                for i in range(count):
                    try:
                        link = repo_links.nth(i)
                        href = link.get_attribute("href")
                        text = link.inner_text().strip()

                        if (
                            href
                            and href.startswith("/")
                            and href.count("/") == 2
                            and "/" in text
                        ):
                            self.last_results.append({
                                "title": text,
                                "url": f"https://github.com{href}"
                            })

                        if len(self.last_results) >= 10:
                            break

                    except:
                        pass

            except:
                pass

            return {

                "success": True,

                "message":
                f"Searching GitHub for {query}",

                "data": {
                    "results": self.last_results
                }
            }

        # =====================
        # YOUTUBE
        # =====================
        elif action == "youtube_search":

            query = data["query"]

            self.page.goto(
                "https://www.youtube.com"
            )

            self.page.wait_for_load_state(
                "domcontentloaded"
            )

            search_box = self.page.locator(
                'input[name="search_query"]'
            )

            search_box.fill(
                query
            )

            search_box.press(
                "Enter"
            )

            self.page.wait_for_timeout(
                2000
            )

            return {

                "success": True,

                "message":
                f"Searching YouTube for {query}",

                "data": {}
            }

                # =====================
        # CLICK FIRST RESULT
        # =====================
        elif action == "click_first_result":

            try:

                current_url = self.page.url

                print(
                    f"CURRENT PAGE: {current_url}"
                )

                # =====================
                # GITHUB SEARCH PAGE
                # =====================
                if "github.com/search" in current_url:

                    repo_links = self.page.locator(
                        "a"
                    )

                    count = repo_links.count()

                    print(
                        f"GITHUB LINKS FOUND: {count}"
                    )

                    for i in range(count):

                        try:

                            link = repo_links.nth(i)

                            href = (
                                link.get_attribute(
                                    "href"
                                )
                            )

                            text = (
                                link.inner_text()
                                .strip()
                            )

                            if (
                                href
                                and href.startswith("/")
                                and href.count("/") == 2
                                and "/" in text
                            ):

                                print(
                                    f"REPO: {text}"
                                )

                                print(
                                    f"CLICKING: {href}"
                                )

                                link.click()

                                self.page.wait_for_timeout(
                                    2000
                                )

                                return {

                                    "success": True,

                                    "message":
                                    f"Opened {text}",

                                    "data": {}
                                }

                        except:
                            pass

                # =====================
                # FALLBACK
                # =====================
                links = self.page.locator(
                    "a"
                )

                count = links.count()

                for i in range(count):

                    try:

                        link = links.nth(i)

                        href = (
                            link.get_attribute(
                                "href"
                            )
                        )

                        if href:

                            link.click()

                            self.page.wait_for_timeout(
                                2000
                            )

                            return {

                                "success": True,

                                "message":
                                "Clicked first result.",

                                "data": {}
                            }

                    except:
                        pass

                return {

                    "success": False,

                    "message":
                    "No clickable result found.",

                    "data": {}
                }

            except Exception as e:

                return {

                    "success": False,

                    "message":
                    str(e),

                    "data": {}
                }

        # =====================
        # OPEN RESULT BY INDEX
        # =====================
        elif action == "open_result":

            index = data.get("index", 0)

            if not self.last_results:
                return {
                    "success": False,
                    "message": "No results stored. Search first.",
                    "data": {}
                }

            if index >= len(self.last_results):
                return {
                    "success": False,
                    "message": f"Only {len(self.last_results)} results stored.",
                    "data": {}
                }

            target = self.last_results[index]
            url = target["url"]
            title = target["title"]

            self.page.goto(url)
            self.page.wait_for_timeout(2000)

            return {
                "success": True,
                "message": f"Opened {title}",
                "data": {"url": url, "title": title}
            }

        # =====================
        # GO BACK
        # =====================
        elif action == "go_back":

            self.page.go_back()
            self.page.wait_for_timeout(1500)

            return {
                "success": True,
                "message": "Went back.",
                "data": {}
            }

        # =====================
        # GO FORWARD
        # =====================
        elif action == "go_forward":

            self.page.go_forward()
            self.page.wait_for_timeout(1500)

            return {
                "success": True,
                "message": "Went forward.",
                "data": {}
            }

        # =====================
        # WHAT PAGE AM I ON
        # =====================
        elif action == "current_page":

            url = self.page.url
            title = self.page.title()

            return {
                "success": True,
                "message": f"Page: {title}\nURL: {url}",
                "data": {"url": url, "title": title}
            }

        # =====================
        # GET PAGE TEXT
        # =====================
        elif action == "get_page_text":

            # Extract visible text only
            text = self.page.evaluate("""
                () => {
                    const clone = document.body.cloneNode(true);
                    const remove = clone.querySelectorAll(
                        'script, style, noscript, nav, footer, header'
                    );
                    remove.forEach(el => el.remove());
                    return clone.innerText;
                }
            """)

            # Trim to 4000 chars for LLM
            trimmed = text.strip()[:4000]

            return {
                "success": True,
                "message": trimmed,
                "data": {"length": len(text)}
            }

        # =====================
        # READ README (GitHub)
        # =====================
        elif action == "read_readme":

            url = self.page.url

            # Must be on a GitHub repo page
            if "github.com" not in url:
                return {
                    "success": False,
                    "message": "Not on GitHub. Navigate to repo first.",
                    "data": {}
                }

            try:
                readme = self.page.locator(
                    "article"
                ).first.inner_text()

                trimmed = readme.strip()[:4000]

                return {
                    "success": True,
                    "message": trimmed,
                    "data": {"url": url}
                }

            except Exception:

                return {
                    "success": False,
                    "message": "README not found on this page.",
                    "data": {}
                }

        # =====================
        # EXTRACT LINKS
        # =====================
        elif action == "extract_links":

            links = self.page.evaluate("""
                () => {
                    const anchors = document.querySelectorAll('a[href]');
                    return Array.from(anchors)
                        .map(a => ({
                            text: a.innerText.trim(),
                            href: a.href
                        }))
                        .filter(l => l.text && l.href.startsWith('http'))
                        .slice(0, 20);
                }
            """)

            if not links:
                return {
                    "success": False,
                    "message": "No links found.",
                    "data": {}
                }

            msg = "\n".join(
                f"{l['text']} -> {l['href']}"
                for l in links
            )

            return {
                "success": True,
                "message": msg,
                "data": {"links": links}
            }

        # =====================
        # NEW TAB
        # =====================
        elif action == "new_tab":

            label = data.get("label", "").strip().lower() or f"tab{len(self.pages)+1}"
            url = data.get("url", "")

            new_page = self.browser.new_page()
            self.pages[label] = new_page
            self.page = new_page
            self.active_label = label

            if url:
                if not url.startswith(("http://", "https://")):
                    url = f"https://{url}"
                new_page.goto(url)
                new_page.wait_for_timeout(2000)
                msg = f"Opened new tab '{label}' at {url}"
            else:
                msg = f"Opened new tab '{label}'"

            return {"success": True, "message": msg, "data": {"label": label}}

        # =====================
        # SWITCH TAB
        # =====================
        elif action == "switch_tab":

            label = data.get("label", "").strip().lower()

            if label in self.pages:
                self.page = self.pages[label]
                self.active_label = label
                title = self.page.title()
                return {
                    "success": True,
                    "message": f"Switched to tab '{label}' — {title}",
                    "data": {"label": label, "title": title}
                }

            # Fuzzy: find tab whose label contains the query
            for tab_label, tab_page in self.pages.items():
                if label in tab_label or tab_label in label:
                    self.page = tab_page
                    self.active_label = tab_label
                    title = tab_page.title()
                    return {
                        "success": True,
                        "message": f"Switched to tab '{tab_label}' — {title}",
                        "data": {"label": tab_label, "title": title}
                    }

            return {
                "success": False,
                "message": f"No tab found matching '{label}'. Open tabs: {', '.join(self.pages.keys())}",
                "data": {}
            }

        # =====================
        # LIST TABS
        # =====================
        elif action == "list_tabs":

            if not self.pages:
                return {"success": True, "message": "No tabs open.", "data": {}}

            lines = []
            for lbl, pg in self.pages.items():
                try:
                    t = pg.title() or pg.url
                except Exception:
                    t = "(closed)"
                marker = " < active" if lbl == self.active_label else ""
                lines.append(f"  {lbl}: {t}{marker}")

            msg = "Open tabs:\n" + "\n".join(lines)
            return {"success": True, "message": msg, "data": {"tabs": list(self.pages.keys())}}

        # =====================
        # CLOSE TAB
        # =====================
        elif action == "close_tab":

            label = data.get("label", "").strip().lower() or self.active_label

            if label not in self.pages:
                return {"success": False, "message": f"No tab '{label}' found.", "data": {}}

            try:
                self.pages[label].close()
            except Exception:
                pass

            del self.pages[label]

            # Switch to last remaining tab
            if self.pages:
                self.active_label = list(self.pages.keys())[-1]
                self.page = self.pages[self.active_label]
                msg = f"Closed tab '{label}'. Now on '{self.active_label}'."
            else:
                self.active_label = None
                self.page = None
                msg = f"Closed tab '{label}'. No tabs remaining."

            return {"success": True, "message": msg, "data": {}}

        return {

            "success": False,

            "message":
            f"Unknown browser action: {action}",

            "data": {}
        }

    def submit(
        self,
        action,
        data,
        timeout: float = 90.0
    ):

        # Safety: if the worker isn't running, start it (auto-start on demand).
        if not self.running:
            self.start()

        result_holder = {}

        finished = []

        def callback(result):

            result_holder["result"] = result

            finished.append(
                True
            )

        self.queue.put({

            "action":
            action,

            "data":
            data,

            "callback":
            callback
        })

        # Bounded wait — never hang forever (defense against a stuck page or dead worker)
        deadline = time.time() + timeout
        while not finished:
            if time.time() > deadline:
                return {
                    "success": False,
                    "message": "Browser timed out — the page took too long or the browser couldn't start.",
                    "data": {}
                }
            time.sleep(0.05)

        return result_holder[
            "result"
        ]

browser_worker = BrowserWorker()