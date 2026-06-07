# Introduction — tell your assistant who you are

> New here? See [`examples/introduction.md`](examples/introduction.md) for a fully worked
> example (the fictional "Mara Voss"), then fill this one in. Do **not** edit the files under
> `examples/` — `./aether reset` deletes that folder.

Fill this in once. Your assistant reads it on first run to personalize itself — the more it
knows, the faster it becomes useful. Replace every `[fill]` with your own answer (or delete a
line you want to skip). Nothing here is shared anywhere; it lives in your own copy.

---

## 1. About you

- **Name / what to call you:** [fill]
- **Role or title:** [fill]
- **What you do (one or two lines):** [fill]
- **Areas of expertise:** [fill]
- **Current projects (name + one line each):**
  - [fill]
  - [fill]
- **Goals (next 6–12 months):** [fill]
- **Location / timezone (optional):** [fill]
- **Languages you work in:** [fill]

## 2. How you want the assistant to work

- **Tone:** [fill — e.g. concise and direct / warm / formal / playful]
- **Reply length:** [fill — e.g. lead with the answer, keep it short / give me depth]
- **When to ask vs. act:** [fill — e.g. confirm before irreversible actions; otherwise proceed]
- **Teaching style:** [fill — e.g. explain as you go / just do it / quiz me]
- **Things to always do:** [fill]
- **Things to never do:** [fill]

## 3. Your vaults

The system ships with three numbered vaults. Assign each a real meaning and rename it if you
like. Suggested: make one your **shared-knowledge vault** (generic, reusable technique) and the
others domain vaults (personal, a project, work). Add rows for more.

| Vault | Your name for it | What it holds | Shared-knowledge? |
|---|---|---|---|
| vault1 | [fill] | [fill] | [yes/no] |
| vault2 | [fill] | [fill] | [yes/no] |
| vault3 | [fill] | [fill] | [yes/no] |

## 4. Name your agents

Your assistant and its specialists ship with plain role names. Give them whatever names you
like — fill the **Your name** column. Leave a row blank to keep the default. The agents keep
their roles; only what you call them changes.

| Default role | Your name | Role (what it does) |
|---|---|---|
| assistant | [fill] | Your main AI — coordinates everything, the one you talk to |
| engineer | [fill] | Engineering + finance/cost judgment |
| data-steward | [fill] | Datasets, knowledge base, vault upkeep, lookups |
| researcher | [fill] | Research, literature synthesis, methodology |
| red-team | [fill] | Offensive security on your own systems (authorized only) |
| security | [fill] | Defensive code security, secret/dependency scanning |
| reviewer | [fill] | Code review and lint (read-only) |
| ops | [fill] | Deployment, runtime, operations |
| quick-tasks | [fill] | Quick scripts, scaffolding, bulk file ops |
| designer | [fill] | Visual/UX/content design, presentations |
| strategist | [fill] | Long-horizon pre-mortems on big, hard-to-reverse decisions |

> After you rename them here, you can also rename the files in `agents/` and the `name:` field
> in each file's frontmatter to match — optional, but keeps things tidy.

## 5. Setup pointers

Most of this is done for you by **`./aether init`** (copies the templates, sets exec bits, wires
the pre-commit gate). After that:

- **Your denylist:** `./aether init` created `system/denylist.txt` from the example — add any
  names (employer, customers, ventures) that must never leak into the shared-knowledge vault.
- **Secrets (optional):** if you use the Telegram bridge, fill in `tools/telegram.env` (created
  from the example, gitignored — never committed).
- **First run:** open the assistant **from this folder** (`claude`) and ask it to read this file.
  It will introduce itself and confirm what it learned.
- **Back up to your own git (optional):** auto-push is OFF by default. To commit + push your vault
  to *your own* repo at the end of each session:
  ```
  ./aether sync https://github.com/you/your-vault.git
  ```
  Add `--no-autopush` to back up but push by hand. Turn auto-push off later: `rm tools/.autopush-enabled`.
