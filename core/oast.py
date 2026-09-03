"""
OAST / OOB confirmation (v1.3 A5) — local HTTP callback listener + correlation.

Upgrades BLIND probes (SSRF / blind-XXE / blind-cmdi / blind-SQLi) from `candidate` -> `CONFIRMED` by
minting a per-probe callback URL with a correlation id, injecting it into the existing payload, and
observing the out-of-band hit on a listener. That OOB request is proof the target reached out — it can
NOT be produced by reflection, so it turns an unprovable blind bug into a confirmed one.

Design: pluggable + OPT-IN. This module ships a self-contained LOCAL HTTP catcher (threaded, ephemeral
port) — enough for HTTP-based OOB. DNS + interactsh adapters are design-banked (see V1_3_OAST_DESIGN.md);
they implement the same mint()/poll() shape. Default off; local-only hunts are unaffected. This is the one
place reality dents local-first — contained behind an explicit, injectable listener object.
"""
import threading
import datetime
import http.server
import socketserver


class LocalHTTPListener:
    """Catches HTTP callbacks on 127.0.0.1:<ephemeral>. Correlation id = the first path segment.
    mint(cid) -> a callback URL to inject; poll(cid) -> the recorded hits (with src ip / proto / time)."""

    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.port = port
        self._hits = {}
        self._lock = threading.Lock()
        self._httpd = None
        self._thread = None

    def start(self):
        hits, lock = self._hits, self._lock

        class _H(http.server.BaseHTTPRequestHandler):
            def _record(self):
                cid = self.path.strip("/").split("/")[0].split("?")[0]
                with lock:
                    hits.setdefault(cid, []).append({
                        "cid": cid, "path": self.path, "method": self.command,
                        "src_ip": self.client_address[0], "proto": "http",
                        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                        "user_agent": self.headers.get("User-Agent", ""),
                    })
                try:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                except Exception:
                    pass

            do_GET = do_POST = do_HEAD = do_PUT = _record

            def log_message(self, *a):
                pass

        socketserver.TCPServer.allow_reuse_address = True
        self._httpd = socketserver.TCPServer((self.host, self.port), _H)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def mint(self, cid: str) -> str:
        return f"http://{self.host}:{self.port}/{cid}"

    def poll(self, cid: str) -> list:
        with self._lock:
            return list(self._hits.get(cid, []))

    def stop(self):
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass

# ---------------------------------------------------------------------------
# v1.3 A5 adapter (2026-09-01) — INTERNET-REACHABLE listeners.
#
# Why: LocalHTTPListener binds 127.0.0.1, so it can never catch a callback from a
# remote target. That gap cost two reports (one closed INFORMATIVE, one NOT
# APPLICABLE — impact described, not demonstrated) and forced a hand-rolled
# Cloudflare Worker on Auth0. These adapters implement the SAME mint()/poll()
# shape; nothing else in the codebase changes.
#
# Both FAIL LOUDLY when they cannot be internet-reachable. A listener that
# silently degrades to localhost looks like a control and catches nothing.
# ---------------------------------------------------------------------------
import os
import re
import json
import random
import string
import subprocess
import urllib.request

_LABEL_OK = re.compile(r"[^a-z0-9-]")


class OastUnavailable(RuntimeError):
    """Raised when an internet-reachable listener cannot be established.
    Never fall back to loopback: a listener that cannot catch is not a listener."""


def make_cid(proto: str = "http", probe: str = "ssrf", host: str = "t") -> str:
    """Correlation id: {proto}-{probe}-{shorthost}-{rand}, DNS-label-safe (<=63 chars).
    DNS-safe because the same id must work for the design-banked DNS listener."""
    short = _LABEL_OK.sub("", (host or "t").lower().split(":")[0].replace(".", ""))[:12] or "t"
    rand = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    cid = f"{proto}-{probe}-{short}-{rand}".lower()
    cid = _LABEL_OK.sub("", cid)
    return cid[:63]


