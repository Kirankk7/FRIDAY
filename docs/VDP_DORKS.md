# VDP / Self-Hosted Programme Discovery — Dork Corpus

Source: Kiran, 2026-08-18. Purpose: find **self-hosted** vulnerability-disclosure
programmes (outside H1/YWH/Bugcrowd) whose policy page is itself the published
authorisation to test.

## 🚦 THE GATE — read before running any of these

A dork returns a *page*, not a permission. A candidate only enters the pipeline when its
policy page states **all three**:

1. **Scope** — which hosts/assets may be tested (a policy with no scope is not authorisation).
2. **Safe harbour / non-prosecution wording** — explicit "we will not pursue legal action".
3. **A working intake channel** — mailbox, form, or platform link ([[venue-first-rule]]).
4. **Domain ownership verified** — the scoped domains must actually belong to the
   publisher. Cross-check branding, product names and outbound links on each claimed
   host. Policies get copied between companies, list domains not yet owned, or name a
   domain that has since changed hands. **A scope list is a claim, not a title deed**,
   and a claim by party A over party B's domain authorises nothing. This one is manual
   — no regex can settle it.

Then the existing screens still apply: reachability from UAE, then product class
(money / limits / roles first — that is what produced both filed bugs).

⚠️ **Jurisdiction matters more here than on a platform.** The UK Computer Misuse Act 1990
has **no good-faith-researcher exemption and no safe-harbour doctrine** — unauthorised
access is an offence regardless of intent or damage. Same shape in NL/DE/BE. On a platform,
scope is the authorisation; here the **policy page is the only thing standing between
research and an offence**. No published scope ⇒ no testing. Not a judgement call.

🚫 **Never** use these to find *invite-only* H1/YWH/Synack programme pages and test them
uninvited. That is an RoE violation that burns the platform accounts Milestone B depends on.
`"powered by bugcrowd" -site:bugcrowd.com` and `"powered by synack"` are for **recognising a
managed programme**, not for entering one — if it is managed, apply through the platform.

## 💰 Milestone note

Most self-hosted VDPs pay nothing (swag / hall of fame). [[milestone-hypothesis-origin]]
Milestone B needs a **paid** report. So:
- reward-bearing dorks (`reward`, `bounty`, `£`, `€`, `monetary`) → Milestone B candidates
- everything else → **Milestone A lab** (soft targets where a hypothesis can actually be
  falsified; fortresses starve the lens because nothing there is breakable)

---

## Operator repairs — much of the raw list does not execute

| Raw | Problem | Fixed |
|---|---|---|
| `inurl : / security` | spaces break the operator | `inurl:/security` |
| `insite:"responsible disclosure"` | `insite:` is not an operator | `site:` |
| `intext responsible disclosure` | missing colon | `intext:"responsible disclosure"` |
| `inurl"security report"` | missing colon | `inurl:"security report"` |
| `r=h:uk` / `r=h:nl` / `r=h:eu` | **not a Google operator** (carried over from other engines) | `site:.uk` — or append `&cr=countryUK` to the results URL |
| `site:*.*.uk` | wildcard in the TLD position is unreliable | `site:.uk` |
| `site:*.gov.*` | same | `site:.gov.uk` |
| `responsible disclosure:sites` | not an operator | drop |
| `site eu responsible disclosure` | no operator at all | `site:.eu "responsible disclosure"` |

Also: `ext:` and `filetype:` are equivalent; Google caps results hard, so **vary the dork
rather than paging deep**. Many entries in the raw list are near-duplicates of each other.

---

## 🇬🇧 UK working set (start here)

```
site:.uk "responsible disclosure" "reward"
site:.uk "vulnerability disclosure policy" "reward"
site:.uk "bug bounty" intext:"£"
site:.uk inurl:/.well-known/security.txt
site:.uk inurl:security.txt "Policy:"
site:.uk intext:"if you believe you have found a security vulnerability" "reward"
site:.uk inurl:/security "hall of fame"
site:.co.uk "responsible disclosure" -site:hackerone.com -site:bugcrowd.com
site:.uk inurl:responsible-disclosure intext:"monetary"
site:.uk "we take security seriously" inurl:/security
```

