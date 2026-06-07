# Third-party notices

AETHER OS is MIT-licensed (see [`LICENSE`](LICENSE)). It bundles a small number of
skill packs that are **adapted from upstream open-source projects**. Those upstreams
are themselves MIT-licensed, and MIT requires their copyright + permission notice be
retained in redistribution. They are reproduced below.

Each adapted skill also carries an `origin:` line in its `SKILL.md` frontmatter
pointing back to its source.

---

## Adapted skill packs

| Skill pack | Upstream project | License |
|---|---|---|
| `cost-aware-llm-pipeline`, `mle-workflow`, `pytorch-patterns`, `regex-vs-llm-structured-text` | [affaan-m/ECC](https://github.com/affaan-m) | MIT |
| `cybersecurity` | [AgriciDaniel/claude-cybersecurity](https://github.com/AgriciDaniel) (pinned commit `bcc9638`) | MIT |
| `recsys-pipeline-architect` | [mturac](https://github.com/mturac) — independent reimplementation of the pattern popularized by xAI's "For You" algorithm | MIT |

### MIT permission notice (applies to the adapted upstreams above)

```
Copyright (c) the respective upstream authors (see the table above)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

> The `recsys-pipeline-architect` skill is an independent reimplementation of an
> architectural *pattern* (no source code copied); the xAI "For You" repository it
> references is Apache-2.0, but no Apache-licensed code is included here.

---

## Public reference taxonomies

The `cybersecurity` skill references public security taxonomies and standard
identifiers — **OWASP** (content © the OWASP Foundation, CC-BY-SA), **MITRE ATT&CK**
and **CWE** (© The MITRE Corporation), and **CVE** identifiers. Standard identifiers
(CWE-/CVE-/ATT&CK technique IDs) are factual references; where OWASP text is quoted,
attribution is to the OWASP Foundation. These are used for reference and education
and are the property of their respective owners.

---

AETHER OS is an independent open-source project and is **not affiliated with,
endorsed by, or sponsored by** Anthropic, xAI, or any other company. Product and
company names referenced (including "Claude" and "Claude Code") are trademarks of
their respective owners and are used here only for truthful description of
compatibility.
