# Schrodinger Skills

> *"Skills should not observe each other — until you actively choose, they exist in superposition."*

Schrodinger Skills is an open-source collection of AI Skills by [余明宸 (sljdxde)](https://github.com/sljdxde), following the [Agent Skills](https://agentskills.io) open standard.

Each skill lives in its own folder with a `SKILL.md` file at its core. Install by asking your Agent one sentence.

*Note for English readers: This project originated in the Chinese AI community. Contributions and translations are welcome.*

---

## Skills

### skill-governor

*When your Agent has too many plugins and doesn't know which one to use — let Skill Governor be the judge.*

| Property | Value |
|----------|-------|
| Compatible Platforms | Claude Code / Codex / OpenCode / Cursor |
| Complexity | Medium |
| Has Scripts | `reconcile.py`, `init_policy.py`, `report.py`, `create_ref.py` |
| Has References | `references/` directory |

**What it does**: Scans installed Agent Skills, merges conflicts via a policy file, and generates a routing registry plus conflict report. Supports single-directory save with `SKILL.REF` references to avoid duplication across directories.

**Good for**: Users with multiple Agent plugins who need unified skill routing management.

**Not for**: Users with only one or two skills and no conflict scenarios.

---

## Install

Tell your Agent:

```
Install this skill: https://github.com/sljdxde/schrodinger-skills/tree/main/skill-governor
```

---

## Registry

| Skill | ClawHub | Tessl |
|-------|---------|-------|
| skill-governor | v0.1.0 | 0.1.0 |

---

## License

[MIT](LICENSE)
