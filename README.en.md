<div align="center">

[中文](./README.md) · **English**

# Schrodinger Skills

#### Practical AI Skills, ready to use

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-7-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![Cursor](https://img.shields.io/badge/Cursor-Skill-8B5CF6?style=flat-square)

</div>

Each Skill is a structured instruction set that Agents can load directly, following the [Agent Skills](https://agentskills.io) open standard. Works with Claude Code, Codex, OpenCode, and Cursor.

Installation is simple — just one sentence to your Agent. No path or configuration hassle.

*Note for English readers: This project originated in the Chinese AI community. Contributions and translations are welcome.*

Skills in this repository that provide self-update support can compare their local folder with the latest GitHub copy, back up and sync themselves when needed, and update backing tool packages when the skill depends on one. Bundles also provide an explicit installation entry point.

Self-update uses **semantic versioning**: each skill declares a `version` in its `SKILL.md` frontmatter (bundles use a root-level `VERSION` file). The updater compares the remote version first and downloads nothing when versions match; if either side lacks a version it falls back to the legacy file-manifest comparison, so old scripts and old installs stay fully compatible. Rules are in [docs/versioning.md](./docs/versioning.md).

The self-update helper requires `python`; npm-backed skills such as Skills-Doctor also require `npm` for package updates.

---

## Table of Contents

| Name | One-liner | Link |
|---|---|---|
| [学区房助手 (House-Buying)](./house-buying) | Due-diligence & decision analysis for homes across 46 Chinese cities: 5-tier source hierarchy, citation-backed anti-fabrication, price momentum, school premium, student-cohort projection, and price forecasts | [SKILL.md](./house-buying/SKILL.md) |
| [Skills-Doctor](./skills-doctor) | Diagnose and govern local AI Agent Skills — detect risks, conflicts, duplicates, zombies | [SKILL.md](./skills-doctor/SKILL.md) |
| [Memory-Forge](./memory-forge) | Forge any study material into memorable cards, stories, mind-maps, quizzes, and an Ebbinghaus/SM-2 review schedule | [SKILL.md](./memory-forge/SKILL.md) |
| [MTD-Download](./mtd-download) | Multi-threaded / chunked download for large files via curl, auto-detects Range support, with live progress and speed | [SKILL.md](./mtd-download/SKILL.md) |
| [Skill-Architect](./skill-architect) | Turns vague needs or personal/domain experience into installable AI Skills through first-principles 10-facet decision-tree interviews, blueprint compilation, and quality evaluation | [SKILL.md](./skill-architect/SKILL.md) |
| [Personal-Knowledge-Base](./personal-knowledge-base) | A Codex + Obsidian + `ob` CLI bundle for local personal knowledge management, including `ob-llm-wiki` and `ob` | [README.md](./personal-knowledge-base/README.md) |

---

## Install

In any Agent that supports Skills (Claude Code, Codex, Cursor, etc.), just say:

```
Install this skill: https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

Replace `<skill-name>` with the one you want. The Agent will clone it to the right directory automatically.

The personal knowledge base is a bundle. Install the whole directory and explicitly ask the Agent to install both components:

```
Install the complete personal-knowledge-base bundle from schrodinger-skills, including ob-llm-wiki and ob. Do not install only one component.
```

---

## Skills

### [学区房助手 (House-Buying)](./house-buying)

Due diligence and decision support for Chinese residential property purchases. It is designed for target communities, school-district homes, area comparisons, and buy/watch decisions, with explicit evidence tracking for transaction prices, listings, school-premium comparisons, admissions policy, student sources, community demographics, and city fundamentals.

**Key Features:**
- **46 pre-configured cities**: provincial capitals, municipalities, and major prefecture cities (Shenzhen, Suzhou, Ningbo, Qingdao, Luoyang, etc.); each city's government sources (housing, net-sign, registry, statistics, education) are URL-verified, so new cities plug in at zero cost
- **5-tier source hierarchy (T0–T4)**: T0 Beike/Lianjia + Woaiwojia as mandatory dual-source cross-check; T1 official sources (housing/registry/statistics/education) carry the highest conflict-resolution weight; T2 government apps (Zheli Ban / Suishen Ban / Jintong / Yushiban) and city mini-programs; T3 Zhuge/Anjuke/Fang/58 as cross-validation only; T4 public opinion as leads
- **Citation-backed anti-fabrication**: every data point must carry source + real URL + publish/access date + caliber + consistency; multi-source conflicts resolved by "newest > most authoritative caliber > closest to primary (official net-sign/gov)", with ≤5% treated as consistent, >5% disclosed side-by-side, hard conflicts flagged "unverified"
- **Single-dimension-first rollout**: nail the "price" dimension first (listing/transaction monthly timeline + MoM/YoY/N-month change + viewings/inventory), then expand to volume, supply/demand, land transfer, school policy, migration, and credit
- Monthly price timelines for the same community, including peak/trough/current values, volatility, and sample size (no fabrication when samples are thin)
- Anti-scraping adapters for web sources: browser-like requests, cookies/headers, optional Playwright rendering of public pages
- Compare school-district homes with nearby non-school-district or weaker-school alternatives to quantify the education premium
- **Student-cohort projection**: middle-school outcomes lag birth cohorts by ~9–15 years; reconstruct the historical cohort, compare it with the current cohort, and project the future (3–5 yrs of outcomes + birth-cohort comparison + base/optimistic/pessimistic scenarios) — answering "what will my child's future look like if I buy now"
- Analyze school outcomes, admission rules, seat warnings, and student-source quality
- Build a community demographic profile instead of relying only on price
- Produce base/optimistic/pessimistic housing-price forecast scenarios
- Give a clear buy / cautious buy / watch / do-not-buy recommendation

**Recent upgrade (v1.4.0):**
- Source model upgraded from "dual-platform cross-check" to a **T0–T4 five-tier hierarchy**; official sources hold the highest weight in conflict resolution
- Added **citation five-elements**: every data point is traceable (source / URL / date / caliber / consistency) to eliminate fabrication
- Introduced the **single-dimension-first** strategy with `references/dimension-network.md`
- Added **student-cohort projection** methodology (`references/school-cohort-analysis.md`): outcomes lag birth cohorts by 9–15 years; project the future by comparing historical vs current cohorts
- City registry expanded 45 → **46 cities** (Luoyang added, gov URLs verified)
- Decision record: `docs/adr/0005-source-hierarchy-and-dimension-network.md`; semantic versioning, currently 1.4.0

**Usage:**

Tell your Agent:
```
Use house-buying to analyze whether Hangzhou Yaojiang Wendingyuan is worth buying for self-use plus school access under a 4M RMB budget
```
Or declare another city:
```
Use house-buying to analyze Shanghai Zhangjiang Tangcheng Haoyuan for self-use plus school access under an 8M RMB budget, city: Shanghai
```

The Agent will verify public data first, then produce an evidence-backed report with a monthly price timeline, risks, comparisons, and an actionable recommendation.

**Auto-update:**
- Run `python scripts/update_self.py --apply` before use
- Checks and syncs the latest `house-buying` skill folder from GitHub

### [Skills-Doctor](./skills-doctor)

Diagnose and govern local AI Agent Skills. Supports Claude Code, Codex, Cursor, OpenCode and more. Detects risks, conflicts, duplicates, zombies and generates fix suggestions.

**Key Features:**
- 7 diagnostic types: risk, conflict, duplicate, version drift, zombie, description quality, scan warnings
- Generate fix prompts (fix command)
- Export reports in Markdown/HTML/JSON
- CI integration (--ci --fail-on)

**Usage:**

Just tell your Agent:
```
Please use agent-skill-doctor to diagnose my local Agent Skills
```

The Agent will run diagnostics, generate reports, and output a fix plan. You can also ask for specifics:
```
Check for duplicate skills
Detect zombie skills
```

**Auto-update:**
- Run `python scripts/update_self.py --apply` before use
- Checks and syncs the latest `skills-doctor` skill folder from GitHub
- Checks and updates the `agent-skill-doctor` npm package to the latest version

### [Memory-Forge](./memory-forge)

Forge any study material (pasted text, `.txt` / `.md` / `.docx` / `.pdf`) into something easy to understand and remember. It uses memory science to break knowledge into small cards, paired with stories / analogies / complementary visuals, quizzes, and a review schedule — because brains remember pictures and stories far better than raw text.

**Key Features:**
- One concept per card: each card holds a single idea to avoid overloading working memory
- Abstract concepts always get a story / analogy; visuals must complement (not decorate) the text
- Flip cards: question on the front → plain-language answer + key points + mnemonic on the back
- Knowledge mind-map: the whole relationship graph as a clickable, highlightable tree
- Quiz section: answer first, then reveal the explanation (testing effect)
- Ebbinghaus / SM-2 review plan: 0–5 self-rating instantly computes the next interval
- Web deep-dive: proactively fetches authoritative explanations + diagrams for unfamiliar terms, with source and date
- Dual delivery: inline explanation in chat + export an offline, self-contained HTML / Markdown package
- Theme: `--theme claude` (default, warm ivory + clay accent + serif display, Claude Design style) / `--theme editorial` (warm paper + serif display, magazine style) / `--theme swiss` (near-white + single Klein Blue + all sans-serif + right angles, Swiss International style); all fully offline, emoji-free, switchable anytime

**Usage:**

Tell your Agent:
```
Use memory-forge to help me understand and remember these frontend notes, and give me a downloadable package
```
Or just paste / upload material:
```
(paste study text or upload a docx/pdf) help me memorize the key points quickly
```

The Agent extracts concepts, then progressively generates cards, stories, a mind-map, quizzes, and a review plan, finishing with inline explanation and a downloadable package.

**Auto-update:**
- Run `python scripts/update_self.py --apply` before use
- Checks and syncs the latest `memory-forge` skill folder from GitHub

### [Personal-Knowledge-Base](./personal-knowledge-base)

A local knowledge-base bundle designed specifically for **Codex + Obsidian + the `ob` CLI**. Codex interprets requests, keeps reads narrow, extracts reusable conclusions, and maintains indexes; `ob` is the vault read/write boundary; Obsidian remains the human-facing browsing and review surface.

**The bundle contains two skills that should be installed together:**
- `ob-llm-wiki`: session startup, querying, ingest, structuring, auditing, and conversation archiving
- `ob`: vault checks, resolution, listing, reading, searching, writing, moving, and deleting

**It can:**
- Query existing notes by scope, tags, directories, and keywords while reading only what is needed
- Store conclusions and source material under `raw/`, `concepts/`, `entities/`, `comparisons/`, and `queries/`
- Maintain `index.md`, `log.md`, wikilinks, and `#个人` / `#工作` scope tags
- Audit missing directories, broken links, stranded notes, index drift, and tag conflicts
- Refuse to guess between multiple vaults and minimize sensitive reads and outputs

**Install:**

Tell your Agent:

```
Install this directory as a bundle:
https://github.com/sljdxde/schrodinger-skills/tree/main/personal-knowledge-base
Install both ob-llm-wiki and ob.
```

See [personal-knowledge-base/README.md](./personal-knowledge-base/README.md) for the full capability description, layout, and examples.

**Auto-update:**
- If installed by copying the whole bundle directory, run `python scripts/update_self.py --apply` before use
- Automatically checks and syncs the `personal-knowledge-base` bundle directory on GitHub (covering both `ob-llm-wiki` and `ob` sub-skills)
- If sub-skills were installed separately via `install_bundle.py`, re-run `python scripts/install_bundle.py --replace` to update

### [MTD-Download](./mtd-download)

A multi-threaded download tool built on the system `curl`. It splits a large file into byte-range chunks downloaded in parallel — much faster when the server supports `Range`. When Range is unsupported, the file is small, or the size is unknown, it falls back to single-threaded streaming. Pure standard library plus system `curl`; no `pip install` needed.

**Key Features:**
- Auto-detects file size and server `Range` support; multi-threaded only when Range works and file > 4MB
- Multi-threaded writes use `os.pwrite` at absolute offsets so chunks never overlap; even if the server ignores Range, only this chunk's bytes are kept
- Single-threaded fallback: works without Range, for files ≤ 4MB, or when size is unknown
- Live progress bar (percent / downloaded / speed / ETA), all on stderr so stdout stays clean
- Per-chunk retry (3 tries); on overall failure the incomplete output is removed instead of left behind
- Exit code `0` on success, `1` on failure, for easy scripting

**Usage:**

Tell your Agent:
```
Use mtd-download to download this large file: https://example.com/big-file.iso
```

Or run directly:
```bash
# default 16 threads, filename inferred from the URL
python scripts/mtd.py <URL>

# specify thread count and output name
python scripts/mtd.py <URL> -t 32 -o myfile.iso
```

The Agent probes first, then downloads with the right strategy and reports the result.

**Auto-update:**
- Run `python scripts/update_self.py --apply` before use
- Checks and syncs the latest `mtd-download` skill folder from GitHub

### [Skill-Architect](./skill-architect)

A Meta Skill that turns vague needs or personal/domain experience into **installable AI Skills**. The core insight: users usually know *what problem* they want to solve, but not *what capabilities* a Skill should have — so the AI acts as product manager + domain expert and runs a **first-principles interview**, then produces a blueprint, compiles a package, and evaluates the result.

**Key Features:**
- First-principles decomposition: interviews are built around the 10 facets a Skill must define (identity, audience, goal, input, process, analysis framework, output spec, boundaries, data, interaction/quality) — no facet is skipped
- Decision tree + question clusters: each facet is asked as a 3–6 question cluster with branching drill-downs, not one question at a time; inferable items become assumptions instead of clutter
- Conditional branches: analysis/decision Skills must drill into the "analysis framework" (dimensions, scoring, evidence rigor, visualization); Skills with deliverables must specify the "output spec" (md / html / json / chat / multi-file, with further drill-downs on interactivity and naming)
- Dual-path interviews: Path A (Need→Skill) + Path B (Experience→Skill), with experience uniformly mapped onto the same facet table
- Domain knowledge library: built-in capability checklists for study / travel / investment / creation plus a generic template, to surface unknown needs
- Interview-to-output: conclusions land in `blueprint.json` fields (`input_spec`, `output_spec`, `analysis`, `interaction_model`), which `compile_skill.py` renders directly into the generated package's Input / Analysis / Output / Interaction sections
- `compile_skill.py` full scaffolding: produces a package with the exact same layout as house-buying (SKILL.md + agents/openai.yaml + update_self.py + references/ + evaluations/), instantly installable and self-updating
- 4-dimension evaluation: professionalism / completeness / task success rate / error rate, written to `evaluations/self-eval.md`

**Usage:**

Tell your Agent:
```
Use skill-architect to build a house-buying assistant for me
```
Or for experience distillation:
```
I've been in real estate for 20 years; turn my experience into an AI consultant
```

The Agent interviews you, produces a blueprint, compiles a package, and evaluates it. You can also run the compiler directly:
```bash
python scripts/compile_skill.py --blueprint examples/sample-blueprint.json --out ./skills
```

**Auto-update:**
- Run `python scripts/update_self.py --apply` before use
- Checks and syncs the latest `skill-architect` skill folder from GitHub

---

## About

Schrodinger Skills is an actively maintained collection of AI Skills. Each skill is battle-tested in real projects before being open-sourced.

Want to contribute a skill? PRs welcome. Issues and suggestions? Open an Issue.

---

<div align="center">

[MIT License](./LICENSE) · Free to use / modify / redistribute

Made by [@sljdxde](https://github.com/sljdxde)

</div>