Deprioritised for the UK pass:
- `site:.gov.uk` — real NCSC-backed VDPs exist and are legitimate, but government estates
  carry the highest legal sensitivity and effectively never pay. Not a first pass.
- `site:*.edu` / university dorks — rarely pay, frequently no safe-harbour wording.
- crypto/BTC/USDT dorks — exchanges often publish a "bounty" with no safe harbour and
  hostile terms. High risk, low expected payout.

---

## Full raw corpus (as supplied, unedited)

```
inurl /bug bounty
inurl : / security
inurl:security.txt
inurl:security "reward"
inurl : /responsible disclosure
inurl : /responsible-disclosure/ reward
inurl : / responsible-disclosure/ swag
inurl : / responsible-disclosure/ bounty
inurl:'/responsible disclosure' hoodie
responsible disclosure swag r=h:com
responsible disclosure hall of fame
responsible disclosure europe
responsible disclosure white hat
white hat program
insite:"responsible disclosure" -inurl:nl
intext responsible disclosure
site eu responsible disclosure
site .nl responsible disclosure
site responsible disclosure
responsible disclosure:sites
responsible disclosure r=h:nl
responsible disclosure r=h:uk
responsible disclosure r=h:eu
responsible disclosure bounty r=h:nl
responsible disclosure bounty r=h:uk
responsible disclosure bounty r=h:eu
responsible disclosure swag r=h:nl
responsible disclosure swag r=h:uk
responsible disclosure swag r=h:eu
responsible disclosure reward r=h:nl
responsible disclosure reward r=h:uk
responsible disclosure reward r=h:eu
"powered by bugcrowd" -site:bugcrowd.com
"submit vulnerability report"
site:*.gov.* "responsible disclosure"
intext:"we take security very seriously"
site:responsibledisclosure.com
inurl:'vulnerability-disclosure-policy' reward
intext:Vulnerability Disclosure site:nl
intext:Vulnerability Disclosure site:eu
site:*.*.nl intext:security report reward
site:*.*.nl intext:responsible disclosure reward
"security vulnerability" "report"
inurl"security report"
"responsible disclosure" university
inurl:/responsible-disclosure/ university
buy bitcoins "bug bounty"
inurl:/security ext:txt "contact"
"powered by synack"
intext:responsible disclosure bounty
inurl: private bugbountyprogram
inurl:/.well-known/security ext:txt
inurl:/.well-known/security ext:txt intext:hackerone
inurl:/.well-known/security ext:txt -hackerone -bugcrowd -synack -openbugbounty
inurl:reporting-security-issues
inurl:security-policy.txt ext:txt
site:*.*.* inurl:bug inurl:bounty
site:help.*.* inurl:bounty
site:support.*.* intext:security report reward
intext:security report monetary inurl:security
intext:security report reward inurl:report
site:security.*.* inurl: bounty
site:*.*.de inurl:bug inurl:bounty
site:*.*.uk intext:security report reward
site:*.*.cn intext:security report reward
"vulnerability reporting policy"
"van de melding met een minimum van een" -site:responsibledisclosure.nl
inurl:/security ext:txt "contact"
inurl:responsible-disclosure-policy
"If you believe you've found a security vulnerability"
intext:"BugBounty" and intext:"BTC" and intext:"reward"
intext:bounty inurl:/security
inurl:"bug bounty" and intext:"€" and inurl:/security
inurl:"bug bounty" and intext:"$" and inurl:/security
inurl:"bug bounty" and intext:"INR" and inurl:/security
inurl:/security.txt "mailto*" -github.com -wikipedia.org -portswigger.net -magento
/trust/report-a-vulnerability
site:*.edu intext:security report vulnerability
"cms" bug bounty
"If you find a security issue" "reward"
"responsible disclosure" intext:"you may be eligible for monetary compensation"
inurl: "responsible disclosure", "bug bounty", "bugbounty"
responsible disclosure inurl:in
site:*.br responsible disclosure
site:*.at responsible disclosure
site:*.be responsible disclosure
site:*.au responsible disclosure
inurl:security-program intext:bug bounty
intext:report a bug intext:reward
intext:"our bug bounty program" "reward"
intext:"bug bounty program" "@"
intext:"USDT" inurl:"Bug-Bounty"
intext:whitehat program reward
inurl:report-a-bug intext:reward
intext:you will receive a reward inurl:Bug bounty
inurl:bug-bounty intext:cash rewards
site:security.*.com intext:bug bounty
site:security.*.* inurl: bounty
vulnerability detection program reward
intext:Cryptocurrency Exchange intext:Bug bounty
inurl:bug bounty intext:token of gratitude
inurl:bug bounty intext:token of appreciation
inurl:vulnerability-disclosure intext:bounty
site"*.nl intext:Responsible disclosure intext:€25
site"*.nl inurl:vulnerability-disclosure intext:reward
responsible disclosure r=h:com intext:€25
```