def evidence_block(cid: str, minted_url: str, hits: list) -> dict:
    """The `oast:` block for the Evidence Object. `confirmed` is TRUE ONLY when a hit
    was observed — that observation is what upgrades candidate -> CONFIRMED."""
    return {
        "oast": {
            "cid": cid,
            "minted_url": minted_url,
            "hit_count": len(hits),
            "confirmed": bool(hits),
            "hits": hits,
            "note": ("target reached the listener out-of-band; cannot be produced by reflection"
                     if hits else "no callback observed — remains a candidate, NOT confirmed"),
        }
    }


class TunnelHTTPListener:
    """LocalHTTPListener + a public `cloudflared` tunnel in front of it.

    mint(cid) returns the PUBLIC url; poll(cid) reads the local listener's hits.
    Requires the `cloudflared` binary on PATH. Raises OastUnavailable otherwise —
    it does NOT quietly return a localhost URL."""

    def __init__(self, binary="cloudflared", timeout=25):
        self.binary = binary
        self.timeout = timeout
        self.local = LocalHTTPListener()
        self.public_url = None
        self._proc = None

    def start(self):
        self.local.start()
        try:
            self._proc = subprocess.Popen(
                [self.binary, "tunnel", "--url", f"http://127.0.0.1:{self.local.port}",
                 "--no-autoupdate"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", bufsize=1)
        except FileNotFoundError:
            self.local.stop()
            raise OastUnavailable(
                f"'{self.binary}' not on PATH. Install it "
                "(https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) "
                "or use RemoteCollectorListener(base_url=...). Refusing to fall back to loopback.")
        pat = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
        import time
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                if self._proc.poll() is not None:
                    break
                continue
            m = pat.search(line)
            if m:
                self.public_url = m.group(0)
                return self
        self.stop()
        raise OastUnavailable(
            f"no public URL from '{self.binary}' within {self.timeout}s. Refusing to fall back to loopback.")

    def mint(self, cid: str) -> str:
        if not self.public_url:
            raise OastUnavailable("tunnel not started; call start() first")
        return f"{self.public_url}/{cid}"

    def poll(self, cid: str) -> list:
        return self.local.poll(cid)

    def stop(self):
        try:
            if self._proc:
                self._proc.terminate()
        except Exception:
            pass
        self.local.stop()


class RemoteCollectorListener:
    """Adapter for an EXTERNAL collector (e.g. the Cloudflare Worker hand-rolled for the
    Auth0 SSRF). Contract, deliberately minimal:
        mint  -> f"{base_url}/{cid}"
        poll  -> GET {poll_url}?cid={cid}  ->  JSON list of hit dicts (or {"hits": [...]})
    Same mint()/poll() shape as the local listener, so callers do not change."""

    def __init__(self, base_url: str = None, poll_url: str = None, token: str = None, timeout=10):
        self.base_url = (base_url or os.environ.get("JARVIS_OAST_BASE") or "").rstrip("/")
        self.poll_url = (poll_url or os.environ.get("JARVIS_OAST_POLL") or
                         (self.base_url + "/_hits" if self.base_url else ""))
        self.token = token or os.environ.get("JARVIS_OAST_TOKEN")
        self.timeout = timeout
        if not self.base_url:
            raise OastUnavailable(
                "no collector base_url (pass base_url= or set JARVIS_OAST_BASE). "
                "Refusing to fall back to loopback.")

    def start(self):
        return self

    def mint(self, cid: str) -> str:
        return f"{self.base_url}/{cid}"

    def poll(self, cid: str) -> list:
        req = urllib.request.Request(f"{self.poll_url}?cid={cid}")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8", "replace") or "[]")
        except Exception as e:
            raise OastUnavailable(f"collector poll failed: {type(e).__name__}: {e}")
        if isinstance(data, dict):
            data = data.get("hits", [])
        return list(data or [])

    def stop(self):
        return None
