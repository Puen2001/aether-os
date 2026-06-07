> **EXAMPLE — fictional persona "Mara Voss."** This file exists so you can see AETHER
> working before you write a word. Do **not** put your own data here — `./aether reset`
> deletes the whole `examples/` folder. Fill in the real `introduction.md` at the repo root.

# Introduction — Mara Voss

## 1. About you
- **Name / what to call you:** Mara Voss
- **Role or title:** Freelance ML & data consultant
- **What you do:** I build recommender systems and data pipelines for clients under NDA,
  and I write publicly about technique. I work alone, so my tools have to keep my clients
  separated for me.
- **Areas of expertise:** recommender systems, data pipelines, Python
- **Current projects:**
  - Commons — my portable, vendor-neutral craft notes (shareable)
  - Cobalt Pay — fintech client (NDA)
  - Verda Health — health startup client (NDA, PII-sensitive)
- **Goals (6–12 mo):** turn one-off projects into two recurring retainer clients;
  productize my pipeline playbook without leaking any client's specifics.
- **Location / timezone:** Lisbon (WET)

## 2. How you want the assistant to work
- **Tone:** concise, answer-first.
- **Reply length:** lead with the verdict; depth on ask.
- **When to ask vs. act:** confirm anything irreversible or anything that crosses a vault boundary.
- **Things to always do:** apply the IP-clean check before filing; name the boundary out loud.
- **Things to never do:** let a client's name or data enter the shared (Commons) vault.

## 3. Your vaults
| Vault | Your name for it | What it holds | Shared-knowledge? |
|---|---|---|---|
| vault1 | Commons | Portable ML/data technique, vendor-neutral notes | yes |
| vault2 | Cobalt  | Cobalt Pay (fintech client) — NDA | no |
| vault3 | Verda   | Verda Health (health client) — NDA, PII-sensitive | no |

## 4. Name your agents
The roster ships role-named under the one AETHER OS brand. Naming them is optional —
here Mara has named a few; the rest keep their default role names.

| Default role | Your name | Role |
|---|---|---|
| assistant  | Aether    | Your main AI — the one you talk to |
| researcher | Atlas     | Research, synthesis, methodology |
| strategist | Cassandra | Pre-mortems on big decisions |
| (the rest left blank → keep defaults) | | |

## 5. Setup pointers
Already handled by `./aether init`. The denylist (`system/denylist.txt`) is seeded with the
client names that must never reach the Commons vault: `Cobalt Pay`, `Verda Health`.
