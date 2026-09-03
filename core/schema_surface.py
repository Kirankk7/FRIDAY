"""Schema Surface — turn a GraphQL introspection dump into a COMPLETE, testable attack surface.

WHY THIS EXISTS
  On hunt #37 the app's own JS bundle shipped a full `__schema` payload. A first pass mined only the
  String-typed fields of INPUT_OBJECTs — 365 of them — and called that "the input inventory". That
  was a partial read, and partial reads are how a hunt closes with an untested corner. A GraphQL
  schema exposes attacker-controlled values in FIVE distinct places, and only one of them is
  "String fields on input objects":

    1. ARGUMENTS on root fields and on nested fields   <- selectors live here (the tenant id!)
    2. INPUT_OBJECT fields, of EVERY scalar type       <- not just String
    3. ENUM values                                     <- privileged members are a lane of their own
    4. CUSTOM SCALARS                                  <- hand-written parsers, rarely fuzzed
    5. the Query root itself                           <- the read surface

  This module extracts all five and emits a per-class test matrix, so "did we test everything?" is a
  file you can read rather than a claim you have to trust.

PARSING NOTE
  The dump is a JS string literal inside a bundle: newlines are doubly escaped, so `json.loads` on
  the raw slice fails on the first description containing `\\n`. Do not fight it. Scan for each
  type's `"kind":"X","name":"Y"` marker, take its balanced brace block, and regex inside that bounded
  window. Bounded scans also avoid the catastrophic backtracking a naive pattern hits on 1.3 MB.

Offline, stdlib-only. Sends nothing.
"""
import json
import os
import re
import sys
import collections

KINDS = ("OBJECT", "INPUT_OBJECT", "ENUM", "INTERFACE", "SCALAR", "UNION")
BUILTIN_SCALARS = {"String", "Int", "Float", "Boolean", "ID"}


def _block(text, at, cap=400000):
    """Balanced-brace block containing position `at`."""
    start = text.rfind("{", 0, at)
    if start < 0:
        return ""
    depth, j, limit = 0, start, start + cap
    while j < len(text) and j < limit:
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
        j += 1
    return text[start:min(len(text), limit)]


def _bracket(text, at, cap=200000):
    """Balanced-bracket list starting at the '[' on/after `at`."""
    i = text.find("[", at)
    if i < 0:
        return ""
    depth, j, limit = 0, i, i + cap
    while j < len(text) and j < limit:
        c = text[j]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
        j += 1
    return text[i:min(len(text), limit)]


def _typename(seg):
    """Innermost named type from a nested NON_NULL/LIST/ofType chain."""
    names = re.findall(r'"name":(?:"(\w+)"|null)', seg)
    for n in names:
        if n and n not in ("ofType",):
            return n
    return "?"


def extract(text):
    """Return {types: {...}} from an introspection dump embedded in arbitrary text."""
    types = {}
    for kind in KINDS:
        pos = 0
        marker = '"kind":"%s"' % kind
        while True:
            i = text.find(marker, pos)
            if i < 0:
                break
            pos = i + 1
            m = re.search(r'"name":"(\w+)"', text[i:i + 240])
            if not m:
                continue
            name = m.group(1)
            blk = _block(text, i)
            if len(blk) < 40:
                continue
            rec = types.setdefault(name, {"kind": kind, "fields": [], "inputFields": [],
                                          "enumValues": []})
            if kind in ("OBJECT", "INTERFACE"):
                fi = blk.find('"fields":')
                if fi >= 0:
                    seg = _bracket(blk, fi)
                    # A field's own args are `{"name":...}` objects too, so a naive scan promotes
                    # every ARGUMENT into a sibling FIELD and silently inflates the count. Track the
                    # span of each args list and skip any match that falls inside one.
                    skip_until = 0
                    for fm in re.finditer(r'\{"name":"(\w+)","description"', seg):
                        if fm.start() < skip_until:
                            continue
                        fname = fm.group(1)
                        after = seg[fm.start():fm.start() + 8000]
                        ai = after.find('"args":')
                        args = []
                        if ai >= 0:
                            aseg = _bracket(after, ai)
                            skip_until = fm.start() + after.find(aseg, ai) + len(aseg)
                            for am in re.finditer(r'\{"name":"(\w+)","description"', aseg):
                                atail = aseg[am.start():am.start() + 400]
                                args.append({"name": am.group(1), "type": _typename(atail[len(am.group(0)):]),
                                             "nonNull": '"kind":"NON_NULL"' in atail})
                        if not any(f["name"] == fname for f in rec["fields"]):
                            rec["fields"].append({"name": fname, "args": args})
            elif kind == "INPUT_OBJECT":
                fi = blk.find('"inputFields":')
                if fi < 0:
                    fi = blk.find('"fields":')
                if fi >= 0:
                    seg = _bracket(blk, fi)
                    for fm in re.finditer(r'\{"name":"(\w+)","description"', seg):
                        tail = seg[fm.start():fm.start() + 400]
                        entry = {"name": fm.group(1), "type": _typename(tail[len(fm.group(0)):]),
                                 "nonNull": '"kind":"NON_NULL"' in tail}
                        if not any(f["name"] == entry["name"] for f in rec["inputFields"]):
                            rec["inputFields"].append(entry)
            elif kind == "ENUM":
                fi = blk.find('"enumValues":')
                if fi >= 0:
                    seg = _bracket(blk, fi)
                    vals = re.findall(r'\{"name":"(\w+)","description"', seg)
                    rec["enumValues"] = sorted(set(rec["enumValues"]) | set(vals))
    return types


