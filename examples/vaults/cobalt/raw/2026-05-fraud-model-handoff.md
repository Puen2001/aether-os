---
title: Cobalt Pay — fraud model handoff notes
type: note
tags: [cobalt, fraud, handoff]
created: 2026-05-20
updated: 2026-05-20
sources: [client call 2026-05-20]
---

> **EXAMPLE — fictional client note.** Note there is **no `ip_clean: true`** here — this is
> the *same kind of work* as the Commons cold-start note, but walled. A stranger reading it
> can tell exactly who it's for; it would be deleted the day the engagement ends. That is the
> wall. `./aether reset` removes this folder.

# Cobalt Pay — fraud model handoff

Client-specific. **Must stay in the Cobalt vault. Never file in Commons.**

- Model: gradient-boosted trees on the `txn_velocity_7d`, `device_risk_v2`, and
  `merchant_cohort` features (their internal naming).
- Decision threshold tuned to **0.83** to hit their <=0.4% false-positive SLA.
- Vendor: scoring runs on their "Sentinel" internal platform; handoff is a weekly parquet drop.
- Launch date: **2026-06-15** to the EU segment first.

Generic lesson extracted to Commons → [[cold-start-in-recsys]] (the *technique*, with all
Cobalt specifics stripped). This note keeps the specifics; Commons keeps the craft.
