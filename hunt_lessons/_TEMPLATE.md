# <YYYY-MM> — <Target / Program>

- **Program:** <name + platform (HackerOne/Intigriti/VDP/self-hosted dogfood)>
- **Scope:** <in-scope hosts/APIs; auth model; # principals>
- **Date(s):** <YYYY-MM-DD …>
- **FRIDAY version / commit:** <git short-sha>

## What FRIDAY found
- <finding — class, endpoint, candidate|confirmed, CVSS>

## What FRIDAY MISSED (false negatives)
- <bug a human found that the engine did not — why the probe/oracle didn't fire>

## False positives
- <what fired but was not real — root cause of the over-claim>

## Manual work (engine couldn't do)
- <recon/auth/pivot/validation a human had to do by hand>

## Feature NOT added
- <gap observed but deliberately NOT built — reason (one-off? hunt-gated? out-of-scope?)>

## Feature added / to add
- <deterministic improvement earned by THIS hunt — only if pattern recurred, else leave blank>

## Lessons
- <one-liners. workflow / authz model / JWT quirk / spec shape / triager expectation worth remembering>