---

## 🔬 THE EDGE IS NOT THE DORK LIST — mutate it

**Verified 2026-08-18:** the corpus above is `sushiwushi/bug-bounty-dorks` verbatim (155
lines, same order, same quirks: `buy bitcoins "bug bounty"`, the Dutch
`van de melding met een minimum van een`). It is mirrored across GitHub, Medium, GitBook
and Scribd. Every beginner following those posts runs these exact strings against the same
Google index, so the programmes it surfaces are the **most**-dorked, not the least.
Same lesson as `newest-programs-are-the-most-crowded` and `top-hunter-repos-mined`:
**a public artefact is never the edge.**

### 1. British-English mutations (the public corpus is US/NL-centric)
UK policy pages spell it *programme*, *recognise*, *authorised*, and say *"in the first
instance"*. Nobody dorks these:

```
site:.uk "vulnerability disclosure programme"
site:.uk "we operate a responsible disclosure programme"
site:.uk "report it to us in the first instance" security
site:.uk "security.txt" "Preferred-Languages: en-GB"
site:.uk "recognise the value of the security community"
site:.uk "we will not seek prosecution" security
site:.uk intext:"in-scope" intext:"good faith" -site:hackerone.com
site:.co.uk "coordinated disclosure" -inurl:blog
```
⭐ `"we will not seek prosecution"` came from reading a real UK policy page — it is the
UK phrasing of safe harbour, and the US-centric corpus has no pattern for it.

### 2. Skip Google entirely — `scripts/vdp_sweep.py`
Google caps results and everyone shares the index. security.txt (RFC 9116) is a
**well-known URI that exists to be fetched**, so a domain list beats a dork list.

```bash
python scripts/vdp_sweep.py uk_domains.txt -o uk.jsonl --policy --rate 3 --contact <your-handle>
python scripts/vdp_sweep.py --report uk.jsonl
```
One request per host, global rate limit (default 4/s), identifying User-Agent. Stage 2
fetches each `Policy:` URL and scores **scope / safe-harbour / reward / monetary_reward /
platform**, then ranks gate-passers first.

⚠️ **`gate_pass` is regex, not permission.** It means "this page probably contains the
right clauses" — read the policy yourself before touching any host.

**Sourcing the domain list** (the sweep is only as good as its input): Tranco top-1M
filtered to `.uk`, Companies House bulk data, sector directories (fintech / insurtech /
healthcare suppliers). Rank by **product class first** — money / limits / roles is what produced
both filed bugs; a retailer with a VDP is still a retailer.

### 3. Read the `platform` column before hunting
A `security.txt` whose Contact/Policy points at a managed platform means the programme
is **managed** — apply through that platform, never self-hunt it. In the smoke test
**4 of 6** were platform-managed and only **one** was genuinely self-hosted. That ratio
is the point: most of what a dork surfaces is already somebody's public programme.

### Calibration from the smoke test (7 UK domains, 6 with security.txt)
| case | gate | reward | cash | lesson |
|---|---|---|---|---|
| national broadcaster | PASS | yes | **no** | self-hosted, but the "reward" is swag — cash filter matters |
| challenger bank | PASS | yes | yes | pays, but platform-managed ⇒ apply, don't self-hunt |
| government estate | - | **no** | - | states outright *"you will not be paid a reward"* |
| grocery retailer | - | - | - | platform-managed |

Three regex bugs were caught only by checking against real page text — never trust these
patterns without re-reading the page:
- `"will not seek prosecution"` missed by *pursue/take/initiate legal*
- `"in-scope"` hyphenated, missed by `in scope`
- `"you will not be paid a reward"` scored **reward=True** until `no_reward` was taught to win
