# MediaMarkt Hunt #1 — Playbook (HAR co-pilot, compliant)

Target: `https://www.mediamarkt.de` (+ other in-scope country sites). React PWA + **GraphQL** API, Cloudflare-fronted.
Program **forbids automated scanning** → the browser is the crawler, FRIDAY analyzes the HAR offline. Do everything by hand at human pace.

## STEP 0 — Enrol (once, required for legal safe-harbour)
1. Create a **YesWeHack** account → open the **MediaMarktSaturn** program → **read + accept the policy** (you're only covered if enrolled).
2. Get your **`@yeswehack.ninja`** email alias (YWH profile → your alias, e.g. `kiran@wh<id>.yeswehack.ninja`).
3. Install a **User-Agent Switcher** browser extension → set UA to append ` -MMS-BugBounty ` (required by the program on every request).

## STEP 1 — Two accounts (compliance: min needed, your own only)
- Register **2** MediaMarkt accounts using `+` tags on your alias: `you+a@…yeswehack.ninja`, `you+b@…yeswehack.ninja`.
- On each, create a **free** owner-scoped object so there's something to BOLA-test: **add a shipping address** (+ a wishlist item, put an item in cart). *(Order-BOLA needs a placed order = costs money → skip; address/wishlist/cart are free.)*
- Write down each account's object IDs as you see them (addressId, wishlistId, customerId, cartId).

## STEP 2 — Capture the HAR (Chrome)
1. Log in as **account A**.
2. `F12` → **Network** tab.
3. Tick **"Preserve log"** (so navigating doesn't wipe it). Optionally filter to **Fetch/XHR** (the API calls).
4. Now **browse the owner-scoped area slowly**, so the GraphQL/REST calls that carry your IDs get recorded:
   `Mein Konto` → **Adressen** (open/edit an address) → **Merkliste** (wishlist) → **Warenkorb** (cart) → **Profil/Daten** → **Bestellungen** if you have any.
5. Right-click anywhere in the request list → **"Save all as HAR with content"** → save `mediamarkt_A.har`.
6. *(optional)* repeat logged in as **B** → `mediamarkt_B.har`.

**Firefox:** `F12` → Network → right-click a request → **"Save All As HAR"**.

## STEP 3 — FRIDAY (offline, zero requests)
- Drop the `.har` path in chat. FRIDAY runs `hunt_mode(har)` →
  ranked **owner-scoped BOLA/IDOR candidates** + GraphQL operations + object-ID map + JWT analysis.
- GraphQL-aware: it reads `operationName` + `variables` (where the IDs live) and ranks the `GetAddress`/`GetWishlist`-type ops.

## STEP 4 — Verify ONE candidate (manual, your 2 accounts, single request)
- Take FRIDAY's #1 candidate (e.g. `GetAddress(addressId:)`).
- As **account B**, replay that exact request but with **A's** addressId (Burp Repeater, or DevTools "Copy as fetch" + edit).
- **BOLA confirmed** if B receives **A's** address data (and an anonymous/no-token request is denied).
- Reproduce **twice**. Screenshot before/after. **Redact PII.**

## STEP 5 — Report
- Drop the confirmed candidate + responses in chat → FRIDAY writes the report (title/severity/CVSS, summary, exact repro, PoC, impact, remediation), PII redacted.
- Submit on YesWeHack. Log the row in `HUNT_TRACKER.md`.

## Sticky-note rules
- ✅ UA tag `-MMS-BugBounty` on EVERY request · 2 accounts, your own only · IDOR only across YOUR accounts · redact PII · reproduce 2× · low request rate.
- ❌ No automated scanning/fuzzing · no touching other real users' data · no SQLi table dumps (version-only) · XSS = `alert(17)` only · no bulk contact-form messages.
- If FRIDAY finds nothing → **that's still a real lesson.** Log it. Don't build. Hunt again.
