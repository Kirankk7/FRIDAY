"""Authz Sweep — verdict cross-tenant authorization on EVERY gated mutation, not a sample of four.

WHY THIS EXISTS
  Hunt #37 proved cross-entity authz on 4 mutation families and the write-up was drifting toward
  "cross-tenant authz is enforced". The denominator was 219. The same gap closed hunt #35 with an
  untested corner. Testing 219 mutations by performing 219 successful writes is impossible: you
  cannot construct valid input for every one, and you should not try on a live target.

  The way out is that a GraphQL server tells you WHY it refused, and the reasons are distinguishable:

    CUSTOM_UN_AUTHORIZED   caller not entitled to this object   <- an authorization decision
    FORMAT                 selector malformed                   <- an input decision
    INVALID_VALUE (400)    schema-layer rejection
    no error, plain value  resolver ran, application logic answered

  So a probe does not need to SUCCEED to be readable. It needs to reach the authorization check and
  report which of those four states it hit. Send each mutation twice — once with the caller's own
  selector (control) and once with a selector the caller must not own (test) — and the pair is a
  verdict:

    control reaches resolver + test CUSTOM_UN_AUTHORIZED   -> ENFORCED
    control reaches resolver + test reaches resolver       -> FALSIFIED, escalate by hand
    control errors for any other reason                    -> UNREADABLE, never "safe"

PARANOIA
  Destructive verbs are excluded by name. A sweep that deletes things is not a sweep, it is an
  outage, and "no service degradation" sits in most programme rules. Mutations taking `Upload` are
  excluded too — a file cannot ride in a JSON variables block. Filing verbs (efile, submit, verify)
  are excluded because on a tax product they produce a statutory document.

  The generated batch points at the operator's OWN second account. That is the only target a
  selector sweep may ever be aimed at.

Offline, stdlib-only. Generates a batch; sends nothing itself.
"""
import json
import os
import re
import sys

try:
    from . import schema_surface as ss
except ImportError:                                  # run as a script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import schema_surface as ss

# Verbs excluded by name. `archive` and `start`/`initiate` were NOT in the first version, and the
# first live run archived the operator's own marker entity and kicked off a filing on it — which
# then made 119 of 122 control legs error on the next run. A control leg is a WRITE; any verb that
# changes an object's LIFECYCLE or STATE, not just one that deletes rows, has to sit on this list.
DESTRUCTIVE = re.compile(r"delete|remove|reset|clear|purge|revoke|cancel|drop|wipe|discard|"
                         r"unlink|deregister|terminate|efile|submit|verify|"
                         r"archive|initiate|start|revise|revert|generate|import|dismiss", re.I)


def _dummy(argtype, types, gate_arg, arg_name, own, fy):
    """A structurally valid value for an argument whose content does not matter."""
    if arg_name == gate_arg:
        return own
    t = types.get(argtype, {})
    kind = t.get("kind")
    if argtype in ("Int", "Long"):
        return 0
    if argtype in ("Float", "Decimal", "Percent", "Rupee", "PreciseRupee", "MoneyEx"):
        return "0"
    if argtype == "Boolean":
        return False
    if argtype == "FiscalYear":
        return fy
    if argtype in ("String", "Byte"):
        return "ZZPROBE"
    if argtype in ("ShortGuid", "Guid", "ID"):
        return own
    if argtype in ("DateTime", "DateTimeWrapper", "TimeStampWrapper"):
        return "2025-04-01T00:00:00Z"
    if kind == "ENUM":
        vals = t.get("enumValues") or []
        return vals[0] if vals else None
    if kind == "INPUT_OBJECT":
        return {}
    return None


