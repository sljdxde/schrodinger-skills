# Skill Governor Architecture

## Data Flow

```
skill dirs ──scan──> state ──+policy──> registry ──> report
                              │
                         lock file
                     (plugin metadata)
```

## Components

### reconcile.py (Core Engine)

1. **Load** — reads policy YAML and previous registry
2. **Scan** — walks skill directories, parses `SKILL.md` frontmatter, resolves `SKILL.REF` references
3. **Resolve** — maps each skill to a capability (policy override or keyword inference)
4. **Assign** — determines status for each candidate (active/shadow/disabled/etc.)
5. **Write** — outputs state, registry, and report files

### init_policy.py

Seeds a default `skill-policy.yaml` with 8 capability-to-primary mappings.

### report.py

Reads and prints the latest conflict report.

### create_ref.py

Creates `SKILL.REF` files for single-directory save.

## Key Design Decisions

- **Zero dependencies**: only Python stdlib, no PyYAML
- **Hand-rolled YAML parser**: simple enough for the policy/registry format, avoids external deps
- **Keyword inference**: heuristic-based capability matching, overridable via policy
- **Reference resolution**: `SKILL.REF` files are resolved during scan, transparent to the registry
