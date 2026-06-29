"""Crypto agent — encode/decode/hash/JWT/cipher transforms (CODEX).

Thin wrapper over core.crypto_tools (deterministic, no LLM). Useful for
bug-bounty (JWT + token decode, payload encoding), CTF, and everyday
"decode this base64". Routed deterministically by the regex router.
"""
from core import crypto_tools


class CryptoAgent:
    """Deterministic crypto/encoding toolkit. Actions: crypto, list_ops."""

    def run(self, input_text: str, action: str = None, parameters: dict = None) -> dict:
        try:
            parameters = parameters or {}

            if action == "list_ops":
                ops = crypto_tools.list_operations()
                lines = [f"  {n} — {info['description']}" for n, info in ops.items()]
                return {"success": True,
                        "message": f"{len(ops)} crypto ops:\n" + "\n".join(lines),
                        "data": {"operations": ops}}

            if action == "crypto":
                op = (parameters.get("op") or "").strip()
                payload = parameters.get("input", input_text or "")
                if not op:
                    return {"success": False, "message": "Need an op (e.g. base64_decode).", "data": {}}
                extra = {k: v for k, v in parameters.items() if k not in ("op", "input")}
                res = crypto_tools.execute(op, payload, **extra)
                if res.get("success"):
                    result = res.get("result", "")
                    # Narrate the result instead of returning the raw hash/decoded bytes alone.
                    # Operation-class -> human prefix.
                    if op.endswith("_hash"):
                        label = op.replace("_hash", "").upper()
                        msg = f"{label}: {result}"
                    elif op.endswith("_encode") or op == "rot13":
                        scheme = op.replace("_encode", "").replace("rot13", "ROT13").upper()
                        msg = f"{scheme} encoded: {result}"
                    elif op.endswith("_decode"):
                        scheme = op.replace("_decode", "").upper()
                        msg = f"Decoded ({scheme}): {result}"
                    elif op == "jwt_decode":
                        msg = f"JWT decoded:\n{result}"
                    elif op == "auto_decode":
                        msg = f"Best guess:\n{result}"
                    else:
                        msg = f"{op}: {result}"
                    return {"success": True, "message": msg,
                            "data": {"op": op, "result": result}}
                return {"success": False, "message": res.get("error", "crypto op failed"),
                        "data": {"op": op}}

            return {"success": False, "message": f"Unknown crypto action: {action}", "data": {}}

        except Exception as e:
            return {"success": False, "message": f"Crypto error: {str(e)}", "data": {}}


crypto_agent = CryptoAgent()