def return_kinds(text, root_mutation="Mutation"):
    """Map mutation name -> its return KIND.

    A mutation returning an OBJECT needs a selection set; without one the server answers
    `SCALAR_LEAFS` on BOTH legs and the pair is unreadable. The first version of this module
    omitted selection sets and reported 109/122 UNREADABLE — a self-inflicted coverage hole that
    looked exactly like a hardened target. Read the return type; do not assume Boolean.
    """
    i = text.find('"kind":"OBJECT","name":"%s"' % root_mutation)
    if i < 0:
        return {}
    blk = ss._block(text, i)
    fi = blk.find('"fields":')
    if fi < 0:
        return {}
    seg = ss._bracket(blk, fi)
    out, skip_until = {}, 0
    for fm in re.finditer(r'\{"name":"(\w+)","description"', seg):
        if fm.start() < skip_until:
            continue
        name = fm.group(1)
        after = seg[fm.start():fm.start() + 12000]
        ai = after.find('"args":')
        if ai < 0:
            continue
        aseg = ss._bracket(after, ai)
        end = after.find(aseg, ai) + len(aseg)
        skip_until = fm.start() + end
        ti = after.find('"type":', end)
        if ti < 0:
            continue
        tblk = after[ti:ti + 600]
        kinds = re.findall(r'"kind":"(\w+)"', tblk)
        leaf = next((k for k in kinds if k not in ("NON_NULL", "LIST")), "SCALAR")
        out[name] = leaf
    return out


def plan(types, root_mutation="Mutation", gate_arg="entityId"):
    """Split every mutation into swept / skipped, with a reason for each skip."""
    root = types.get(root_mutation) or {"fields": []}
    swept, skipped = [], []
    for f in root["fields"]:
        names = [a["name"] for a in f["args"]]
        if gate_arg not in names:
            skipped.append((f["name"], "ungated - no %s arg" % gate_arg))
            continue
        if DESTRUCTIVE.search(f["name"]):
            skipped.append((f["name"], "destructive or filing verb - excluded by policy"))
            continue
        if any(a["type"] == "Upload" for a in f["args"]):
            skipped.append((f["name"], "takes Upload - not expressible in JSON variables"))
            continue
        swept.append(f)
    return swept, skipped


def build(types, swept, own, gate_arg="entityId", fy=2025, entity_index=0, rkinds=None):
    """Emit one op per mutation. The batch substitutes the selector at run time."""
    rkinds = rkinds or {}
    ops = []
    for f in swept:
        decls, args, variables = [], [], {}
        for a in f["args"]:
            gql_t = a["type"] + ("!" if a["nonNull"] else "")
            decls.append("$%s: %s" % (a["name"], gql_t))
            args.append("%s: $%s" % (a["name"], a["name"]))
            v = _dummy(a["type"], types, gate_arg, a["name"], own, fy)
            if a["name"] == "entityIndex":
                v = entity_index
            variables[a["name"]] = v
        sel = " { __typename }" if rkinds.get(f["name"]) in ("OBJECT", "INTERFACE",
                                                             "UNION") else ""
        ops.append({"name": f["name"],
                    "doc": "mutation P(%s){ %s(%s)%s }" % (", ".join(decls), f["name"],
                                                           ", ".join(args), sel),
                    "vars": variables})
    return ops


