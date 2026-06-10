<div align="center">

[中文](./README.md) · **English**

# Schrodinger Skills

#### Practical AI Skills, ready to use

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-1-10B981?style=for-the-badge)](#-skills)
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
| 🛡️ [**no-bash-windows**](#-no-bash-windows) | Forbid bash commands on native Windows, auto-use PowerShell-compatible alternatives | [SKILL.md](./no-bash-windows/SKILL.md) |

---

## Install

In any Agent that supports Skills (Claude Code, Codex, Cursor, etc.), just say:

```
Install this skill: https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

Replace `<skill-name>` with the one you want. The Agent will clone it to the right directory automatically.

---

## Skills

<table>
<tr><td>

### no-bash-windows

> *"Running agent on Windows, half the commands fail — because they're all bash syntax."*

When using AI agents (Claude Code, Codex, Cursor, etc.) on native Windows, agents often generate bash-only commands like `grep`, `rm -rf`, `export`, `source` that fail in PowerShell. no-bash-windows makes agents default to PowerShell-compatible syntax.

**What it does**

- Makes agents automatically use PowerShell commands on Windows
- Provides complete bash -> PowerShell command mapping
- Includes environment check script (preflight)
- Covers Node.js, Python, Java, Go, Rust ecosystems
- Failure diagnosis: auto-detects shell compatibility issues and converts

**Good for**

- Native Windows users (no WSL)
- Users who frequently hit bash command errors from agents
- Users who want agent output to run directly in PowerShell

**Not for**

- Linux / macOS users
- Users who already use WSL comfortably

**How to trigger**

```
Search for keywords in the src directory
Delete the dist directory
Set environment variables and run build
Activate Python virtual environment
```

**Cross-platform Agents**: Claude Code · Codex · OpenCode · Cursor · VS Code Copilot · Gemini CLI

→ [SKILL.md](./no-bash-windows/SKILL.md) · [Command Map](./no-bash-windows/references/command-map.md) · [Failure Recovery](./no-bash-windows/references/failure-recovery.md) · [Test Results](./no-bash-windows/test-results.md)

</td></tr>
</table>

---

## About

Schrodinger Skills is an actively maintained collection of AI Skills. Each skill is battle-tested in real projects before being open-sourced.

Want to contribute a skill? PRs welcome. Issues and suggestions? Open an Issue.

---

<div align="center">

[MIT License](./LICENSE) · Free to use / modify / redistribute

Made by [@sljdxde](https://github.com/sljdxde)

</div>
