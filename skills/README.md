# Skills

Reusable, model-invokable skill packs. Each subdirectory is one skill with a `SKILL.md`
that carries a `name` + `description` frontmatter; the assistant loads a skill when a task
matches its description.

These skills are vendor-neutral methodology packs (API design, CI/CD, security audit,
ML workflow, performance, documentation, and more). They contain no user-specific content.

## Using them
- With Claude Code: place this `skills/` directory where your harness loads skills
  (e.g. point `CLAUDE_CONFIG_DIR` at this tree, or symlink into `~/.claude/skills`).
- Each skill triggers automatically by its `description`, or can be invoked by name.

## Adding your own
Create `skills/<your-skill>/SKILL.md` with frontmatter:

```yaml
---
name: your-skill
description: One line describing WHEN to use this skill (triggers matching).
---
```

Then the body: the procedure, checklists, and guidance the assistant should follow.
