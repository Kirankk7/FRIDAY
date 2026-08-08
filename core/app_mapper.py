"""core/app_mapper.py — Application Semantic Mapper (Cyber-VNext Tier-1 substrate).

`sweep.ingest` dumps a FLAT `object_ids` list. The identity-replay oracle needs more: for every
id-bearing parameter it must know the SEMANTIC ROLE — is this the tenant boundary, a user boundary,
an object id, or a public catalog id? — plus the VALUE SCHEME (sequential = enumerable; composite =
a base64 GUID that *embeds* the tenant id, so cross-tenant ids are craftable).

Twenty-five hunts kept forcing hand-written parsers to answer exactly that ("which id is the tenant
boundary on New Relic?" → accountId, by hand, with a throwaway heredoc). That is the rule-#6 pain this
removes. Deterministic, reuses sweep's parser (no new capture parser), offline — sends nothing.

Consumed next by the replay oracle: tenant_id + object_id + enumerable = the cross-boundary test set.
"""
import re
import base64

from core import sweep
from core.hunt_mode import _UUID, _USER_ID, _PUBLIC_ID

# An id-SHAPED key: ends in id/uuid/guid/number/ref/token/key/hash, singular OR plural (camelCase or
# snake). Dogfood on NR: the real tenant param `account_ids` (plural) is dropped by the singular-only
# _IDKEY, and firmographic noise (`company_annual_revenue`, `numberOfAccounts`) is NOT id-shaped so it
# must never be collected. Requiring id-shape BEFORE role-classifying is what kills both.
_IDISH = re.compile(r"(?:^|[_.])(?:[a-z][a-z0-9]*?)?(?:id|uuid|guid|number|reference|ref|token|key|hash)s?$", re.I)
# The tenant boundary Wesley's B2B lens cares about + NR proved (accountId / organizationId): the id
# that scopes a whole org/account, not a single user. Distinct from _USER_ID (a person within a tenant).
_TENANT_KEY = re.compile(r"account|organi[sz]ation|\borg\b|company|tenant|workspace|realm|\bteam\b", re.I)
_USER_KEY = re.compile(r"\buser|\buid\b|member|customer|party|owner|staff|employee|person|profile", re.I)


def _try_composite(v: str):
    """A base64/base64url GUID that decodes to `<digits>|WORD|...` embeds a tenant id in plaintext.

    Seen in the wild on monitoring platforms: an entity GUID base64-decodes to `<tenant>|TYPE|SUBTYPE|<id>`
    (e.g. `1000|VIZ|DASHBOARD|55`). The leading number IS the tenant/account id, so a cross-tenant GUID is
    craftable by rewriting it — no guessing. Flag it so the replay oracle can swap the embedded tenant.
    """
    if not v or len(v) < 12 or len(v) > 512:
        return None
    s = v.replace("-", "+").replace("_", "/")
    try:
        dec = base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")
    except Exception:
        return None
    m = re.match(r"^(\d{3,})\|[A-Za-z]", dec)
    return {"decoded": dec[:80], "embedded_tenant": m.group(1)} if m else None


def _scheme(values: list) -> str:
    vals = [v for v in values if v]
    if not vals:
        return "unknown"
    if all(_UUID.fullmatch(v) for v in vals):
        return "uuid"
    if all(re.fullmatch(r"\d+", v) for v in vals):
        return "sequential_int"          # enumerable — every prior class becomes bulk-exploitable
    if _try_composite(vals[0]):
        return "composite"               # base64 GUID embedding a tenant/object id
    return "opaque"


def _role(key: str) -> str:
    """Semantic role of an id key. Order matters: tenant before user before generic object; public last-guard."""
    base = key.lower()
    if _PUBLIC_ID.search(base):
        return "public_id"               # product/category/sku = catalog, NOT an ownership boundary
    if _TENANT_KEY.search(base):
        return "tenant_id"
    if _USER_KEY.search(base) or _USER_ID.search(base):
        return "user_id"
    return "object_id"                   # id-shaped (caller already gated on _IDISH) but no owner word