# ---------------------------------------------------------------- surface -----
SENSITIVE_ENUM = re.compile(r"admin|support|agent|owner|super|internal|staff|write|edit|"
                            r"prefill|import|verified|system|root|manage", re.I)
SELECTOR = re.compile(r"(^|_)(id|uuid|guid|index|key|ref|slug|token)$|Id$|Index$|Uuid$|Guid$", re.I)
URLISH = re.compile(r"url|link|callback|redirect|webhook|endpoint|host|domain|site", re.I)
FILEISH = re.compile(r"file|path|attachment|document|s3|upload|image|logo|name$", re.I)
TEXTISH = re.compile(r"name|desc|remark|comment|note|address|title|label|nature|trade|firm|message", re.I)
IDENTISH = re.compile(r"code|number|no$|ref|ifsc|swift|pan|tan|gstin|acknowledg|account", re.I)


def surface(types, root_query="Query", root_mutation="Mutation", gate_arg=None):
    """Classify every attacker-controlled value in the schema."""
    out = {"args": [], "inputs": [], "enums": [], "scalars": [], "roots": {}}
    custom = [n for n, t in types.items()
              if t["kind"] == "SCALAR" and n not in BUILTIN_SCALARS]
    out["scalars"] = sorted(custom)

    for tname, t in types.items():
        if t["kind"] in ("OBJECT", "INTERFACE"):
            for f in t["fields"]:
                for a in f["args"]:
                    out["args"].append({"type": tname, "field": f["name"], "arg": a["name"],
                                        "argType": a["type"], "nonNull": a["nonNull"]})
        elif t["kind"] == "INPUT_OBJECT":
            for f in t["inputFields"]:
                out["inputs"].append({"input": tname, "field": f["name"],
                                      "fieldType": f["type"], "nonNull": f["nonNull"]})
        elif t["kind"] == "ENUM":
            hot = [v for v in t["enumValues"] if SENSITIVE_ENUM.search(v)]
            out["enums"].append({"enum": tname, "count": len(t["enumValues"]),
                                 "values": t["enumValues"], "sensitive": hot})

    for role, rname in (("query", root_query), ("mutation", root_mutation)):
        r = types.get(rname)
        if not r:
            continue
        fields = []
        for f in r["fields"]:
            names = [a["name"] for a in f["args"]]
            fields.append({"field": f["name"], "args": names,
                           "gated": bool(gate_arg) and gate_arg in names})
        out["roots"][role] = fields
    return out


