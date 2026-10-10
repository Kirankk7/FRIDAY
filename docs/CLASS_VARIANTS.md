# SUB-VARIANT TAXONOMY — and which we have ever actually tested

Companion to `CLASS_METHODOLOGY.md`. Written 2026-10-07 because the class list hides a second
denominator: a class marked ENFORCED may have had **one** of its sub-variants tested. "XSS
enforced" has meant reflected-only more than once.

Legend: **T** tested at least once with a passing control · **P** partial / single instance ·
**N** never tested in any hunt · **X** excluded by rule (DoS, social engineering, third-party data)

## 1. BOLA / IDOR
| variant | state |
|---|---|
| direct object id in path | T |
| id in body while the path says otherwise (split-brain) | T |
| id in query string | T |
| raw UUID vs slug — one object, two selector forms | T |
| id carried in `Referer` only | T |
| batch / array of ids — partial authorisation | T (fails atomically, both orders) |
| nested object (parent authorised, child not) | P |
| second-order — id stored now, dereferenced later by another principal | **N** |
| sequential / predictable id enumeration | X — ROE |

## 2. BFLA / privilege escalation
| variant | state |
|---|---|
| forced browsing to an unlinked privileged route | T |
| self-promotion via a role field in a write | T |
| **disabling the control that enforces the gate** | T — best finding of its class |
| client-side-only authorisation check | T |
| vertical — lower role invokes higher-role function | P — TIER-blocked on 3 hunts |
| horizontal function (same level, other principal) | P |
| service-account / machine-identity escalation | **N** — always TIER |
| restricted principal lifts its OWN restriction (self-reactivate, self-unsuspend, self-restore role) | **N** — pb0786; needs our second principal |

## 3. SQLi / NoSQLi
| variant | state |
|---|---|
| error-based | T |
| time-based blind (`pg_sleep`, `SLEEP`) | T |
| boolean-based blind | **N** |
| UNION-based | **N** |
| out-of-band (DNS/HTTP exfil) | **N** |
| second-order (stored, executed on a later read) | **N** |
| NoSQL operator injection (`$ne`, `$gt`, `$regex`) | **N** |
| NoSQL JS / `$where` | **N** |
| ORDER BY / LIMIT injection | **N** |

## 4. XSS
| variant | state |
|---|---|
| reflected — param echoed into HTML | T |
| stored — written now, rendered later | T |
| execution-confirmed vs reflection-only | T since 2026-10-06, both oracle legs |
| JS / script context (json-in-script) | T |
| attribute-context escape | P |
| **DOM-based** — sink in client JS, never reaches the server | **N** |
| **blind** — stored, rendered only in a panel we cannot see | **N** |
| mXSS / mutation | **N** |
| CSTI — client template injection | **N** |
| SVG / file-upload XSS | **N** |
| self-XSS | X — not a finding alone |

## 5. SSRF / XSPA
| variant | state |
|---|---|
| allowlist bypass — hostname that resolves internally | T — the string-matcher finding |
| semi-blind via timing / status differential | T |
| blind — DNS callback only | T — and on the never-submit list alone |
| blind — HTTP callback | P |
| XSPA port scan | P |
| cloud metadata (`169.254.169.254`) | P — attempted, never reached |
| full-response SSRF | **N** |
| redirect-based bypass (302 to internal) | **N** |
| DNS rebinding | **N** |
| protocol smuggling (`gopher:`, `file:`, `dict:`) | **N** |

## 6. Mass assignment
| variant | state |
|---|---|
| flat unknown field accepted | T |
| nested object field | T |
| type confusion (string where object expected) | T |
| array / batch element | T |
| tenant selector override in body | T — discarded, path wins |
| plan / tier / entitlement flag | T — persisted, effect unproven |
| `force*` admin-override prefixed flags | T — persisted, effect unproven |
| read-only / server-computed field (audit, timestamps) | P |
| field that exists only in a sibling API version | **N** |

## 7. Business logic
| variant | state |
|---|---|
| race / TOCTOU on a single-use object | T — 5 concurrent zero-value checkouts |
| client-computed limit raised server-side | T — filed |
| feature flag enabled below entitlement | T — filed |
| workflow step skip / drop / strip / re-context | P |
| replay of the **commit** step | P |
| price / quantity / currency manipulation | **N** |
| negative or overflow quantity | **N** |
| state-machine reversal (refund after ship) | **N** |
| coupon / referral reuse | **N** — OUT_OF_SCOPE asset last time |

