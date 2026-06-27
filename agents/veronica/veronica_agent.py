from core.browser_agent import browser_agent
from core.llm import ask_llm
import os
import subprocess
import platform
import webbrowser
import socket
import psutil
import datetime


class VeronicaAgent:
    """
    Veronica v3 - Premium

    Features:
    - Open apps
    - Open Windows folders
    - Browser memory
    - Smart URL opening
    - YouTube / Google / GitHub search
    - Friendly speech output
    - System information
    - Smart website fallback
    - Standardized run() interface
    - Workflow compatible
    """

    APP_COMMANDS = {

        # ==============================
        # Browsers
        # ==============================
        "chrome": "start chrome",
        "edge": "start msedge",
        "firefox": "start firefox",

        # ==============================
        # Development
        # ==============================
        "vscode": "code",
        "visual studio code": "code",

        # ==============================
        # Utilities
        # ==============================
        "notepad": "notepad",
        "calculator": "calc",
        "cmd": "start cmd",
        "powershell": "start powershell",
        "task manager": "taskmgr",
        "settings": "start ms-settings:",
        "control panel": "control",
        "device manager": "devmgmt.msc",

        # ==============================
        # Windows folders
        # ==============================
        "downloads": os.path.join(
            os.path.expanduser("~"),
            "Downloads"
        ),

        "desktop": os.path.join(
            os.path.expanduser("~"),
            "Desktop"
        ),

        "documents": os.path.join(
            os.path.expanduser("~"),
            "Documents"
        ),

        "pictures": os.path.join(
            os.path.expanduser("~"),
            "Pictures"
        ),

        "videos": os.path.join(
            os.path.expanduser("~"),
            "Videos"
        ),

        "music": os.path.join(
            os.path.expanduser("~"),
            "Music"
        )
    }

    # =====================================
    # WEBSITE FALLBACK MAP
    # =====================================
    WEBSITE_SHORTCUTS = {

        "youtube":
        "https://youtube.com",

        "github":
        "https://github.com",

        "linkedin":
        "https://linkedin.com",

        "gmail":
        "https://mail.google.com",

        "chatgpt":
        "https://chatgpt.com",

        "reddit":
        "https://reddit.com",

        "spotify":
        "https://spotify.com",

        "instagram":
        "https://instagram.com",

        "facebook":
        "https://facebook.com",

        "netflix":
        "https://netflix.com",

        "amazon":
        "https://amazon.com",

        "x":
        "https://x.com",

        "twitter":
        "https://x.com"
    }

    def __init__(self):

        self.current_browser = None

    # =====================================
    # OPEN APP / FOLDER
    # =====================================
    def open_app(
        self,
        app: str
    ):

        app = (
            app.lower()
            .strip()
        )

        command = (
            self.APP_COMMANDS.get(
                app
            )
        )

        # =====================================
        # SMART WEBSITE FALLBACK
        # =====================================
        if not command:

            website = (
                self.WEBSITE_SHORTCUTS.get(
                    app
                )
            )

            if website:

                print(
                    f"[web] Website fallback: "
                    f"{app}"
                )

                return self.open_url(
                    website
                )

            return {

                "success": False,

                "message":
                (
                    f"I couldn't find "
                    f"'{app}'."
                ),

                "data": {
                    "app": app
                }
            }

        try:

            # ==============================
            # WINDOWS FOLDER
            # ==============================
            if os.path.exists(
                command
            ):

                os.startfile(
                    command
                )

                return {

                    "success": True,

                    "message":
                    f"Opening {app}",

                    "data": {

                        "path":
                        command
                    }
                }

            # ==============================
            # NORMAL APP
            # ==============================
            # Security (W2): no shell=True. `command` is an allowlisted dict value;
            # launch via argv list, and route URIs / .msc consoles through startfile.
            if (
                platform.system()
                == "Windows"
            ):

                parts = command.split()
                if parts and parts[0] == "start":   # "start cmd" -> drop cmd.exe builtin
                    parts = parts[1:]
                target = parts[0] if parts else command
                if target.endswith(":") or target.endswith(".msc"):
                    os.startfile(target)            # noqa: S606 — fixed allowlisted URI/console
                else:
                    subprocess.Popen(parts or [target])

            else:

                subprocess.Popen(
                    command.split()
                )

            # ==============================
            # Browser Memory
            # ==============================
            if app in {

                "chrome",
                "edge",
                "firefox"
            }:

                self.current_browser = app

                print(
                    f"[web] Active browser: "
                    f"{app}"
                )

            return {

                "success": True,

                "message":
                f"Opening {app}",

                "data": {
                    "app": app
                }
            }

        except Exception as e:

            return {

                "success": False,

                "message":
                f"Failed to open app: {str(e)}",

                "data": {}
            }

    # =====================================
    # OPEN URL / SMART SEARCH
    # =====================================
    def open_url(
        self,
        url: str
    ):

        if not url:

            return {

                "success": False,

                "message":
                "URL missing.",

                "data": {}
            }

        try:

            lower_url = (
                url.lower()
                .strip()
            )

            friendly_message = (
                "Opening website"
            )

                      # ==============================
            # YOUTUBE SEARCH
            # ==============================
            if lower_url.startswith(
                "search youtube for "
            ):

                query_text = (
                    lower_url.replace(
                        "search youtube for ",
                        ""
                    ).strip()
                )

                return browser_agent.search_youtube(
                    query_text
                )

            # ==============================
            # GOOGLE SEARCH
            # ==============================
            elif lower_url.startswith(
                "search google for "
            ):

                query_text = (
                    lower_url.replace(
                        "search google for ",
                        ""
                    ).strip()
                )

                return browser_agent.search_google(
                    query_text
                )
                      # ==============================
            # GITHUB SEARCH
            # ==============================
            elif lower_url.startswith(
                "search github for "
            ):

                query_text = (
                    lower_url.replace(
                        "search github for ",
                        ""
                    ).strip()
                )

                return browser_agent.search_github(
                    query_text
                )

            # ==============================
            # CLICK FIRST RESULT
            # ==============================
            elif lower_url == (
                "click first result"
            ):

                return browser_agent.click_first_result()

            # ==============================
            # NORMAL WEBSITE
            # ==============================
            elif not url.startswith(
                (
                    "http://",
                    "https://"
                )
            ):

                url = (
                    f"https://{url}"
                )

                friendly_message = (
                    f"Opening {lower_url}"
                )

            browser = (
                self.current_browser
            )

            print(
                f"[web] Using browser: "
                f"{browser}"
            )

            if (
                platform.system()
                == "Windows"
            ):

                if browser == "chrome":

                    chrome_paths = [

                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",

                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                    ]

                    chrome_exe = None

                    for path in chrome_paths:

                        if os.path.exists(
                            path
                        ):

                            chrome_exe = path
                            break

                    if chrome_exe:

                        subprocess.Popen([

                            chrome_exe,
                            "--new-tab",
                            url
                        ])

                    else:

                        webbrowser.open(
                            url
                        )

                elif browser == "edge":

                    subprocess.Popen([

                        "cmd",
                        "/c",
                        "start",
                        "msedge",
                        "--new-tab",
                        url
                    ])

                elif browser == "firefox":

                    subprocess.Popen([

                        "cmd",
                        "/c",
                        "start",
                        "firefox",
                        "-new-tab",
                        url
                    ])

                else:

                    webbrowser.open(
                        url
                    )

            else:

                webbrowser.open(
                    url
                )

            return {

                "success": True,

                "message":
                friendly_message,

                "data": {

                    "url":
                    url,

                    "browser":
                    browser
                }
            }

        except Exception as e:

            return {

                "success": False,

                "message":
                f"Failed to open website: {str(e)}",

                "data": {}
            }

    # =====================================
    # SYSTEM INFO
    # =====================================
    def get_system_info(
        self
    ):

        try:

            ram = psutil.virtual_memory()

            battery = (
                psutil.sensors_battery()
            )

            hostname = (
                socket.gethostname()
            )

            ip = (
                socket.gethostbyname(
                    hostname
                )
            )

            return {

                "success": True,

                "message":
                (
                    f"System Information\n\n"
                    f"OS: Windows 11\n"
                    f"Installed RAM: "
                    f"{round(ram.total / (1024**3))} GB\n"
                    f"Available RAM: "
                    f"{round(ram.available / (1024**3), 2)} GB\n"
                    f"Battery: "
                    f"{battery.percent if battery else 'N/A'}%\n"
                    f"WiFi: Connected\n"
                    f"IP Address: {ip}"
                ),

                "data": {}
            }

        except Exception as e:

            return {

                "success": False,

                "message":
                f"Failed to get system info: {str(e)}",

                "data": {}
            }

    # =====================================
    # SAVE REPORT TO DESKTOP
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
            )

            filename = f"research_{safe_name}_{date_str}.md"
            filepath = os.path.join(desktop, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return filepath

        except Exception as e:
            return None

    # =====================================
    # RESEARCH WORKFLOW
    # =====================================
    def research_workflow(self, query: str):

        if not query:
            return {
                "success": False,
                "message": "No research query provided.",
                "data": {}
            }

        steps_log = []

        # ── Step 1: GitHub search ──
        steps_log.append(f"Searching GitHub for: {query}")

        search_result = browser_agent.search_github(query)

        if not search_result.get("success"):
            return {
                "success": False,
                "message": f"GitHub search failed: {search_result.get('message')}",
                "data": {}
            }

        # ── Step 2: Open first result ──
        open_result = browser_agent.open_result(0)

        if not open_result.get("success"):
            return {
                "success": False,
                "message": f"Could not open result: {open_result.get('message')}",
                "data": {}
            }

        repo_title = open_result.get("data", {}).get("title", query)
        repo_url = open_result.get("data", {}).get("url", "")
        steps_log.append(f"Opened: {repo_title}")

        # ── Step 3: Read README ──
        readme_result = browser_agent.read_readme()

        readme_text = ""

        if readme_result.get("success"):
            readme_text = readme_result.get("message", "")
            steps_log.append("README extracted.")
        else:
            steps_log.append("README not found. Using page text.")
            page_result = browser_agent.get_page_text()
            readme_text = page_result.get("message", "")

        if not readme_text:
            return {
                "success": False,
                "message": "Could not extract any content from repo.",
                "data": {}
            }

        # ── Step 4: LLM analysis ──
        steps_log.append("Analyzing with LLM...")

        prompt = f"""You are a technical research assistant. Analyze this GitHub repository and write a structured research report.

Repository: {repo_title}
URL: {repo_url}

README Content:
{readme_text[:3500]}

Write a research report with these sections:
1. Project Purpose
2. Key Features
3. Architecture Overview
4. Installation / Setup
5. Use Cases
6. Strengths
7. Weaknesses or Limitations

Write in clear English. No markdown headers with #. Use plain section labels. Be thorough but concise.

Report:"""

        report_body = ask_llm(prompt)

        if not report_body:
            return {
                "success": False,
                "message": "LLM failed to generate report.",
                "data": {}
            }

        # ── Step 5: Build full report ──
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        full_report = f"""# Research Report: {repo_title}

**Query:** {query}
**URL:** {repo_url}
**Generated:** {date_str}

---

{report_body}

---
*Generated by JARVIS Research Agent*
"""

        # ── Step 6: Save to Desktop ──
        saved_path = self.save_report(query, full_report)

        save_msg = (
            f"Report saved to Desktop: research_{query.replace(' ', '_')}..."
            if saved_path
            else "Could not save report to Desktop."
        )

        summary = report_body[:300] + "..." if len(report_body) > 300 else report_body

        return {
            "success": True,
            "message": f"{summary}\n\n{save_msg}",
            "data": {
                "repo": repo_title,
                "url": repo_url,
                "saved_path": saved_path,
                "full_report": full_report
            }
        }

    # =====================================
    # STANDARD RUN
    # =====================================
    def run(
        self,
        input_text: str,
        action=None,
        parameters=None
    ):

        parameters = (
            parameters or {}
        )

        # Non-browser actions — always allowed
        _no_browser_actions = {"open_app", "system_info"}
        if action not in _no_browser_actions:
            from core.runtime_flags import is_browser_enabled
            if not is_browser_enabled():
                return {"success": False, "message": "Browser disabled. Say 'enable browser' to turn on Playwright.", "data": {}}

        if action == "open_app":

            return self.open_app(
                parameters.get(
                    "app",
                    ""
                )
            )

        elif action == "open_url":

            return self.open_url(
                parameters.get(
                    "url",
                    ""
                )
            )

        elif action == "system_info":

            return self.get_system_info()

        elif action == "open_result":

            index = parameters.get("index", 0)
            return browser_agent.open_result(index)

        elif action == "go_back":

            return browser_agent.go_back()

        elif action == "go_forward":

            return browser_agent.go_forward()

        elif action == "current_page":

            return browser_agent.current_page()

        elif action == "get_page_text":

            return browser_agent.get_page_text()

        elif action == "read_readme":

            return browser_agent.read_readme()

        elif action == "extract_links":

            return browser_agent.extract_links()

        elif action == "summarize_page":

            result = browser_agent.get_page_text()

            if not result.get("success"):
                return result

            page_text = result["message"]

            prompt = f"""Summarize this web page content in clear, concise spoken English.
No bullet points. No markdown. Just natural explanation.

Content:
{page_text}

Summary:"""

            summary = ask_llm(prompt)

            return {
                "success": True,
                "message": summary or "Could not summarize.",
                "data": {}
            }

        elif action == "summarize_repo":

            result = browser_agent.read_readme()

            if not result.get("success"):
                return result

            readme_text = result["message"]

            prompt = f"""You are analyzing a GitHub repository README.
Summarize in spoken English: purpose, architecture, key features, installation.
No bullet points. No markdown. Natural explanation.

README:
{readme_text}

Summary:"""

            summary = ask_llm(prompt)

            return {
                "success": True,
                "message": summary or "Could not summarize.",
                "data": {}
            }

        elif action == "research":

            query = parameters.get("query", "")
            return self.research_workflow(query)

        # ── Phase 20: Tab management ──
        elif action == "new_tab":
            label = parameters.get("label", "")
            url = parameters.get("url", "")
            return browser_agent.new_tab(label, url)

        elif action == "switch_tab":
            label = parameters.get("label", "")
            return browser_agent.switch_tab(label)

        elif action == "list_tabs":
            return browser_agent.list_tabs()

        elif action == "close_tab":
            label = parameters.get("label", "")
            return browser_agent.close_tab(label)

        return {

            "success": False,

            "message":
            f"Unsupported action: {action}",

            "data": {}
        }


veronica_agent = VeronicaAgent()