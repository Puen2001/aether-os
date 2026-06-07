# Security Policy

AETHER OS is a **local-first scaffold**. It runs as plain files on your machine,
makes no network calls of its own, and ships no telemetry. The main security
surface is therefore (a) the hooks/scripts that execute locally on your machine,
and (b) the pre-commit gate that is meant to stop secrets/IP from leaking into a
commit.

## Reporting a vulnerability

Please report security issues **privately** via
[GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository (Security → Report a vulnerability). Do not open a public issue
for an undisclosed vulnerability.

We aim to acknowledge a report within a few days and to coordinate disclosure once
a fix is available.

## In scope

- The `aether` dispatcher and the hook/tool scripts in `tools/` and `system/`.
- The pre-commit gate (`tools/precommit-scan`) failing to block a planted secret
  or denylisted string it should catch.
- The edit-time gate (`gateguard`) or any hook behaving in a way that could leak
  data off the machine.

## Out of scope

- The contents of **your own** filled-in vaults, `tools/*.env`, or
  `system/denylist.txt` (these are yours, gitignored, and never shipped).
- Your Claude Code installation and account.
- Social-engineering of the model itself.

## Guarantees this project tries to keep

- **No telemetry, ever.** The event log stores a SHA-256 hash of input, not
  plaintext (see [`docs/PRIVACY.md`](docs/PRIVACY.md)). Hashing prevents casual
  recovery of prompts; it is **not** cryptographic anonymization of short,
  low-entropy inputs. The log never leaves your machine.
- **No network egress by default.** Vault sync commits locally only until you opt
  in with your own git remote.
- **Fail-loud, not fail-silent.** `./aether doctor` makes a half-wired setup visible.
- **The IP-clean gate is defense-in-depth, a control you can point to — not a
  guarantee.** It catches known patterns and your denylisted strings; treat it as
  a safety net, not a promise that a leak is impossible.

---

AETHER OS is an independent open-source project and is not affiliated with,
endorsed by, or sponsored by Anthropic, xAI, or any other company. Product and
company names are trademarks of their respective owners.
