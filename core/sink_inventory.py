"""Interpreter / Sink Inventory — the recon layer under the RCE class.

WHY THIS EXISTS
  Kiran, 2026-09-06: *"why are we not trying any remote code execution in our hunt... it is the most
  critical vuln and we do not even touch it."*

  The audit said he was half right, and the wrong half was the bad one. Class 10 EXISTS
  (`cmd/SSTI/XXE/path`) and on one hunt it was tested properly — four mechanisms, OAST controls, all
  four verdicted. But on an earlier hunt the row read:

      10 cmd/SSTI/XXE/path    UNTESTED    3 surfaces. Brief allows id/whoami only.

  The programme had granted `id` and `whoami` in writing and we sent neither. On a third it read
  "no sink identified" — which our own notes already flagged as *a search, not a verdict*.

  We enumerate routes, selectors, gates and input fields. We had never enumerated SINKS. Without
  that list, "no sink" cannot be told apart from "did not look", so the highest-impact class was the
  one most often decided on vibes.

WHAT A SINK IS
  A place where attacker bytes reach something that INTERPRETS them:

      INPUT -> TRANSFORMATION -> INTERPRETER -> EXECUTION BOUNDARY -> OBSERVABLE

  The inventory answers three questions in order, and refuses to skip one:
      1. which interpreters exist on this target?          (FOUND)
      2. which of them did I actually reach with input?    (TESTED, with a control)
      3. what is the minimum sufficient proof?             (the ladder in HUNT_PROTOCOL §4)

THE RULE THIS ENFORCES
  `found=0` is only meaningful when `searched=True`. A kind that was never looked for is NOT_SEARCHED
  and can never print as N/A — the same discipline as `gate=None` in route_inventory, and the same
  failure shape as pb0745: a reader's silence is a claim about the reader until proven otherwise.

Offline, stdlib-only, no network. Detection is a LEAD; only a probe with a passing control verdicts.
"""
import re

# The interpreter boundaries worth asking about. Each is a distinct execution semantic, not a
# payload family — the payloads live in the playbook, the boundaries live here.
KINDS = (
    "command",          # anything that shells out: convert, thumbnail, OCR, AV scan, zip
    "template",         # server-side template / expression evaluation
    "deserialization",  # java, php, pickle, ViewState, YAML, BSON
    "document",         # PDF / DOCX / XLSX / CSV parsing and conversion
    "media",            # image, audio, video processing
    "archive",          # zip / tar extraction (zip-slip, symlink, quota)
    "build",            # package or dependency resolution triggered by a request
    "job",              # background worker / workflow / scheduled execution
    "plugin",           # extension, script, or user-supplied code hooks
    "script",           # explicit server-side script/eval endpoints
)

# Signals visible in a capture. Deterministic and deliberately conservative: a hit here means
# "ask about this", never "this is vulnerable".
_CT_XML = re.compile(r"\b(?:xml|xhtml)\b", re.I)
_CT_YAML = re.compile(r"\byaml\b", re.I)
_CT_MULTIPART = re.compile(r"multipart/form-data", re.I)

_SERIALIZED = (
    (re.compile(r"rO0AB"), "java-serialized (rO0AB)"),
    (re.compile(r"\bO:\d+:\""), "php-serialized (O:n:)"),
    (re.compile(r"__VIEWSTATE"), ".NET ViewState"),
    (re.compile(r"\bgASV|\x80\x04\x95"), "python pickle"),
    (re.compile(r"\bBZh9|\bH4sI"), "compressed blob"),
)

_PARAM_HINTS = (
    ("template", re.compile(r"templ|layout|render|body_html|expr|formula|"
                            r"handlebars|jinja|liquid|freemarker|subject", re.I)),
    # `options`, `args`, and bare `exec`/`script` matched ordinary routes (/setup/api/v1/options)
    # and buried the real sinks. sweep.py learned the same generic-word trap for path params:
    # "bare name/page matched operationName/appName/per_page ... under ~100 FPs".
    ("command",  re.compile(r"\bcmd\b|command|/exec\b|shell|binary|"
                            r"convert|ffmpeg|imagemagick|thumbnailer", re.I)),
    ("document", re.compile(r"\bpdf\b|docx?|xlsx?|csv|invoice|report|statement|export|"
                            r"printing|print_", re.I)),
    ("media",    re.compile(r"image|thumb|avatar|logo|photo|resize|crop|video|audio", re.I)),
    ("archive",  re.compile(r"\bzip\b|tar\b|gz\b|archive|bundle|extract|unpack", re.I)),
    ("build",    re.compile(r"package|dependenc|lockfile|manifest|requirements|npm|pip|maven", re.I)),
    ("job",      re.compile(r"jobs?\b|job_|worker|queue|schedule|cron|task_|workflow|pipeline|"
                            r"trigger|/run\b|run_|execute", re.I)),
    ("plugin",   re.compile(r"plugin|extension|addon|hook|webhook_transform|custom_code", re.I)),
    ("script",   re.compile(r"\beval\b|\bscript\b|sandbox|lambda|function_body|user_code", re.I)),
)

