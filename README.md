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
| 🛡️ [**skill-governor**](#-skill-governor) | 管理已安装的 Agent Skills，解决插件冲突，生成路由注册表 | [SKILL.md](./skill-governor/SKILL.md) |

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

### skill-governor

> *"装了十几个 Agent 插件，打开全是重复功能——是时候找个裁判了。"*

当你的 Agent 装了多个插件，不同 skill 互相抢同一个能力（比如两个 PDF 工具、三个浏览器插件），skill-governor 会扫描所有已安装的 skill，通过策略文件决定谁是主用、谁是备用、谁该禁用，生成一份清晰的路由注册表和冲突报告。

**它能做什么**

- 扫描所有已安装的 Agent Skills，自动归类到对应能力组
- 通过 `skill-policy.yaml` 策略文件管理路由优先级
- 生成 `skill-registry.yaml` 路由注册表和冲突报告
- 支持 `SKILL.REF` 引用文件，避免跨目录重复安装
- 手动覆盖：强制指定某个 skill 的状态（active / shadow / disabled）

**适合**

- 装了多个 Agent 插件，需要统一管理 skill 路由
- 想搞清楚哪些 skill 在抢同一个能力
- 需要跨机器同步 skill 策略

**不适合**

- 只装了一两个 skill，没有冲突场景

**怎么触发**

```
帮我管理一下 skills
有没有重复的 skill
skill 冲突了怎么办
帮我 reconcile 一下
```

**跨平台**：Claude Code · Codex · OpenCode · Cursor

→ [SKILL.md](./skill-governor/SKILL.md) · [架构说明](./skill-governor/references/architecture.md) · [策略示例](./skill-governor/references/policy-examples.md)

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