def map_application(src) -> dict:
    """Capture (HAR path/dict or Burp XML path) -> per-id semantic classification. Offline; sends nothing."""
    try:
        recs = sweep._records(src)
    except FileNotFoundError:
        return {"success": False, "message": "I couldn't find that capture file, boss.", "data": {}}
    except Exception as e:
        return {"success": False, "message": f"That capture didn't parse: {str(e)[:80]}", "data": {}}
    _t = sweep._target_domains(recs)
    recs = [r for r in recs if sweep._in_scope(r, _t)]        # target-aware: keeps the target even
    if not recs:
        return {"success": False, "message": "No in-scope requests in that capture.", "data": {}}

    # key -> {role, values:set, endpoints:set, locations:set}
    acc: dict = {}

    def _note(key, val, endpoint, loc):
        e = acc.setdefault(key, {"values": set(), "endpoints": set(), "locations": set()})
        if val:
            e["values"].add(str(val)[:120])
        e["endpoints"].add(endpoint)
        e["locations"].add(loc)

    for r in recs:
        ep = f"{r['method']} {r['host']}{r['path'].split('?')[0]}"
        for coll, val in sweep._path_ids(r["path"]):
            _note(f"path:{coll}", val, ep, "path")
        for k, v in sweep._params(r).items():
            if _IDISH.search(k.split(".")[-1]):
                _note(k, v, ep, "query/body")

    ids = []
    for key, e in acc.items():
        vals = sorted(e["values"])
        role = _role(key)
        scheme = _scheme(vals)
        comp = _try_composite(vals[0]) if vals else None
        owner = role in ("tenant_id", "user_id", "object_id")
        ids.append({
            "name": key,
            "role": role,
            "scheme": scheme,
            "ownership_sensitive": owner,
            "authz_sensitive": role in ("tenant_id", "user_id"),   # cross-boundary = highest value
            "enumerable": scheme == "sequential_int",
            "embedded_tenant": comp["embedded_tenant"] if comp else None,
            "endpoints": sorted(e["endpoints"])[:8],
            "locations": sorted(e["locations"]),
            "samples": vals[:2],
        })

    # rank: cross-boundary + craftable/enumerable first — that is the replay oracle's priority queue
    _rank = {"tenant_id": 0, "object_id": 1, "user_id": 1, "other": 3, "public_id": 4}
    ids.sort(key=lambda d: (_rank.get(d["role"], 3),
                            0 if (d["enumerable"] or d["embedded_tenant"]) else 1,
                            d["name"]))

    tenants = [d["name"] for d in ids if d["role"] == "tenant_id"]
    objects = [d["name"] for d in ids if d["role"] == "object_id"]
    boundary = [d for d in ids if d["authz_sensitive"]]
    craftable = [d["name"] for d in ids if d["enumerable"] or d["embedded_tenant"]]

    try:
        from core import target_profiles as _tp
        for host in sorted({r["host"] for r in recs})[:5]:
            _tp.record_scan(host, "app_map",
                            f"{len(ids)} id(s): {len(tenants)} tenant, {len(objects)} object, "
                            f"{len(boundary)} authz-boundary, {len(craftable)} craftable/enumerable")
    except Exception:
        pass

    return {"success": True,
            "message": (f"Mapped {len(ids)} id-bearing param(s) across {len(recs)} request(s): "
                        f"{len(tenants)} tenant-boundary, {len(objects)} object, "
                        f"{len(boundary)} authz-sensitive, {len(craftable)} craftable/enumerable. "
                        f"Cross-boundary set (oracle's queue): {', '.join(d['name'] for d in boundary[:8])}"
                        + ("" if len(boundary) <= 8 else " ...")),
            "data": {"ids": ids, "tenants": tenants, "objects": objects,
                     "authz_boundary": [d["name"] for d in boundary], "craftable": craftable,
                     "request_count": len(recs)}}
