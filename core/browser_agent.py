from core.browser_worker import (
    browser_worker
)

from core.browser_memory import (
    save_browser_state,
    get_browser_state
)

from core.runtime_flags import is_browser_enabled

_BROWSER_DISABLED_MSG = {"success": False, "message": "Browser disabled. Say 'enable browser' to turn on Veronica browser features.", "data": {}}


class BrowserAgent:

    def __init__(self):

        self.started = False

    # =====================================
    # ENSURE WORKER RUNNING
    # =====================================
    def ensure_started(self):

        # Browser off -> raise so every caller's try/except returns a clean
        # message instead of blocking forever on a worker that never started.
        if not is_browser_enabled():
            raise RuntimeError(
                "Browser disabled. Say 'enable browser' to use Veronica browser features."
            )

        if not self.started:

            browser_worker.start()

            self.started = True

        return True

    # =====================================
    # GOOGLE SEARCH
    # =====================================
    def search_google(
        self,
        query
    ):

        if not is_browser_enabled():
            return _BROWSER_DISABLED_MSG

        try:

            self.ensure_started()

            result = browser_worker.submit(

                "google_search",

                {
                    "query": query
                }
            )

            save_browser_state(
                search=f"Google: {query}"
            )

            return result

        except Exception as e:

            return {

                "success": False,

                "message":
                f"Google search failed: {str(e)}",

                "data": {}
            }

    # =====================================
    # GITHUB SEARCH
    # =====================================
    def search_github(
        self,
        query
    ):

        if not is_browser_enabled():
            return _BROWSER_DISABLED_MSG

        try:

            self.ensure_started()

            result = browser_worker.submit(

                "github_search",

                {
                    "query": query
                }
            )

            save_browser_state(
                search=f"GitHub: {query}"
            )

            return result

        except Exception as e:

            return {

                "success": False,

                "message":
                f"GitHub search failed: {str(e)}",

                "data": {}
            }

    # =====================================
    # YOUTUBE SEARCH
    # =====================================
    def search_youtube(
        self,
        query
    ):

        try:

            self.ensure_started()

            result = browser_worker.submit(

                "youtube_search",

                {
                    "query": query
                }
            )

            save_browser_state(
                search=f"YouTube: {query}"
            )

            return result

        except Exception as e:

            return {

                "success": False,

                "message":
                f"YouTube search failed: {str(e)}",

                "data": {}
            }

    # =====================================
    # CLICK FIRST RESULT
    # =====================================
    def click_first_result(self):

        try:

            self.ensure_started()

            return browser_worker.submit(

                "click_first_result",

                {}
            )

        except Exception as e:

            return {

                "success": False,

                "message":
                f"Click failed: {str(e)}",

                "data": {}
            }

    # =====================================
    # OPEN RESULT BY INDEX
    # =====================================
    def open_result(self, index: int):

        try:

            self.ensure_started()

            return browser_worker.submit(
                "open_result",
                {"index": index}
            )

        except Exception as e:

            return {
                "success": False,
                "message": f"Open result failed: {str(e)}",
                "data": {}
            }

    # =====================================
    # GO BACK
    # =====================================
    def go_back(self):

        try:

            self.ensure_started()

            return browser_worker.submit("go_back", {})

        except Exception as e:

            return {
                "success": False,
                "message": f"Go back failed: {str(e)}",
                "data": {}
            }

    # =====================================
    # GO FORWARD
    # =====================================
    def go_forward(self):

        try:

            self.ensure_started()

            return browser_worker.submit("go_forward", {})

        except Exception as e:

            return {
                "success": False,
                "message": f"Go forward failed: {str(e)}",
                "data": {}
            }

    # =====================================
    # CURRENT PAGE
    # =====================================
    def current_page(self):

        try:
            self.ensure_started()
            return browser_worker.submit("current_page", {})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    # =====================================
    # GET PAGE TEXT
    # =====================================
    def get_page_text(self):

        try:
            self.ensure_started()
            return browser_worker.submit("get_page_text", {})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    # =====================================
    # READ README
    # =====================================
    def read_readme(self):

        try:
            self.ensure_started()
            return browser_worker.submit("read_readme", {})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    # =====================================
    # EXTRACT LINKS
    # =====================================
    def extract_links(self):

        try:
            self.ensure_started()
            return browser_worker.submit("extract_links", {})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    # =====================================
    # TAB MANAGEMENT (Phase 20)
    # =====================================
    def new_tab(self, label: str = "", url: str = ""):
        try:
            self.ensure_started()
            return browser_worker.submit("new_tab", {"label": label, "url": url})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    def switch_tab(self, label: str):
        try:
            self.ensure_started()
            return browser_worker.submit("switch_tab", {"label": label})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    def list_tabs(self):
        try:
            self.ensure_started()
            return browser_worker.submit("list_tabs", {})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    def close_tab(self, label: str = ""):
        try:
            self.ensure_started()
            return browser_worker.submit("close_tab", {"label": label})
        except Exception as e:
            return {"success": False, "message": str(e), "data": {}}

    # =====================================
    # PAGE INFO
    # =====================================
    def get_page_info(self):

        state = get_browser_state()

        if not state.get("url"):

            return {

                "success": False,

                "message":
                "No active page found.",

                "data": {}
            }

        return {

            "success": True,

            "message":
            (
                f"Current Page\n\n"
                f"Title: {state.get('title')}\n"
                f"URL: {state.get('url')}"
            ),

            "data":
            state
        }


browser_agent = BrowserAgent()