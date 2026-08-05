---
name: ob
description: "Operate the user's local Obsidian vault through the ob CLI for checks, vault resolution, listing, reading, searching, creating, updating, appending, moving, opening, and deleting notes. Use whenever a local vault operation is required."
version: 0.2.0
category: productivity
tags: [codex, obsidian, vault, markdown, knowledge-base]
---

# Obsidian Local Vault Operator

Use the local `ob` CLI as the only write boundary for an Obsidian vault. Higher-level skills such as `ob-llm-wiki` decide what should happen; this skill performs the concrete vault operation.

## Preflight

Before any vault work, run:

```bash
ob check --json
ob vault current --json
```

If `ob` is missing, install the CLI dependency and make the helper available before continuing:

```bash
uv tool install --force obsidian-cli==1.0.2
```

The bundled `scripts/ob.py` is the local helper implementation. When installing this skill for Codex, keep that script at the same skill directory so the wrapper can execute it.

Default vault resolution order:

1. `OB_VAULT_PATH`
2. `~/.config/ob/config.json`
3. the registered Obsidian vault whose basename is `知识库`
4. the only registered vault, if exactly one exists

If more than one vault matches, ask the user to choose. Never silently write to a guessed vault.

## Core commands

```bash
ob version
ob config show --json
ob config set --vault-path "/abs/path/to/vault"
ob vault list --json
ob vault current --json
ob ls [subdir] --json
ob read path/to/note.md --json
ob search "keyword" --json
ob mkdir path/to/folder
ob save path/to/note.md --file /tmp/content.md --json
ob update path/to/note.md --file /tmp/content.md --json
ob append path/to/log.md --file /tmp/entry.md --json
ob mv old/path.md new/path.md
ob open [path]
ob rm path/to/note.md
```

## Operating rules

- Treat the resolved vault filesystem as the source of truth.
- Keep all vault writes inside the resolved vault; use a temporary file for large bodies, then pass it with `--file`.
- Prefer Markdown and relative vault paths.
- Preserve `.obsidian/` and `.trash/` unless the user explicitly asks to change them.
- Read before update; preserve existing frontmatter, tags, links, and unrelated content.
- For sensitive notes, return only the requested fields or a narrow paraphrase.
- Before `ob rm` or recursive deletion, report the target and impact. Prefer a recoverable move or a new version when possible.

## Common patterns

```bash
ob read raw/example.md
ob save concepts/topic.md --file /tmp/topic.md --json
ob search "schema.md" --json
ob ls --json
ob ls raw --json
```

## Failure handling

- If vault resolution fails, stop and explain how to set `OB_VAULT_PATH` or choose a registered vault.
- If a path is outside the vault, stop; do not bypass the path guard.
- If a write fails after content generation, keep the generated content in a temporary file and report the failed target.
- Do not claim a note was changed until the CLI returns success.