JS = r"""// AUTHZ SWEEP - generated by core/authz_sweep.py. Paste into the target-origin console.
// Each mutation is sent TWICE: own selector (control), then target selector (test).
(async()=>{
  const OPS = __OPS__;
  const GATE='__GATE__', OWN='__OWN__', TARGET='__TARGET__';
  const out={ENFORCED:[],FALSIFIED:[],UNREADABLE:[]};
  const post=async(doc,vars)=>{
    const r=await fetch('/graphql',{method:'POST',credentials:'include',
      headers:{'content-type':'application/json','accept':'*/*','X-Comolho-Client':'kiran_kk'},
      body:JSON.stringify({query:doc,variables:vars})});
    const t=await r.text(); let d=null; try{d=JSON.parse(t)}catch{}
    const errs=(d&&d.errors)||[];
    const code=errs.length?((errs[0].extensions&&errs[0].extensions.code)||'ERROR'):null;
    return {status:r.status, code, reached: r.status===200 && !code};
  };
  const gap=(ms)=>new Promise(r=>setTimeout(r,ms));
  for(const op of OPS){
    const c=await post(op.doc,{...op.vars,[GATE]:OWN});
    await gap(120);
    const x=await post(op.doc,{...op.vars,[GATE]:TARGET});
    await gap(120);
    let verdict;
    if(!c.reached)                            verdict='UNREADABLE';
    else if(x.code==='CUSTOM_UN_AUTHORIZED')  verdict='ENFORCED';
    else if(x.reached)                        verdict='FALSIFIED';
    else                                      verdict='UNREADABLE';
    out[verdict].push(op.name+'  ctrl='+(c.code||'ok')+'  test='+(x.code||'ok'));
    console.log(verdict.padEnd(11), op.name, '| ctrl', c.status, c.code||'ok',
                '| test', x.status, x.code||'ok');
  }
  console.log('=== TOTALS  swept '+OPS.length+
    ' | ENFORCED '+out.ENFORCED.length+
    ' | FALSIFIED '+out.FALSIFIED.length+
    ' | UNREADABLE '+out.UNREADABLE.length);
  if(out.FALSIFIED.length) console.log('FALSIFIED:'+String.fromCharCode(10)+out.FALSIFIED.join(String.fromCharCode(10)));
  window.SWEEP=out;
})();
"""


def main(argv):
    if len(argv) < 4:
        print("usage: authz_sweep.py <dump-file> <own-selector> <target-selector> "
              "[gate-arg] [fiscal-year] [entity-index] [out-dir]")
        return 2
    dump, own, target = argv[1], argv[2], argv[3]
    gate = argv[4] if len(argv) > 4 else "entityId"
    fy = int(argv[5]) if len(argv) > 5 else 2025
    idx = int(argv[6]) if len(argv) > 6 else 0
    outdir = argv[7] if len(argv) > 7 else "."

    text = open(dump, encoding="utf-8", errors="replace").read()
    types = ss.extract(text)
    swept, skipped = plan(types, gate_arg=gate)
    rkinds = return_kinds(text)
    ops = build(types, swept, own, gate_arg=gate, fy=fy, entity_index=idx, rkinds=rkinds)

    total = len(types.get("Mutation", {}).get("fields", []))
    if len(swept) + len(skipped) != total:
        raise SystemExit("self-check FAILED: swept %d + skipped %d != %d mutations"
                         % (len(swept), len(skipped), total))
    missing = [f["name"] for f in swept if f["name"] not in rkinds]
    if missing:
        raise SystemExit("self-check FAILED: no return kind for %d swept mutations, first: %s"
                         % (len(missing), missing[:5]))
    need_sel = sum(1 for f in swept if rkinds[f["name"]] in ("OBJECT", "INTERFACE", "UNION"))

    js = (JS.replace("__OPS__", json.dumps(ops))
            .replace("__GATE__", gate).replace("__OWN__", own).replace("__TARGET__", target))
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "authz_sweep.js"), "w", encoding="utf-8", newline="") as fh:
        fh.write(js)

    L = ["# AUTHZ SWEEP PLAN", "",
         "mutation root fields : %d" % total,
         "swept                : %d" % len(swept),
         "skipped              : %d" % len(skipped),
         "object-returning     : %d  (given a { __typename } selection set)" % need_sel,
         "self-check           : clean (swept + skipped == mutations; every swept has a return kind)",
         "",
         "## skipped, with reason"]
    for n, why in sorted(skipped):
        L.append("  %-46s %s" % (n, why))
    with open(os.path.join(outdir, "authz_sweep.md"), "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(L) + "\n")

    print("mutations %d | swept %d | skipped %d | self-check clean" % (total, len(swept),
                                                                       len(skipped)))
    print("wrote authz_sweep.js + authz_sweep.md to", outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