def report(s, gate_arg=None):
    L = []
    q = s["roots"].get("query", [])
    m = s["roots"].get("mutation", [])
    L.append("# SCHEMA ATTACK SURFACE\n")
    L.append("query root fields    : %d" % len(q))
    L.append("mutation root fields : %d" % len(m))
    if gate_arg:
        ung = [f for f in m if not f["gated"]]
        L.append("mutations WITHOUT `%s` : %d  <- outside the tenant gate" % (gate_arg, len(ung)))
        for f in ung:
            L.append("    %-40s args=%s" % (f["field"], ",".join(f["args"]) or "-"))
    L.append("\narguments (all fields) : %d" % len(s["args"]))
    L.append("input-object fields    : %d" % len(s["inputs"]))
    L.append("enums                  : %d" % len(s["enums"]))
    L.append("custom scalars         : %d  %s" % (len(s["scalars"]), ", ".join(s["scalars"][:20])))

    bytype = collections.Counter(i["fieldType"] for i in s["inputs"])
    L.append("\ninput field types: " + ", ".join("%s=%d" % kv for kv in bytype.most_common(15)))

    L.append("\n## SELECTOR-SHAPED ARGUMENTS (authz / IDOR lane)")
    sel = [a for a in s["args"] if SELECTOR.search(a["arg"])]
    L.append("  %d arguments look like object selectors" % len(sel))
    for a in sel[:40]:
        L.append("    %-26s %-30s %s" % (a["arg"], a["type"] + "." + a["field"], a["argType"]))

    L.append("\n## ENUMS WITH PRIVILEGED-LOOKING MEMBERS (role / provenance lane)")
    for e in sorted(s["enums"], key=lambda x: -len(x["sensitive"])):
        if e["sensitive"]:
            L.append("    %-34s %s" % (e["enum"], ", ".join(e["sensitive"][:12])))

    L.append("\n## CUSTOM SCALARS (hand-written parsers — rarely fuzzed)")
    for sc in s["scalars"]:
        L.append("    %s" % sc)

    for label, rx in (("URL-ish (ssrf / open-redirect)", URLISH),
                      ("FILE-ish (traversal / upload)", FILEISH),
                      ("TEXT-ish (xss / ssti)", TEXTISH),
                      ("IDENT-ish (sqli / nosqli)", IDENTISH)):
        hits = [i for i in s["inputs"] if rx.search(i["field"])]
        hits += [{"input": a["type"] + "." + a["field"], "field": a["arg"],
                  "fieldType": a["argType"]} for a in s["args"] if rx.search(a["arg"])]
        L.append("\n## %s : %d" % (label, len(hits)))
        for h in hits[:50]:
            L.append("    %-34s %-28s %s" % (h["field"], h["input"], h["fieldType"]))
    return "\n".join(L)


def selfcheck(types, root_mutation="Mutation"):
    """Fail LOUDLY when the parse has gone wrong.

    The first version of this module promoted every ARGUMENT into a sibling FIELD, inflating the
    mutation count from 219 to 374 without a single error. It was caught only because a human
    remembered a previous number. An extractor that cannot fail loudly manufactures verdicts, so
    these are the cheap invariants that catch that class of bug.
    """
    problems = []
    root = types.get(root_mutation)
    if not root:
        return ["no %s type found — is this an introspection dump?" % root_mutation]
    names = [f["name"] for f in root["fields"]]
    allargs = {a["name"] for f in root["fields"] for a in f["args"]}
    bleed = sorted(set(names) & allargs)
    if bleed:
        problems.append("ARG/FIELD BLEED: %d names are both a root field and an argument -> %s"
                        % (len(bleed), ", ".join(bleed[:12])))
    argless = [n for n, f in zip(names, root["fields"]) if not f["args"]]
    if len(argless) > len(names) * 0.5:
        problems.append("%d/%d root fields parsed with NO args — args extraction likely failed"
                        % (len(argless), len(names)))
    if len(names) < 5:
        problems.append("only %d root fields parsed — block bounding likely too small" % len(names))
    return problems


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        print("usage: python -m core.schema_surface <bundle-or-dump> [--gate <argName>] [--out <dir>]")
        return 1
    src = argv[1]
    gate = None
    outdir = "."
    if "--gate" in argv:
        gate = argv[argv.index("--gate") + 1]
    if "--out" in argv:
        outdir = argv[argv.index("--out") + 1]
    text = open(src, encoding="utf-8", errors="ignore").read()
    types = extract(text)
    print("types parsed: %d" % len(types))
    probs = selfcheck(types)
    if probs:
        print("\n!! SELF-CHECK FAILED — do not trust these numbers:")
        for p in probs:
            print("   " + p)
        print()
    else:
        print("self-check: clean")
    s = surface(types, gate_arg=gate)
    os.makedirs(outdir, exist_ok=True)
    json.dump(s, open(os.path.join(outdir, "schema_surface.json"), "w", encoding="utf-8"), indent=1)
    rep = report(s, gate_arg=gate)
    open(os.path.join(outdir, "schema_surface.md"), "w", encoding="utf-8").write(rep)
    print(rep[:3000])
    print("\nwrote schema_surface.json + schema_surface.md to %s" % outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