# Paths that can never be an interpreter sink: telemetry proxies, static asset bundles, and plain
# media files served by a CDN. A GET of /videos/x.mp4 is a download, not a media pipeline.
_NOISE = re.compile(
    r"heap-proxy|/static-assets/|/application-assets/|/_next/|\.(?:js|css|map|woff2?|ico|png|jpe?g|"
    r"gif|svg|webp|mp4|webm|mp3|wasm)$", re.I)

_UPLOAD_EXT = {
    ".pdf": "document", ".doc": "document", ".docx": "document", ".xls": "document",
    ".xlsx": "document", ".csv": "document", ".rtf": "document", ".odt": "document",
    ".png": "media", ".jpg": "media", ".jpeg": "media", ".gif": "media", ".svg": "media",
    ".webp": "media", ".tif": "media", ".tiff": "media", ".mp4": "media", ".mp3": "media",
    ".zip": "archive", ".tar": "archive", ".gz": "archive", ".7z": "archive", ".rar": "archive",
    ".xml": "document", ".yaml": "deserialization", ".yml": "deserialization",
}


_ID_SEG = re.compile(r"/(?:\d+|[0-9A-HJKMNP-TV-Z]{20,}|[0-9a-f]{8}-[0-9a-f-]{20,})(?=/|$)", re.I)


def _norm_where(where):
    """Collapse a `METHOD https://host/path?query` label to METHOD + id-normalised path, so the same
    ROUTE hit N times counts once."""
    parts = str(where).split(" ", 1)
    meth, url = (parts[0], parts[1]) if len(parts) == 2 else ("", str(where))
    path = url.split("?", 1)[0]
    for pre in ("https://", "http://"):
        if path.startswith(pre):
            path = "/" + path[len(pre):].split("/", 1)[-1] if "/" in path[len(pre):] else "/"
    return meth + " " + _ID_SEG.sub("/{id}", path)


class SinkInventory:
    """One row per interpreter kind. Every kind starts NOT_SEARCHED — an empty inventory is a
    statement about the hunt, never about the target."""

    def __init__(self):
        self._k = {k: {"kind": k, "searched": False, "sinks": [], "tested": 0,
                       "control_passed": None, "verdict": "NOT TESTED", "note": ""}
                   for k in KINDS}

    # ---------------------------------------------------------------- recording ----

    def searched(self, *kinds):
        """Record that these kinds were actually looked for. Without this, `found 0` prints as
        NOT_SEARCHED and the class cannot be closed."""
        for k in (kinds or KINDS):
            if k in self._k:
                self._k[k]["searched"] = True
        return self

    def add(self, kind, where, evidence="", searched=True):
        """Record one candidate sink. `where` is the endpoint/param; `evidence` is why you think an
        interpreter is behind it."""
        if kind not in self._k:
            raise ValueError("unknown sink kind %r; known: %s" % (kind, ", ".join(KINDS)))
        row = self._k[kind]
        if searched:
            row["searched"] = True
        # One ROUTE is one sink, however many times the capture hit it. Keying on the raw URL made
        # 35 replays of /setup/api/v1/options read as 35 command sinks -- a count that inflates
        # silently is the pb0712 failure, and the denominator is the whole point of this module.
        key = (_norm_where(where), evidence)
        if key not in [(_norm_where(s["where"]), s["evidence"]) for s in row["sinks"]]:
            row["sinks"].append({"where": where, "evidence": evidence, "probed": False})
        return self

    def probed(self, kind, where, control_passed, verdict, note=""):
        """Record the OUTCOME of reaching a sink. A probe without a passing control is UNREADABLE —
        it never becomes ENFORCED and never becomes a finding."""
        row = self._k[kind]
        for s in row["sinks"]:
            if s["where"] == where:
                s["probed"] = True
        row["tested"] = sum(1 for s in row["sinks"] if s["probed"])
        row["control_passed"] = control_passed
        row["verdict"] = verdict if control_passed else "UNREADABLE"
        if note:
            row["note"] = note
        return self

    # ---------------------------------------------------------------- reading ----

    def kinds(self):
        return [dict(v, sinks=list(v["sinks"])) for v in self._k.values()]

    def denominator(self):
        """(sinks_found, sinks_probed, kinds_searched, kinds_total) — the four numbers the class row
        needs. None of them can be inferred from the number of payloads sent."""
        found = sum(len(v["sinks"]) for v in self._k.values())
        probed = sum(v["tested"] for v in self._k.values())
        searched = sum(1 for v in self._k.values() if v["searched"])
        return found, probed, searched, len(self._k)

    def unsearched(self):
        return [k for k, v in self._k.items() if not v["searched"]]

    def high_value(self):
        """Kinds with a found sink — the target-selection signal. A target with document/archive/
        media/job sinks has an execution surface worth prioritising; a pure CRUD API does not."""
        return sorted(k for k, v in self._k.items() if v["sinks"])

    def matrix_rows(self):
        """Rows for `workspace/coverage/<target>_matrix.md`, under the RCE class."""
        out = ["| sink kind | found | probed | control | verdict |", "|---|---|---|---|---|"]
        for k in KINDS:
            v = self._k[k]
            if not v["searched"]:
                out.append("| %s | - | - | - | **NOT SEARCHED** |" % k)
                continue
            if not v["sinks"]:
                out.append("| %s | 0 | - | - | N/A (searched, none present) |" % k)
                continue
            ctrl = "-" if v["control_passed"] is None else ("pass" if v["control_passed"] else "FAIL")
            out.append("| %s | %d | %d | %s | %s |"
                       % (k, len(v["sinks"]), v["tested"], ctrl, v["verdict"]))
        f, p, s, t = self.denominator()
        out += ["", "**RCE class denominator:** %d sink(s) found, %d probed; %d/%d kinds searched."
                % (f, p, s, t)]
        if self.unsearched():
            out.append("⚠️ never searched: %s — these are UNMEASURED, not absent."
                       % ", ".join(self.unsearched()))
        return out


