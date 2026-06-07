---
title: Cold-start in recommender systems
type: concept
tags: [recsys, cold-start, technique]
created: 2026-05-12
updated: 2026-05-12
ip_clean: true
sources: []
---

> **EXAMPLE — fictional.** A correctly-filed *shared-knowledge* note: pure technique, no
> client detail, survives any engagement ending. `./aether reset` removes this folder.

# Cold-start in recommender systems

**The problem.** A recommender has nothing to go on for a brand-new user or item — no
interaction history to learn from. "What do we show before we know anything?"

**Why it matters.** Cold-start is where most recsys quietly fail in production: the model
is great for the head and useless on the day someone signs up, which is exactly the moment
that decides retention.

**How it manifests / approaches.**
- **Content-based seeding** — recommend from item *features* (text, tags, embeddings) until
  interactions accrue.
- **Popularity priors** — fall back to "what's popular for people like this" as a safe default.
- **Bandit exploration** — deliberately spend a little traffic learning each new item's appeal
  rather than starving it of impressions.

**Tradeoffs / gotchas.** Popularity priors entrench a rich-get-richer bias; content-based
seeding is only as good as your feature quality; bandits cost short-term conversion to buy
long-term signal. Pick by how expensive a bad first impression is in your domain. See also
[[evaluation-offline-vs-online]] before trusting any of these in an A/B test.

**Cross-links:** [[evaluation-offline-vs-online]]
