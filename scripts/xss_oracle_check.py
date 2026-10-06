#!/usr/bin/env python3
"""Two-leg control for the DOM-XSS execution oracle. Both legs must pass before any verdict.

HUNT_PROTOCOL §7 names the failure this exists to prevent, by hunt and by class: a class closed
at 0 of 40 routes on the stated ground that execution could not be confirmed, while a working
execution oracle sat in the codebase with its test skipping silently.

The existing regression test has a POSITIVE leg only - a raw-reflecting server that must confirm.
That proves the oracle can say yes. It cannot show the oracle is capable of saying no, and an
oracle that can only say yes turns every probe into a finding.

    POSITIVE  raw reflection, payload lands unescaped  -> MUST confirm execution
    NEGATIVE  same payload, HTML-escaped on the way out -> MUST NOT confirm

A negative leg that confirms means the oracle is reporting execution where none happened, and
every ENFORCED it has ever issued is void. A positive leg that fails means the browser is
unavailable and the correct verdict is UNAVAILABLE - never "clean".

    python scripts/xss_oracle_check.py
"""
import html
import http.server
import os
import sys
import threading
import urllib.parse

# run from anywhere: the repo root has to be importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _serve(escape: bool):
    """A tiny server that reflects ?q= either raw or HTML-escaped. Returns (port, shutdown)."""
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            v = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("q", [""])[0]
            if escape:
                v = html.escape(v, quote=True)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(("<html><body><div>%s</div></body></html>" % v).encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1], srv.shutdown


def _run(escape: bool, timeout: int = 20):
    """-> (available, confirmed, message)."""
    from agents.ultron import ultron_agent as _ult
    from core import net as _net
    from core.scope_guard import Scope

    port, stop = _serve(escape)
    saved = _net._GUARD
    try:
        # The oracle fails closed without a declared scope - exactly as a hunt does.
        _net.configure(Scope(in_scope=("127.0.0.1",)))
        r = _ult.ultron_agent.xss_confirm(
            "http://127.0.0.1:%d/s?q=x" % port, param="q", timeout=timeout)
    finally:
        _net._GUARD = saved
        stop()

    if not r.get("success"):
        return False, False, r.get("message", "")
    confirmed = any(f.get("template") == "xss-confirmed"
                    for f in (r.get("data") or {}).get("findings", []))
    return True, confirmed, r.get("message", "")


def main():
    print("=== DOM-XSS execution oracle, two-leg control")

    pos_avail, pos_conf, pos_msg = _run(escape=False)
    if not pos_avail:
        print("  POSITIVE  UNAVAILABLE - %s" % pos_msg[:90])
        print("\n  VERDICT: oracle UNAVAILABLE (no headless browser).")
        print("  A class closed with this oracle missing is UNTESTABLE, never clean.")
        print("  Repair: install the browser runtime, then re-run this check.")
        return 2
    print("  POSITIVE  raw reflection      -> confirmed=%s  %s"
          % (pos_conf, "PASS" if pos_conf else "*** FAIL ***"))

    neg_avail, neg_conf, neg_msg = _run(escape=True)
    print("  NEGATIVE  HTML-escaped        -> confirmed=%s  %s"
          % (neg_conf, "PASS" if not neg_conf else "*** FAIL ***"))

    ok = pos_conf and not neg_conf
    print("\n  VERDICT: %s" % ("oracle USABLE - it can say yes AND no" if ok else
                               "oracle NOT TRUSTWORTHY - do not issue verdicts with it"))
    if pos_conf and neg_conf:
        print("  The negative leg confirmed execution where the payload was escaped.")
        print("  Every ENFORCED this oracle has issued is void until that is fixed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
