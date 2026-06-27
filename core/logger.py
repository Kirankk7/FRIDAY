"""
Phase 51 #4 — Structured logging.

Central rotating logger + a stdout/stderr tee so ALL existing print() output is
captured to jarvis.log (rotating, 5MB x 3) while still showing on the console.

Usage:
    from core.logger import log, install_tee
    install_tee()          # call once at app startup (after stdout reconfigure)
    log.info("message")    # structured logging for new code
"""
import sys
import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = "jarvis.log"

# ── Central rotating logger ───────────────────────────────────────────────────
log = logging.getLogger("jarvis")
if not log.handlers:
    log.setLevel(logging.INFO)
    _fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    log.addHandler(_fh)
    log.propagate = False


# ── stdout/stderr tee -> routes print() lines into the logger ──────────────────
class _StreamToLogger:
    """Wrap a stream: echo to console AND emit complete lines to the logger."""

    def __init__(self, orig_stream, level):
        self._orig = orig_stream
        self._level = level
        self._buf = ""

    def write(self, data):
        # Always preserve console output
        try:
            self._orig.write(data)
        except Exception:
            pass
        # Buffer and flush complete lines into the logger
        try:
            self._buf += data
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                if line.strip():
                    log.log(self._level, line.rstrip())
        except Exception:
            pass

    def flush(self):
        try:
            self._orig.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        # Delegate everything else (reconfigure, encoding, isatty, ...) to original
        return getattr(self._orig, name)


_tee_installed = False


def install_tee():
    """Redirect stdout->INFO, stderr->ERROR through the logger. Idempotent."""
    global _tee_installed
    if _tee_installed:
        return
    sys.stdout = _StreamToLogger(sys.stdout, logging.INFO)
    sys.stderr = _StreamToLogger(sys.stderr, logging.ERROR)
    _tee_installed = True
    log.info("=== JARVIS logging started (jarvis.log, rotating 5MB x 3) ===")
