"""
Finance agent (codename LEDGER) — crypto portfolio (E) + expense log (H).
Local, no bank/exchange integration. Live crypto pricing via vision.crypto_price.
"""
from core import portfolio, expenses


class FinanceAgent:
    def run(self, input_text: str = "", action: str = None, parameters: dict = None) -> dict:
        p = parameters or {}
        try:
            if action == "portfolio_add":
                return portfolio.add_holding(p.get("amount"), p.get("coin", ""))
            if action == "portfolio_remove":
                return portfolio.remove_holding(p.get("coin", ""))
            if action == "portfolio_clear":
                return portfolio.clear()
            if action in ("portfolio_show", "portfolio"):
                return portfolio.value()
            if action == "expense_add":
                return expenses.add_expense(p.get("amount"), p.get("category", "misc"), p.get("note", ""))
            if action == "expense_report":
                return expenses.report(p.get("window", "week"))
            if action == "expense_categories":
                return expenses.by_category(p.get("window", "all"))
            return {"success": False, "message": f"Unknown finance action: {action}", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Finance error: {str(e)[:80]}", "data": {}}


finance_agent = FinanceAgent()
