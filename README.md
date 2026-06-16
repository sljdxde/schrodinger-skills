<div align="center">

**中文** · [English](./README.en.md)

# Schrodinger Skills

#### 实用的 AI Skills 合集，开箱即用

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-1-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![Cursor](https://img.shields.io/badge/Cursor-Skill-8B5CF6?style=flat-square)

</div>

每个 Skill 都是 Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex、OpenCode、Cursor 都能装。

安装方式很简单——对 Agent 说一句话就行，不用操心路径和配置。

---

## 目录

| 名字 | 一句话 | 链接 |
|---|---|---|
| [Skill Scanner](./skill-scanner) | 自动发现和扫描多 Agent 生态的 skills，支持 plugins/cache 递归检测 | [SKILL.md](./skill-scanner/SKILL.md) |

---

## 安装方式

在 Claude Code、Codex、Cursor 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想装的那个。Agent 会自己 clone 到对应目录，不用你操心路径。

---

## Skills

### [Skill Scanner](./skill-scanner)

自动发现和扫描 AI Agent 技能的通用模块。支持 Claude Code、Codex、Cursor、OpenCode 等 12 种 Agent 生态，能递归发现 `plugins/cache`、`plugins/marketplaces` 等嵌套目录下的 skills。

**核心能力：**
- 自动递归发现 Agent 目录下的 skills
- 智能跳过 sessions、backups 等无关目录
- 解析 SKILL.md 元数据（name、description、source 等）
- 支持 7 种诊断：风险、冲突、重复、版本漂移、僵尸、描述质量、结构警告

**使用方式：**
```bash
npm install -g agent-skill-doctor
agent-skill-doctor scan
```

---

## 关于

Schrodinger Skills 是一个持续更新的 AI Skills 合集。每个 skill 都经过实际使用验证，确认好用才开源出来。

如果你有好的 skill 想贡献，欢迎提 PR。有问题或建议，欢迎在 Issues 里说。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@sljdxde](https://github.com/sljdxde)

</div>
