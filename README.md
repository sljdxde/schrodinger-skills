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
| 🛡️ [**no-bash-windows**](#-no-bash-windows) | Windows 原生环境禁止 bash 命令，自动使用 PowerShell 兼容方案 | [SKILL.md](./no-bash-windows/SKILL.md) |

---

## 安装方式

在 Claude Code、Codex、Cursor 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想装的那个。Agent 会自己 clone 到对应目录，不用你操心路径。

---

## Skills

<table>
<tr><td>

### no-bash-windows

> *"在 Windows 上跑 agent，一半命令报错——因为全是 bash 语法。"*

当你在 Windows 原生环境下使用 AI agent（Claude Code、Codex、Cursor 等），agent 经常生成 `grep`、`rm -rf`、`export`、`source` 等 bash-only 命令，在 PowerShell 中无法执行。no-bash-windows 让 agent 默认使用 PowerShell 兼容语法，避免这类问题。

**它能做什么**

- 让 agent 在 Windows 环境下自动使用 PowerShell 命令
- 提供 bash -> PowerShell 完整命令映射表
- 内置环境检查脚本（preflight）
- 覆盖 Node.js、Python、Java、Go、Rust 等主流生态
- 失败诊断：自动识别 shell 兼容问题并转换

**适合**

- Windows 原生用户（不装 WSL）
- 经常遇到 agent 生成 bash 命令报错
- 希望 agent 输出可直接在 PowerShell 中执行

**不适合**

- Linux / macOS 用户
- 已有 WSL 且习惯使用 WSL 的用户

**怎么触发**

```
帮我搜索 src 目录下的关键字
删除 dist 目录
设置环境变量并运行 build
激活 Python 虚拟环境
```

**跨平台 Agent**：Claude Code · Codex · OpenCode · Cursor · VS Code Copilot · Gemini CLI

→ [SKILL.md](./no-bash-windows/SKILL.md) · [命令映射](./no-bash-windows/references/command-map.md) · [失败诊断](./no-bash-windows/references/failure-recovery.md) · [测试结果](./no-bash-windows/test-results.md)

</td></tr>
</table>

---

## 关于

Schrodinger Skills 是一个持续更新的 AI Skills 合集。每个 skill 都经过实际使用验证，确认好用才开源出来。

如果你有好的 skill 想贡献，欢迎提 PR。有问题或建议，欢迎在 Issues 里说。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@sljdxde](https://github.com/sljdxde)

</div>
