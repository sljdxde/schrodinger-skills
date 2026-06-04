---
name: skill-governor
description: >-
  Use when managing installed agent skills or plugins, especially after installing
  new skills/plugins, resolving duplicate skill capabilities, generating or updating
  skill-policy.yaml, skill-state.yaml, skill-registry.yaml, reviewing skill routing
  conflicts, creating SKILL.REF references for single-directory save, or when the
  user mentions "skill governance", "plugin conflicts", "skill routing", "skill
  management", "duplicate skills", "which skill to use", "skill policy", "skill
  registry", "reconcile skills", "skill conflicts", "技能管理", "插件冲突",
  "技能路由", "技能治理", "冲突解决", "重复技能", "技能策略".
  Triggers on: '/skill-governor', 'skill governor', 'govern skills', 'reconcile',
  'skill conflicts', 'plugin conflicts', 'skill routing', 'skill management',
  'duplicate skills', 'skill policy', 'skill registry', 'SKILL.REF', 'create ref',
  'single directory save', '技能管理', '插件冲突', '技能路由', '冲突解决'.
  Compatible with: Claude Code, Codex, OpenCode, OpenClaw, Cursor.
  Do not undertrigger — if the user has multiple agent plugins installed and is
  asking about which one to use, or if they mention skill/plugin management in any
  form, this skill should activate.
---

# Skill Governor

Govern installed agent skills with policy, registry reconciliation, and conflict reports.

## When to Use

- After installing new skills or plugins
- When multiple skills compete for the same capability
- When the user wants to see which skills are active/shadow/disabled
- When creating SKILL.REF references for single-directory save
- When initializing or updating skill policy

## Core Concepts

**Capabilities** group skills that do the same job (e.g., `document.pdf`, `web.browsing`). Each capability has at most one `active` skill; the rest are `shadow`, `dependency-only`, or `disabled`.

**Policy** (`skill-policy.yaml`) is user-editable and syncable across machines. It declares which skill is primary for each capability and allows manual overrides.

**Registry** (`skill-registry.yaml`) is the generated routing table — the runtime truth for which skill handles what.

**References** (`SKILL.REF`) allow a skill to live in one canonical directory while other directories point to it, avoiding duplication.

## Workflow

### 1. Initialize Policy

```bash
python3 scripts/init_policy.py
```

Creates `~/.agents/skill-policy.yaml` with sensible defaults.

### 2. Reconcile Skills

```bash
python3 scripts/reconcile.py
```

Scans skill directories, merges with policy, writes registry and report.

Options:
- `--skill-dir <path>` — additional skill directory (repeatable)
- `--policy <path>` — custom policy file path
- `--registry <path>` — custom registry output path
- `--state <path>` — custom state output path
- `--report <path>` — custom report output path

### 3. View Report

```bash
python3 scripts/report.py
```

Prints the latest conflict report.

### 4. Create References (Single-Directory Save)

```bash
python3 scripts/create_ref.py /path/to/canonical/skill /path/to/reference/location
```

Creates a `SKILL.REF` file that points to the canonical skill directory. Use this when a skill is installed in multiple locations — keep the real files in one place and reference from others.

## Statuses

| Status | Meaning |
|--------|---------|
| `active` | Default/primary skill for a capability |
| `shadow` | Installed but not preferred unless explicitly requested |
| `dependency-only` | Installed for a plugin, hidden from global routing |
| `disabled` | Manually blocked by policy |
| `missing` | Previously known but no longer found locally |
| `review-required` | Detected but not confidently categorized |

## Policy Overrides

```yaml
version: 1
capabilities:
  web.browsing:
    primary: web-access
    candidates:
      web-access:
        status: active
skills:
  lark-mail:
    capability: communication.email
  aihot:
    capability: news.ai
```

- `capabilities.<id>.primary` — set the default skill for a capability
- `capabilities.<id>.candidates.<name>.status` — force a status
- `skills.<name>.capability` — manually categorize when inference is wrong

## Files

| File | Location | Purpose |
|------|----------|---------|
| `skill-policy.yaml` | `~/.agents/` | User-editable policy (syncable) |
| `skill-state.yaml` | `~/.agents/` | Machine-local scan result |
| `skill-registry.yaml` | `~/.agents/` | Generated routing registry |
| `skill-registry-report.md` | `~/.agents/` | Generated conflict report |
| `SKILL.REF` | any skill dir | Reference to canonical skill directory |

## Rules

- Do not delete plugin-installed skills to resolve overlap.
- Treat plugin-installed skills as `dependency-only` unless policy promotes them.
- Keep existing `primary` choices unless the user explicitly asks to change them.
- New standalone skills for an existing capability should start as `shadow`.
- If a skill description is broad or forceful, flag it for review instead of promoting it.

## References

- [references/architecture.md](references/architecture.md) — System architecture and data flow
- [references/policy-examples.md](references/policy-examples.md) — Advanced policy configuration examples
