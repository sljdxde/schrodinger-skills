<div align="center">

[中文](./README.md) · **English**

# Schrodinger Skills

#### Practical AI Skills, ready to use

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-2-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![Cursor](https://img.shields.io/badge/Cursor-Skill-8B5CF6?style=flat-square)

</div>

Each Skill is a structured instruction set that Agents can load directly, following the [Agent Skills](https://agentskills.io) open standard. Works with Claude Code, Codex, OpenCode, and Cursor.

Installation is simple — just one sentence to your Agent. No path or configuration hassle.

*Note for English readers: This project originated in the Chinese AI community. Contributions and translations are welcome.*

Every skill in this repository includes a pre-use self-update check. Before running, the skill can compare its local folder with the latest GitHub copy, back up and sync itself when needed, and update backing tool packages when the skill depends on one.

The self-update helper requires `python`; npm-backed skills such as Skills Doctor also require `npm` for package updates.

---

## Table of Contents

| Name | One-liner | Link |
|---|---|---|
| [House Buying](./house-buying) | Due diligence and decision support for Chinese home purchases, including transactions, school premiums, student sources, community demographics, and forecasts | [SKILL.md](./house-buying/SKILL.md) |
| [Skills Doctor](./skills-doctor) | Diagnose and govern local AI Agent Skills — detect risks, conflicts, duplicates, zombies | [SKILL.md](./skills-doctor/SKILL.md) |

---

## Install

In any Agent that supports Skills (Claude Code, Codex, Cursor, etc.), just say:

```
Install this skill: https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

Replace `<skill-name>` with the one you want. The Agent will clone it to the right directory automatically.

---

## Skills

### [House Buying](./house-buying)

Due diligence and decision support for Chinese residential property purchases. It is designed for target communities, school-district homes, area comparisons, and buy/watch decisions, with explicit evidence tracking for transaction prices, listings, school-premium comparisons, admissions policy, student sources, community demographics, and city fundamentals.

**Key Features:**
- Cross-check transaction prices, listing prices, inventory, and negotiation room
- Compare school-district homes with nearby non-school-district or weaker-school alternatives to quantify the education premium
- Analyze school outcomes, admission rules, seat warnings, and student-source quality
- Build a community demographic profile instead of relying only on price
- Produce base/optimistic/pessimistic housing-price forecast scenarios
- Give a clear buy / cautious buy / watch / do-not-buy recommendation

**Usage:**

Tell your Agent:
```
Use house-buying to analyze whether Hangzhou Yaojiang Wendingyuan is worth buying for self-use plus school access under a 4M RMB budget
```

The Agent will verify public data first, then produce an evidence-backed report with risks, comparisons, and an actionable recommendation.

**Auto-update:**
- Run `python scripts/update_self.py --apply` before use
- Checks and syncs the latest `house-buying` skill folder from GitHub

### [Skills Doctor](./skills-doctor)

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

---

## About

Schrodinger Skills is an actively maintained collection of AI Skills. Each skill is battle-tested in real projects before being open-sourced.

Want to contribute a skill? PRs welcome. Issues and suggestions? Open an Issue.

---

<div align="center">

[MIT License](./LICENSE) · Free to use / modify / redistribute

Made by [@sljdxde](https://github.com/sljdxde)

</div>
