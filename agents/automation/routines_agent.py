"""Phase 43 — Routines agent (tool wrapper over core.routines.routine_manager)."""
from core.routines import routine_manager


class RoutinesAgent:
    def run(self, input_text: str = "", action: str = None, parameters: dict = None) -> dict:
        parameters = parameters or {}
        try:
            if action == "create_routine":
                msg = routine_manager.start_recording(parameters.get("name", ""))
            elif action == "stop_recording":
                msg = routine_manager.stop_recording()
            elif action == "cancel_recording":
                msg = routine_manager.cancel_recording()
            elif action == "run_routine":
                msg = routine_manager.run_routine(parameters.get("name", ""))
            elif action == "list_routines":
                msg = routine_manager.list_routines()
            elif action == "delete_routine":
                msg = routine_manager.delete_routine(parameters.get("name", ""))
            else:
                return {"success": False, "message": f"Unsupported routines action: {action}", "data": {}}
            return {"success": True, "message": msg, "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Routines error: {e}", "data": {}}


routines_agent = RoutinesAgent()
