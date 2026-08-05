---
name: ob-llm-wiki
description: "Use with Codex and Obsidian for a local personal knowledge base: inspect, search, ingest, structure, audit, archive, and maintain Markdown notes through the ob CLI. Trigger on 知识库, 个人知识库, 查知识库, 存入知识库, wiki, LLM wiki, 知识查询, 知识库审计, 切换知识库, or 归档对话."
version: 0.3.0
category: research
tags: [codex, obsidian, ob, wiki, knowledge-base, markdown]
---

# Codex + Ob Personal Knowledge Base

Use this skill as the orchestration layer for a local Obsidian knowledge base. The companion `ob` skill is required for the actual vault operations.

## Operating model

Keep the responsibilities explicit:

- **Codex** interprets the request, chooses the narrowest useful read set, extracts reusable knowledge, and decides which indexes or logs need updating.
- **`ob`** is the filesystem boundary. Use it for vault checks, reads, searches, directory creation, saves, updates, appends, moves, and deletes.
- **Obsidian** is the human-facing interface for browsing, backlinks, visual review, and manual edits.

Do not invent note IDs or write arbitrary absolute paths. Use relative vault paths as the stable identifiers, and keep temporary generated content outside the vault until it is ready to save.

## Preflight

Run these before responding to a knowledge-base request:

```bash
ob check --json
ob vault current --json
```

If `ob` is unavailable, use the companion `ob` skill to repair or install the local helper before touching notes. If vault resolution fails, ask the user to choose a vault or set `OB_VAULT_PATH`; do not guess.

## Session startup

1. Read `ob-wiki-registry.md` if it exists.
2. If it does not exist, read `schema.md`, `index.md`, and scan the standard directories.
3. Treat `schema.md` as the source of truth for page shape, naming, and directory meaning.
4. If the vault has multiple local wikis, ask which one to use before reading content.
5. Keep the first read narrow. Search first, then read only the matched notes needed for the answer.

The default layout is:

```text
<vault>/
├── schema.md
├── index.md
├── log.md
├── ob-wiki-registry.md
├── raw/
├── entities/
├── concepts/
├── comparisons/
└── queries/
```

## What this skill can do

### Query

For direct lookups, start with:

```bash
ob search "keyword" --json
```

For scope-constrained requests, search the exact marker first:

```bash
ob search "标签：#个人" --json
ob search "标签：#工作" --json
```

Then combine the scope with the user's topic and read only the matching notes. If the result is ambiguous, consult `schema.md` or `index.md` before broadening the search.

### Ingest and structure

1. Preserve the source in `raw/` when provenance matters.
2. Extract durable concepts, entities, comparisons, or query conclusions into their corresponding directories.
3. Add or preserve a scope tag near the top of every Markdown note: `标签：#个人` by default, or `标签：#工作` when the user explicitly identifies work content.
4. Preserve existing tags and append missing metadata; do not silently replace tags.
5. Update `index.md` and append a short entry to `log.md` after a meaningful mutation.
6. Prefer wikilinks such as `[[concepts/topic]]` and `[[raw/source-note]]`.

Keep `raw/` immutable when possible. Corrections and interpretations belong in derived pages so the original source remains traceable.

### Audit

Check the following as one pass:

- missing standard directories or control files
- broken wikilinks and stale index references
- notes stranded outside the standard structure
- drift between `schema.md`, `index.md`, and `log.md`
- notes missing a scope tag or carrying conflicting `#个人` and `#工作` tags

For an audit-only request, report findings and proposed changes without writing anything.

### Archive conclusions

Archive a reusable conclusion into `queries/` or `concepts/`, depending on whether it answers a concrete question or expresses a durable idea. Include the date, source links or note links, the conclusion, uncertainty, and the next action when relevant. Then update the index and log.

## Tagging and privacy

- Scope tags are classification metadata, not access control.
- A note should not receive both `#个人` and `#工作` unless the user explicitly says it spans both contexts.
- For sensitive notes, read the smallest possible set and return only the requested field or a short paraphrase.
- Never expose secrets, tokens, private keys, or unrelated personal data in the response or generated artifacts.

## Composition with other skills

This bundle contains the two skills needed for the core Codex + Ob workflow:

- `ob-llm-wiki` decides what the knowledge-base operation means.
- `ob` performs the local vault operation.

Optionally compose with other skills when the task demands it:

- `memory-forge` for turning study material into cards, quizzes, or review packages before archiving durable conclusions.
- A web/search skill for current external sources; record source and access date in the resulting note.
- A document/PDF skill for converting source files before ingestion.

Do not duplicate those optional skills inside the vault workflow; use them only for the part they own and return a clean Markdown result to this skill.

## Common commands

```bash
ob read schema.md
ob read index.md
ob ls raw --json
ob search "账号信息" --json
ob save queries/example.md --file /tmp/example.md --json
ob append log.md --file /tmp/log-entry.md --json
```

## Output rules

- State which vault was used when it matters.
- Separate source facts, derived conclusions, and uncertainty.
- Say what was read and what was changed at a useful level of detail, without dumping sensitive note contents.
- For write operations, report the exact relative paths changed and whether `index.md` or `log.md` was updated.
- For failed preflight or partial work, say what blocked the operation and what remains.

