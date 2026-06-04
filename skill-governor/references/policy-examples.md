# Policy Examples

## Basic: Set Primary Skill

```yaml
version: 1
capabilities:
  document.pdf:
    primary: pdf
  web.browsing:
    primary: web-access
```

## Override Skill Status

Force a specific skill to be disabled:

```yaml
version: 1
capabilities:
  document.pdf:
    primary: pdf
    candidates:
      old-pdf-tool:
        status: disabled
```

## Manual Capability Assignment

When keyword inference fails, manually assign a skill:

```yaml
version: 1
skills:
  lark-mail:
    capability: communication.email
  aihot:
    capability: news.ai
  my-custom-tool:
    capability: custom.category
```

## Plugin-Aware Configuration

Plugin-installed skills default to `dependency-only`. Promote them if needed:

```yaml
version: 1
policies:
  newPluginSkill: shadow  # changed from dependency-only
capabilities:
  web.browsing:
    primary: plugin-browser
```

## Cross-Machine Sync

The policy file is designed to be synced across machines. Machine-specific state
is in `skill-state.yaml` (not synced). Only sync:

- `skill-policy.yaml`

Do NOT sync:

- `skill-state.yaml`
- `skill-registry.yaml`