def from_capture(recs):
    """Deterministic first pass over a capture -> a populated SinkInventory.

    Marks every kind as SEARCHED, because the capture was genuinely scanned for all of them. That is
    the whole point: after this runs, `found 0` is a real answer instead of a shrug. It is still only
    a first pass — a sink the capture never exercised is invisible here, so the bundle/route/docs
    sweep must feed it too.
    """
    inv = SinkInventory()
    inv.searched()
    for r in recs or []:
        where = "%s %s" % (r.get("method", "?"), r.get("url", r.get("path", "?")))
        req_h = {k.lower(): v for k, v in (r.get("req_headers") or {}).items()}
        ct = req_h.get("content-type", "")
        body = r.get("req_body") or ""

        if _CT_MULTIPART.search(ct):
            inv.add("document", where, "multipart upload — what parses the file?")
        if _CT_XML.search(ct):
            # XML is a PARSER boundary (XXE, its own class); it is a DESERIALIZATION boundary only
            # when the payload is an object graph, so it is recorded as a lead, not as both.
            inv.add("deserialization", where, "XML body — object graph or plain document?")
        if _CT_YAML.search(ct):
            inv.add("deserialization", where, "YAML body — unsafe load reaches constructors")
        for rx, label in _SERIALIZED:
            if rx.search(body):
                inv.add("deserialization", where, "serialized blob: " + label)
                break

        # The PATH carries as much sink signal as the parameters do — /pdf/generate, /jobs/run,
        # /import, /convert. Scanning only param names missed every one of them, which is how a
        # capture full of interpreters can still report "no sink identified".
        # PATH ONLY -- matching the query string made a telemetry beacon's random `s=` value look
        # like a command sink. sweep.py already excludes third-party/self-hosted telemetry; the same
        # exclusions belong here or the denominator is noise.
        path = str(r.get("url", r.get("path", ""))).split("?", 1)[0]
        if _NOISE.search(path):
            continue
        params = r.get("params") or {}
        names = list(params) if isinstance(params, dict) else list(params)
        for kind, rx in _PARAM_HINTS:
            if rx.search(path):
                inv.add(kind, where, "path suggests a %s sink" % kind)
                continue
            for n in names:
                if rx.search(str(n)):
                    inv.add(kind, where, "param %r suggests a %s sink" % (n, kind))
                    break
        for n, v in (params.items() if isinstance(params, dict) else []):
            ext = str(v).lower().strip()
            for e, kind in _UPLOAD_EXT.items():
                if ext.endswith(e):
                    inv.add(kind, where, "param %r carries a %s filename" % (n, e))
                    break
    return inv
