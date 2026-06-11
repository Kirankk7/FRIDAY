from core.self_improvement import self_improve, get_stats, get_current_directive


class SelfImprovementAgent:
    def run(self, input_text: str = "", action: str = "", parameters: dict = None) -> dict:
        parameters = parameters or {}

        if action == "analyze":
            result = self_improve()
            return {"success": True, "message": result, "data": {}}

        if action == "stats":
            result = get_stats()
            return {"success": True, "message": result, "data": {}}

        if action == "directive":
            d = get_current_directive()
            msg = d if d else "No directive set yet, boss. Run 'analyze your responses' first."
            return {"success": True, "message": msg, "data": {}}

        return {"success": False, "message": f"Unknown self_improvement action: {action}", "data": {}}


self_improvement_agent = SelfImprovementAgent()
