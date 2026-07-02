"""
Daily agent (codename ATLAS) — daily-life info: weather (A), morning briefing (B),
unified find (D), and calendar ICS import/export (G). Thin wrapper over core modules.
"""
from core import weather, briefing, unified_find, calendar_ics


class DailyAgent:
    def run(self, input_text: str = "", action: str = None, parameters: dict = None) -> dict:
        p = parameters or {}
        try:
            if action == "weather":
                return weather.get_weather(p.get("place", ""))
            if action == "will_rain":
                return weather.will_rain(p.get("place", ""), p.get("day", "today"))
            if action == "briefing":
                return briefing.build_briefing()
            if action == "find":
                return unified_find.find(p.get("query", "") or input_text)
            if action == "cal_export":
                return calendar_ics.export_ics(p.get("path", ""))
            if action == "cal_import":
                return calendar_ics.import_ics(p.get("src", ""))
            if action == "watch_docs":
                from core import rag
                return rag.watch_folder(p.get("folder", ""))
            if action == "unwatch_docs":
                from core import rag
                return rag.unwatch_folder(p.get("folder", ""))
            if action == "docs_watched":
                from core import rag
                return rag.list_watched()
            return {"success": False, "message": f"Unknown daily action: {action}", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Daily error: {str(e)[:80]}", "data": {}}


daily_agent = DailyAgent()
