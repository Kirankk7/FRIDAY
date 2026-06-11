from core.personal_memory import set_fact, format_all, get_all


class PersonalAgent:
    """
    Personal Memory Agent.
    Stores and recalls structured facts about the user.
    Facts: weight, location, education, certifications, career, investments, health, name.
    """

    def run(self, input_text: str, action: str = None, parameters: dict = None) -> dict:
        try:
            parameters = parameters or {}

            if action == "set_fact":
                key = parameters.get("key", "").strip()
                value = parameters.get("value", "").strip()
                if not key or not value:
                    return {"success": False, "message": "Need both key and value.", "data": {}}
                set_fact(key, value)
                return {
                    "success": True,
                    "message": f"Got it, boss. {key.capitalize()} locked in as: {value}.",
                    "data": {"key": key, "value": value}
                }

            elif action == "get_all":
                text = format_all()
                return {"success": True, "message": text, "data": {"facts": get_all()}}

            return {"success": False, "message": f"Unknown personal action: {action}", "data": {}}

        except Exception as e:
            return {"success": False, "message": f"Personal memory error: {str(e)}", "data": {}}


personal_agent = PersonalAgent()
