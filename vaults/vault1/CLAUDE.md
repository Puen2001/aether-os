# vault1 — shared-knowledge vault

> Suggested role: your **shared-knowledge vault** — generic, portable, IP-clean technique and
> reference. Read by every other vault for depth. See `system/SYSTEM.md` for the full doctrine.
> Rename this vault and change its role in `introduction.md` if you like.

## What goes here

Pure technique and reference that would survive even if you left a job or sold a venture —
no employer / customer / venture fingerprints. Apply the **IP-clean placement check**
(`system/SYSTEM.md` §3) before filing anything here.

| Belongs here (yes) | Belongs in a domain vault (no) |
|---|---|
| A reusable method or pattern | "How we did X for <employer/customer>" |
| Vendor-neutral tool/framework comparison | A negotiated price, an internal hostname, a customer name |
| A general workflow | A project's private dataset or credentials |

## Folders

- `concepts/` — technique pages (definition → why it matters → tradeoffs → cross-links).
- `entities/` — tools, vendors, frameworks (vendor-neutral reference).
- `analysis/` — long-form methodology pieces.
- `raw/` — raw material pending the placement check (exempt from `ip_clean` until filed).
- `wiki/index.md` — the content catalogue (keep current).
- `wiki/log.md` — append-only activity log (one line per ingest).

## Conventions

Frontmatter requires `ip_clean: true` for every filed page (your self-attestation). Use
`[[wiki-links]]` between pages. See `system/SYSTEM.md` §4 for the full page convention.
