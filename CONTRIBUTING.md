# Contributing to AETHER OS

Thanks for considering a contribution. AETHER OS is a small, self-hostable scaffold;
the best contributions keep it **generic, safe, and easy to adopt**.

## The one hard rule: no personal data

This repo ships **zero personal data**. The only filled-in content lives under
`examples/` and is obviously fictional (the "Mara Voss" persona), clearly banner-marked
for deletion. Never commit:

- real names, emails, usernames, hostnames, IP addresses, or absolute home paths;
- employer / client / customer names or any data under an NDA;
- secrets, tokens, or API keys (the pre-commit gate will try to stop you, but don't rely on it).

Before opening a PR, run:

```bash
./aether doctor          # confirms your setup is wired correctly
tools/precommit-scan .   # scans staged changes for secrets / denylisted strings
```

## Good first contributions

- **New skill packs.** A `skills/<name>/SKILL.md` with a clear auto-trigger description.
  If adapted from an upstream project, add an `origin:` frontmatter line and an entry in
  [`NOTICE.md`](NOTICE.md) (MIT-compatible licenses only).
- **Worked-example personas** for other professions (a designer, a researcher, a
  founder) — they help newcomers see the wedge in their own terms.
- **`./aether doctor` checks** that catch a common setup mistake.
- **Connectors** that let another medium reach an AETHER vault (see the roadmap in
  [`README.md`](README.md)).

## How to add an agent

Agents are plain Markdown with frontmatter in `agents/`. Keep them **role-named and
generic** (the user renames them in `introduction.md`). Respect the dispatch-tier
discipline in [`system/SYSTEM.md`](system/SYSTEM.md) §5 — default to inline, dispatch
only when context isolation earns its cost.

## Pull requests

- One focused change per PR; describe the *why*.
- Keep the doctrine in `system/SYSTEM.md` and the README in sync if you change behavior.
- No emoji in `system/SYSTEM.md`, agent prompts, or community files.
- Sign off your commits (DCO): `git commit -s`.

By contributing you agree your work is licensed under the project's
[MIT License](LICENSE). Be excellent to each other — see
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
