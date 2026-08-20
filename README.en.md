<div align="center">

[中文](./README.md) · **English**

# Schrodinger Skills

#### Practical AI Skills, ready to use

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-8-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![Cursor](https://img.shields.io/badge/Cursor-Skill-8B5CF6?style=flat-square)

</div>

Each Skill is a structured instruction set that Agents can load directly, following the [Agent Skills](https://agentskills.io) open standard. Works with Claude Code, Codex, OpenCode, and Cursor.

Installation is simple — just one sentence to your Agent. No path or configuration hassle.

*Note for English readers: This project originated in the Chinese AI community. Contributions and translations are welcome.*

---

## Table of Contents

| Name | One-liner | Link |
|---|---|---|
| [House-Buying](./house-buying) | Due-diligence & decision analysis for homes across 47 Chinese cities: official Beike CLI data, 5-tier source hierarchy, citation-backed anti-fabrication, price momentum, school premium, student-cohort projection, and price forecasts | [SKILL.md](./house-buying/SKILL.md) |
| [Layout-Analysis](./layout-analysis) | Floor-plan analysis from a web link / floor-plan image / manual data: space utilization, layout flow, lighting/ventilation, privacy, and renovation potential, with a scored report and fit-for-whom | [SKILL.md](./layout-analysis/SKILL.md) |
| [Skills-Doctor](./skills-doctor) | Diagnose and govern local AI Agent Skills — detect risks, conflicts, duplicates, zombies, and generate fix suggestions | [SKILL.md](./skills-doctor/SKILL.md) |
| [Memory-Forge](./memory-forge) | Forge any study material into memorable cards, stories, mind-maps, quizzes, and an SM-2 review schedule with a gamification system | [SKILL.md](./memory-forge/SKILL.md) |
| [MTD-Download](./mtd-download) | Multi-threaded / chunked download for large files via curl, auto-detects Range support, WAF/rate-limit fallback, with live progress and speed | [SKILL.md](./mtd-download/SKILL.md) |
| [Skill-Architect](./skill-architect) | Turns vague needs or personal/domain experience into installable AI Skills through first-principles 10-facet decision-tree interviews, blueprint compilation, and quality evaluation | [SKILL.md](./skill-architect/SKILL.md) |
| [Milestone-Gate](./milestone-gate) | Milestone-gated execution for complex tasks: break work into milestones with acceptance criteria, present each deliverable for confirmation, and re-run the previous milestone on failure | [SKILL.md](./milestone-gate/SKILL.md) |
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

### [House-Buying](./house-buying)

Due diligence and decision support for Chinese residential property purchases. Designed for target communities, school-district homes, area comparisons, and buy/watch decisions, with mandatory evidence tracking for transaction prices, listings, school-premium comparisons, admissions policy, student sources, community demographics, and city fundamentals, producing a self-contained HTML report.

**Key Features:**

- **47 pre-configured cities**: provincial capitals, municipalities, and major prefecture cities (Shenzhen, Suzhou, Ningbo, Qingdao, Luoyang, etc.); each city's government sources (housing, net-sign, registry, statistics, education) are URL-verified, so new cities plug in at zero cost
- **Official Beike CLI integration**: on load it auto-detects whether the local Beike CLI is installed and authenticated (`beike-check`), preferring the official real-data channel for listings / transactions / price trends / community profiles (all with real ke.com detail URLs); if absent, it can be skipped with a web-search fallback — never fabricates
- **5-tier source hierarchy (T0–T4) + T1.5**: T0 Beike/Lianjia + Woaiwojia as mandatory dual-source cross-check; T1 official sources carry the highest conflict-resolution weight; T1.5 city-local high-frequency sources (Hangzhou housing-data / Xiaoji-style) approach net-sign caliber; T2 government apps (Zheli Ban / Suishen Ban / Jintong); T3 Zhuge/Anjuke/Fang/58 as cross-validation only; T4 public opinion as leads
- **Citation-backed anti-fabrication (mandatory)**: every data point must carry source + real URL + publish/access date + caliber + consistency; conflicts resolved by "newest > most authoritative caliber > closest to primary (official net-sign/gov)", with ≤5% treated as consistent, >5% disclosed side-by-side, hard conflicts flagged "unverified"
- **Single-dimension-first rollout**: nail the "price" dimension first (listing/transaction monthly timeline + MoM/YoY/N-month change + viewings/inventory), then expand to volume, supply/demand, land transfer, school policy, migration, and credit
- **Unified multi-platform search**: `python scripts/data_sources.py search` runs "Beike CLI first + Woaiwojia + optional T3 cross-check" in one call, returning per-platform status and the last 10 real transactions; manual entry fallback via `gen_styled_report.py --chengjiao`
- **Monthly price timelines**: inline SVG charts (listing vs transaction dual series) with peak/trough/current values, volatility, and sample size (no fabrication when samples are thin)
- **School-district toolkit**: quantify the education premium vs nearby non-school-district homes; school tier rating (tier 1–4 + rationale); **student-cohort projection** (outcomes lag birth cohorts by ~9–15 years, reconstruct historical vs current cohorts to project the future); title-occupation / hukou-years pre-purchase self-check list and contract template
- **2026 policy baseline snapshot**: multi-school assignment / teacher rotation / hukou decoupling / seat locking / warnings structured per city, used as a default high-weight scenario
- **Three-scenario price forecast**: base/optimistic/pessimistic across 6–12 months, 1–3 years, and 3–10 years with confidence ranges
- **Script-generated self-contained HTML report**: visual theme chosen by the user — warm / editorial / cinematic / glass / data / olive (same content, CSS only); SVG charts, tables, and citation links all inlined with no external dependencies
- Clear buy / cautious buy / watch / do-not-buy recommendation (with confidence)

**Usage:**

Tell your Agent:

```
Use house-buying to analyze whether Hangzhou Yaojiang Wendingyuan is worth buying for self-use plus school access under a 4M RMB budget
```

Or declare another city:

```
Use house-buying to analyze Shanghai Zhangjiang Tangcheng Haoyuan for self-use plus school access under an 8M RMB budget, city: Shanghai
```

The Agent will detect the Beike CLI status → collect requirements → verify public data → produce an evidence-backed report with a monthly price timeline, risks, comparisons, and an actionable recommendation, letting you pick a visual theme before delivery.

---

### [Layout-Analysis](./layout-analysis)

A floor-plan analysis tool for general buyers. From a web link, a floor-plan image, or manual fields, it produces a complete report with pros/cons, renovation advice, lighting/ventilation/orientation, and an overall score.

**Key Features:**

- **Three input modes**: web link (scrape Beike-style pages), floor-plan image (read-and-parse), or manual fields (area / layout / orientation / dimensions); asks when key info is missing, never guesses
- **Layout parsing**: extracts the room list, per-room area and dimensions, orientation, window openings, and load-bearing-wall clues into structured data
- **Five-dimension analysis**: space utilization / circulation / lighting-ventilation / privacy / renovation potential, each with verifiable rationale
- **Composite scoring**: each dimension scored 0–5, weighted into a total; gives a pros/cons list and fit-for-whom (self-use / upgrade / investment)
- **Renovation advice**: flags load-bearing / shear-wall risks and common-area limits; marks uncertain items for on-site confirmation
- **Multi-layout comparison** (optional)
- **Clear boundaries**: excludes price appraisal & investment advice, legal/title/school-district judgement, and renovation quoting/construction/feng-shui

**Usage:**

Tell your Agent:

```
Use layout-analysis to analyze this floor plan: <web link / floor-plan image / layout data>
```

Or paste area, layout, orientation, and dimensions directly. The Agent will ask for missing info, then produce a full report: overview → per-dimension analysis → renovation advice → scorecard → summary and fit-for-whom.

---

### [Skills-Doctor](./skills-doctor)

Diagnose and govern local AI Agent Skills. Supports Claude Code, Codex, Cursor, OpenCode and more. Detects risks, conflicts, duplicates, zombies and generates fix suggestions.

**Key Features:**

- 7 diagnostic types: risk, conflict, duplicate, version drift, zombie, description quality, scan warnings
- Generate fix prompts (filterable by type / severity)
- Export reports in Markdown / HTML / JSON
- CI integration (`--ci --fail-on`)
- Bundled npm package `agent-skill-doctor`, checked and updated to the latest automatically

**Usage:**

Just tell your Agent:

```
Please use agent-skill-doctor to diagnose my local Agent Skills
```

The Agent will run diagnostics, generate reports, and output a fix plan. You can also run commands directly:

```bash
# Full diagnosis (Chinese)
agent-skill-doctor diagnose --lang zh

# Targeted queries
agent-skill-doctor risks --json
agent-skill-doctor conflicts --json
agent-skill-doctor duplicates --json
agent-skill-doctor zombies --json

# Generate reports
agent-skill-doctor report --format md --lang zh
agent-skill-doctor report --format html --lang en --output ./reports/report.html

# Generate fix prompts
agent-skill-doctor fix --lang zh
agent-skill-doctor fix --type risk --severity high --lang zh

# CI integration: fail on high-severity issues
agent-skill-doctor diagnose --ci --fail-on high
```

Default scan paths: `~/.agent/skills`, `~/.agents/skills`, `~/.codex/skills`, `~/.claude/skills`, `~/.cursor/skills`, `~/.opencode/skills`, etc.

---

### [Memory-Forge](./memory-forge)

Forge any study material (pasted text, `.txt` / `.md` / `.docx` / `.pdf`) into something easy to understand and remember. It uses memory science to break knowledge into small cards, paired with stories / analogies / complementary visuals, quizzes, and a review schedule — because brains remember pictures and stories far better than raw text.

**Key Features:**

- One concept per card: each card holds a single idea to avoid overloading working memory
- Abstract concepts always get a story / analogy; visuals must complement (not decorate) the text
- Flip cards: question on the front → plain-language answer + key points + mnemonic on the back
- Knowledge mind-map: the whole relationship graph as a clickable, highlightable tree
- Quiz section: answer first, then reveal the explanation (testing effect)
- SM-2 / Ebbinghaus review plan: 0–5 self-rating instantly computes the next interval
- Web deep-dive: proactively fetches authoritative explanations + diagrams for unfamiliar terms, with source and date
- Gamification: built-in levels / XP / badge wall / streak (progress stored locally in the browser), with theme-based custom badges to boost engagement
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

---

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

---

### [MTD-Download](./mtd-download)

A multi-threaded download tool built on the system `curl`. It splits a large file into fixed small byte-range chunks downloaded in parallel — much faster when the server supports `Range`. When Range is unsupported, the file is small, WAF/rate-limit is hit, or the size is unknown, it falls back to single-threaded streaming. Pure standard library plus system `curl`; no `pip install` needed.

**Key Features:**

- Probe first: `curl -sIL` to get `content-length` and `accept-ranges`; multi-threaded only when Range works and file > 4MB
- Fixed small chunks + high concurrency + per-chunk fault tolerance: default 2MB under proxy / 5MB otherwise (`--chunk`), each chunk downloaded and retried independently (default 5 tries), avoiding "single-connection throttle + large-chunk hang"
- Per-thread independent redirect: avoids CDN auth expiry writing HTML error pages as file data
- Range non-zero check: if a sampled chunk is >95% zeros, the CDN's Range is deemed broken and it degrades to single-threaded
- WAF / rate-limit auto fallback: on 418/429/401/403/407/503 it stops concurrency and degrades, avoiding ban amplification
- Resume (`--resume`): records completed chunks and only fetches the rest on re-run; also scans large zero-holes in existing files and self-heals them
- Post-download integrity check: scans for large contiguous zero-holes + format validation (PDF head/tail, `file` detecting HTML error pages); never delivers a full-size but internally corrupted file
- Proxy bypass / mirror: `--noproxy` for direct connection; `--mirror ghproxy` wraps the URL as `https://ghproxy.net/<URL>`; GitHub `blob` links auto-rewrite to `raw.githubusercontent.com` direct links
- Progress on stderr (keeps stdout clean); exit code 0/1; optional `--sha256` verification; auto-clears macOS Gatekeeper quarantine after download

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

# adjust chunk size (small chunks resist CDN throttle-hang)
python scripts/mtd.py <URL> --chunk 2

# resume (fetch only remaining chunks, self-heal zero-holes)
python scripts/mtd.py <URL> --resume

# bypass transparent proxy for direct connection
python scripts/mtd.py <URL> --noproxy

# ghproxy mirror for direct connection (GitHub large files)
python scripts/mtd.py "https://github.com/owner/repo/blob/main/big.pdf" --mirror ghproxy

# verify against official SHA256 after download
python scripts/mtd.py <URL> --sha256 <official-hex-value>
```

The Agent probes first, then downloads with the right strategy and reports the result.

---

### [Skill-Architect](./skill-architect)

A Meta Skill that turns vague needs or personal/domain experience into **installable AI Skills**. The core insight: users usually know *what problem* they want to solve, but not *what capabilities* a Skill should have — so the AI acts as product manager + domain expert and runs a **first-principles interview**, then produces a blueprint, compiles a package, and evaluates the result.

**Key Features:**

- First-principles decomposition: interviews are built around the 10 facets a Skill must define (identity, audience, goal, input, process, analysis framework, output spec, boundaries, data, interaction/quality) — no facet is skipped
- Decision tree + question clusters: each facet is asked as a 3–6 question cluster with branching drill-downs, not one question at a time; inferable items become assumptions instead of clutter
- Conditional branches: analysis/decision Skills must drill into the "analysis framework" (dimensions, scoring, evidence rigor, visualization); Skills with deliverables must specify the "output spec" (md / html / json / chat / multi-file, with further drill-downs on interactivity and naming)
- Dual-path interviews: Path A (Need→Skill) + Path B (Experience→Skill), with experience uniformly mapped onto the same facet table
- Domain knowledge library: built-in capability checklists for study / travel / investment / creation plus a generic template, to surface unknown needs
- Interview-to-output: conclusions land in `blueprint.json` fields (`input_spec`, `output_spec`, `analysis`, `interaction_model`), which `compile_skill.py` renders directly into the generated package's Input / Analysis / Output / Interaction sections
- `compile_skill.py` full scaffolding: produces a package with the exact same layout as house-buying (SKILL.md + agents/openai.yaml + update_self.py + references/ + evaluations/), instantly installable
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

---

### [Milestone-Gate](./milestone-gate)

A milestone-gating workflow for complex tasks. At the start it breaks the goal into an ordered list of milestones, each with a deliverable and acceptance criteria. After each milestone it shows you the intermediate deliverable for confirmation; if it fails the bar, it re-runs only that milestone (keeping the already-passed ones) instead of redoing everything — turning "betting on the final result" into "correctable at every step", which saves tokens and time.

**Key Features:**

- Milestone decomposition: split complex tasks into a verifiable deliverable sequence with visible acceptance criteria up front
- Acceptance criteria: every milestone has explicit pass/fail checks — "good enough" is not a pass
- Stage delivery & confirmation: present each milestone's deliverable via preview/cards and ask for confirmation
- Correction loop: on failure, re-run only the current milestone while preserving completed ones
- Progress visibility: a task checklist shows status at all times
- Hazard front-loading: pause before irreversible/costly/external-side-effect steps, working with existing safety rules

**Usage:**

Tell your Agent:

```
Use milestone-gate to do X, confirm at each step
```

Or describe a complex task and say "plan first" / "step by step" — the Agent applies milestone-gating automatically; you can also invoke it explicitly.

---

## About

Schrodinger Skills is an actively maintained collection of AI Skills. Each skill is battle-tested in real projects before being open-sourced. Most skills ship with an auto-update mechanism (syncing with GitHub on load, silently degrading on network failure), so no manual maintenance is needed.

Want to contribute a skill? PRs welcome. Issues and suggestions? Open an Issue.

---

<div align="center">

[MIT License](./LICENSE) · Free to use / modify / redistribute

Made by [@sljdxde](https://github.com/sljdxde)

</div>