## 8. Secrets / disclosure
| variant | state |
|---|---|
| minified client bundle | T |
| source maps with `sourcesContent` | T |
| server-rendered hydration payload | T |
| archived bundles (Wayback) | T since 2026-10-06 |
| API over-fetch — field returned that the UI never shows | T |
| error message / stack trace | P |
| session material in URLs / query strings | P — many archived instances seen, current behaviour unconfirmed |
| git / repo exposure | **N** on bounty targets |
| EXIF / document metadata | **N** |

## 9. Auth / session
| variant | state |
|---|---|
| token mint without entitlement | T |
| expiry honoured | T |
| one-use / burn semantics | T |
| device / fingerprint binding | T |
| SSO assertion tamper | T |
| OAuth `redirect_uri` manipulation | T — filed |
| signature actually verified | P — usually UNTESTABLE externally |
| replay after logout | P |
| reset-token entropy | P |
| OIDC device-code flow abuse | P |
| session fixation | **N** |
| reset-token reuse / non-expiry | **N** |
| 2FA bypass | **N** |
| credential stuffing / brute force | X — forbidden by name |

## 10. RCE / server-side execution
| variant | state |
|---|---|
| SSTI — `{{7*7}}` evaluated | T — falsified on 37+ fields |
| OS command injection | **N** |
| insecure deserialization | **N** |
| expression language (SpEL / OGNL / EL) | **N** |
| `eval`-class code injection | **N** |
| file-write then include | **N** |
| dependency / package confusion | **N** |
| LFI to RCE via log poisoning | **N** |

## 11. XXE / path traversal / LFI
| variant | state |
|---|---|
| path traversal — read | T — the disclosed CVE |
| path traversal — write / delete | P — the embargoed one |
| XXE classic (in-band entity) | **N** |
| XXE blind / OOB | **N** |
| XInclude | **N** |
| zip-slip | **N** |
| symlink traversal | **N** |
| XML / YAML bomb | X — DoS |

## Micro-classes
| class | tested | never |
|---|---|---|
| JWT | claim tamper · expiry · `alg` read | `alg:none` · HS/RS confusion · weak-secret crack · `kid`/`jku`/`x5u` injection |
| CORS | static self-origin · reflected origin · credentialed cross-origin | `null` origin · pre/post-domain wildcard · subdomain-takeover chain |
| CSRF | token presence · rotation · server requires it | token not bound to session · method override · JSON CSRF · SameSite gap |
| GraphQL | introspection · array batching · aliasing · field suggestion | **query depth** · mutation-level authz · nested resolver authz · (complexity DoS = X) |
| Open redirect | naive · allowlist named in error · SSO `return_to` | `@` `//` `\` unicode bypasses · header-based · protocol-relative |
| File upload | reachability on an empty store | extension · content-type · magic-byte · double extension · filename traversal · SVG to XSS · polyglot |

---

## WHAT THIS TABLE IS FOR

**Count the N's.** Verified by parsing this file, not estimated:

```
CLASS-LEVEL  104 variants   T=42  P=17  N=41  X=4
MICRO-LEVEL   42 items      tested=17  never=25
             ---------------------------------------
TOTAL        146 enumerated
NEVER         66   45%
TESTED        59   40%
PARTIAL       17
EXCLUDED       4   (DoS, social engineering, enumeration ROE)
```

**66 of 146 sub-variants have never been tested in any hunt** (2026-10-10: +1, self-reactivation, from an ingested writeup). That is the honest shape of our
coverage, and it explains more than the class-level matrices do: a class can read ENFORCED while
most of its variant space was never touched.

⚠️ The first version of this paragraph said "55 of ~95" — both numbers wrong, written from
memory into a document whose entire subject is unverified numbers. Three separate counting scripts
disagreed before one was right (two had regex bugs: `` after `**` never matches, so every `**N**`
row was silently dropped). **A count in prose is a claim; a count the file can reproduce is a fact.**
Re-derive with the parser, never re-type the number.

It also redirects effort, and the direction is counter-intuitive. The playbook is thickest in
xss / sqli / ssrf — the three classes with the **most N rows and zero filed bugs** — and thinnest
in mass assignment and limit bypass, which produced the findings. So the variants worth adding are
the ones **adjacent to what has already paid**:

```
second-order BOLA          id stored now, dereferenced later by another principal
workflow skip / replay     the commit-step replay we have only done partially
price / quantity           never once attempted, and it is the same family as limit bypass
reset-token reuse          the one auth variant adjacent to a filed OAuth finding
GraphQL query depth        sitting at NOT TESTED on every GraphQL target so far
```

Not another SQLi technique. Nine N rows there have produced nothing in 40+ hunts.
