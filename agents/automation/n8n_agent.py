"""
Phase 53 — n8n automation agent.

Triggers self-hosted n8n workflows (outbound actions JARVIS can't do natively:
email, Telegram/WhatsApp, multi-step pipelines). Each n8n workflow with a
Webhook trigger is reachable at {N8N_BASE_URL}/webhook/{path}.

Setup (one-time):
    docker run -it --rm -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
    -> open http://localhost:5678 -> build a workflow -> add a Webhook trigger
    -> JARVIS triggers it with "run workflow <path>".

Graceful when n8n isn't running — never crashes, returns a clear message.
"""
import requests


class N8nAgent:

    def _base(self):
        from config import N8N_BASE_URL
        return N8N_BASE_URL.rstrip("/")

    # ── Trigger a workflow via its webhook ─────────────────────────────────
    def trigger(self, workflow: str, payload: dict = None) -> dict:
        if not workflow:
            return {"success": False, "message": "Which workflow? Say 'run workflow <name>'.", "data": {}}
        wf = workflow.strip().strip("/").replace(" ", "-").lower()
        url = f"{self._base()}/webhook/{wf}"
        try:
            r = requests.post(url, json=payload or {}, timeout=20)
            if r.status_code == 404:
                # try the test-webhook path (n8n exposes /webhook-test/ during editing)
                r2 = requests.post(f"{self._base()}/webhook-test/{wf}", json=payload or {}, timeout=20)
                if r2.status_code == 404:
                    return {"success": False,
                            "message": f"No n8n workflow webhook '{wf}'. Check the workflow is active and the path matches.",
                            "data": {}}
                r = r2
            if r.status_code >= 400:
                return {"success": False, "message": f"n8n workflow '{wf}' returned HTTP {r.status_code}.", "data": {}}
            # n8n may return JSON or plain text from the workflow's Respond node
            try:
                body = r.json()
                summary = body.get("message") or body.get("result") or str(body)[:200]
            except Exception:
                summary = (r.text or "")[:200]
            return {"success": True,
                    "message": f"Workflow '{wf}' triggered. {summary}".strip(),
                    "data": {"workflow": wf, "status": r.status_code}}
        except requests.exceptions.ConnectionError:
            return {"success": False,
                    "message": "n8n isn't reachable. Start it (docker run ... n8nio/n8n) or check N8N_BASE_URL.",
                    "data": {}}
        except Exception as e:
            return {"success": False, "message": f"n8n trigger failed: {e}", "data": {}}

    # ── List workflows (needs API key) ─────────────────────────────────────
    def list_workflows(self) -> dict:
        from config import N8N_API_KEY
        if not N8N_API_KEY:
            return {"success": True,
                    "message": "Set N8N_API_KEY to list workflows. You can still run them with 'run workflow <name>'.",
                    "data": {}}
        try:
            r = requests.get(f"{self._base()}/api/v1/workflows",
                             headers={"X-N8N-API-KEY": N8N_API_KEY}, timeout=15)
            if r.status_code != 200:
                return {"success": False, "message": f"n8n API error {r.status_code}.", "data": {}}
            wfs = r.json().get("data", [])
            if not wfs:
                return {"success": True, "message": "No workflows in n8n yet.", "data": {}}
            names = [w.get("name", "?") + (" (active)" if w.get("active") else "") for w in wfs]
            return {"success": True,
                    "message": f"{len(names)} n8n workflows: " + " | ".join(names[:15]),
                    "data": {"workflows": names}}
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "n8n isn't reachable.", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"Couldn't list workflows: {e}", "data": {}}

    # ── Dispatch ───────────────────────────────────────────────────────────
    def run(self, input_text: str = "", action: str = None, parameters: dict = None) -> dict:
        parameters = parameters or {}
        try:
            if action == "trigger":
                return self.trigger(parameters.get("workflow", ""), parameters.get("payload"))
            elif action == "list_workflows":
                return self.list_workflows()
            return {"success": False, "message": f"Unsupported n8n action: {action}", "data": {}}
        except Exception as e:
            return {"success": False, "message": f"n8n agent error: {e}", "data": {}}


n8n_agent = N8nAgent()
