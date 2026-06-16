"""
Phase 63 — Burp traffic ingestion (Community-friendly, no Pro / no API key).

Parse a Burp Suite "Save items" / proxy-history export (XML with base64 request/
response) into an endpoint + parameter inventory. Feeds Ultron's target profile
and gives nuclei/httpx a real list of live endpoints (incl. hidden APIs that
passive recon misses). Optional live connector pulls from the Burp MCP server's
HTTP endpoint if configured.

Active scanning stays out (that's Burp Pro); detection is nuclei's job.
"""

import os
import re
import base64
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, parse_qsl

try:
    from config import BURP_MCP_URL
except Exception:
    BURP_MCP_URL = os.getenv("BURP_MCP_URL", "")


def _decode(node) -> str:
    """Decode a Burp <request>/<response> node (base64 attr or plain text)."""
    if node is None:
        return ""
    txt = node.text or ""
    if node.get("base64") == "true":
        try:
            return base64.b64decode(txt).decode("utf-8", "replace")
        except Exception:
            return ""
    return txt


def _params_from_request(raw_req: str, url: str) -> set:
    """Pull query + body param names from a raw HTTP request and the URL."""
    params = set()
    try:
        params.update(k for k, _ in parse_qsl(urlsplit(url).query))
    except Exception:
        pass
    if raw_req:
        # body params (after the blank line) for form-encoded bodies
        parts = raw_req.split("\r\n\r\n", 1) if "\r\n\r\n" in raw_req else raw_req.split("\n\n", 1)
        if len(parts) == 2 and "=" in parts[1] and "{" not in parts[1][:1]:
            params.update(k for k, _ in parse_qsl(parts[1].strip()))
    return params


def parse_export(path: str) -> dict:
    """Parse a Burp XML export → endpoint inventory."""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return {"success": False, "message": "I couldn't find that Burp export, boss.", "data": {}}
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return {"success": False, "message": f"That doesn't look like a Burp XML export: {str(e)[:60]}", "data": {}}

    endpoints, params, hosts, methods = {}, set(), set(), {}
    items = root.findall(".//item")
    for it in items:
        url = (it.findtext("url") or "").strip()
        method = (it.findtext("method") or "GET").strip().upper()
        status = (it.findtext("status") or "").strip()
        if not url:
            continue
        sp = urlsplit(url)
        hosts.add(sp.netloc)
        key = f"{method} {sp.scheme}://{sp.netloc}{sp.path}"
        endpoints[key] = {"url": f"{sp.scheme}://{sp.netloc}{sp.path}", "method": method,
                          "status": status}
        methods[method] = methods.get(method, 0) + 1
        params.update(_params_from_request(_decode(it.find("request")), url))

    if not endpoints:
        return {"success": False, "message": "No HTTP items found in that export.", "data": {}}

    inv = {
        "items": len(items),
        "hosts": sorted(hosts),
        "endpoints": sorted(endpoints.keys()),
        "urls": sorted({e["url"] for e in endpoints.values()}),
        "params": sorted(params),
        "methods": methods,
    }
    msg = (f"Ingested {len(items)} Burp items: {len(inv['endpoints'])} unique endpoints "
           f"across {len(hosts)} host(s), {len(params)} parameters. "
           f"Methods: {', '.join(f'{m} x{c}' for m, c in sorted(methods.items()))}.")
    return {"success": True, "message": msg, "data": inv}


def live_pull() -> dict:
    """Best-effort pull from the Burp MCP server's HTTP endpoint (if configured)."""
    if not BURP_MCP_URL:
        return {"success": False,
                "message": "No live Burp endpoint set. Export history to XML and use "
                           "ingest_burp <file>, or set BURP_MCP_URL in .env.", "data": {}}
    try:
        import requests
        r = requests.get(BURP_MCP_URL, timeout=8)
        if r.status_code != 200:
            return {"success": False, "message": f"Burp endpoint returned {r.status_code}.", "data": {}}
        # MCP/proxy responses vary; surface what we got for the caller to handle
        return {"success": True, "message": "Connected to Burp endpoint.",
                "data": {"raw": r.text[:5000]}}
    except Exception as e:
        return {"success": False, "message": f"Couldn't reach Burp endpoint: {str(e)[:60]}", "data": {}}
