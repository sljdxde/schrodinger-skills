<div align="center">

**中文** · [English](./README.en.md)

# Schrodinger Skills

#### 实用的 AI Skills 合集，开箱即用

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-2-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![Cursor](https://img.shields.io/badge/Cursor-Skill-8B5CF6?style=flat-square)

</div>

每个 Skill 都是 Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex、OpenCode、Cursor 都能装。

安装方式很简单——对 Agent 说一句话就行，不用操心路径和配置。

本仓库的 skill 都内置使用前自检更新机制：运行时会先检查 GitHub 上对应 skill 目录是否更新，必要时备份并同步本地 skill；带外部工具依赖的 skill 还会检查对应工具包版本。

自检更新需要本机可运行 `python`；`Skills Doctor` 的 npm 包自动更新还需要本机可运行 `npm`。

---

## 目录

| 名字 | 一句话 | 链接 |
|---|---|---|
| [House Buying](./house-buying) | 中国住宅购房尽调与决策分析，覆盖成交、学区溢价、升学、生源、小区人口和价格预测 | [SKILL.md](./house-buying/SKILL.md) |
| [Skills Doctor](./skills-doctor) | 诊断和治理本地 AI Agent Skills，检测风险、冲突、重复、僵尸等问题 | [SKILL.md](./skills-doctor/SKILL.md) |

---

## 安装方式

在 Claude Code、Codex、Cursor 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想装的那个。Agent 会自己 clone 到对应目录，不用你操心路径。

---

## Skills

### [House Buying](./house-buying)

中国住宅购房尽调和决策分析工具。适合评估具体楼盘、学区房、片区对比和买入时机，要求联网核验成交、挂牌、学校、政策、升学、生源、小区人口、学区溢价与城市基本面数据。

**核心能力：**
- 成交/挂牌/库存/议价空间多源核验
- 学区房与周边非学区/弱学区房价格对比，量化教育溢价
- 学校升学、招生政策、学位预警和生源结构分析
- 小区人口与居住画像，区分“买学位入口”和“可长期自住社区”
- 基准/乐观/悲观三情景价格预测
- 明确给出买入、谨慎可买、观望或不建议买入

**使用方式：**

对 Agent 说：
```
请使用 house-buying 分析杭州耀江文鼎苑是否值得买，自住+学区，预算400万以内
```

Agent 会先核验公开数据，再输出证据台账、风险评估、横向对比和购买建议。

**自动更新：**
- 使用前运行 `python scripts/update_self.py --apply`
- 自动检查并同步 GitHub 上的 `house-buying` skill 目录

### [Skills Doctor](./skills-doctor)

诊断和治理本地 AI Agent Skills 的工具。支持 Claude Code、Codex、Cursor、OpenCode 等多种生态，检测风险、冲突、重复、僵尸等问题并生成修复建议。

**核心能力：**
- 7 种诊断：风险、冲突、重复、版本漂移、僵尸、描述质量、结构警告
- 生成修复提示（fix 命令）
- 支持 Markdown/HTML/JSON 报告导出
- CI 集成（--ci --fail-on）

**使用方式：**

对 Agent 说：
```
请使用 agent-skill-doctor 诊断我的本地 Agent Skills
```

Agent 会自动运行诊断、生成报告、输出修复计划。也可以指定具体需求：
```
帮我检查有没有重复的 skills
检测一下有没有僵尸 skill
```

**自动更新：**
- 使用前运行 `python scripts/update_self.py --apply`
- 自动检查并同步 GitHub 上的 `skills-doctor` skill 目录
- 自动检查并更新 `agent-skill-doctor` npm 包到最新版

---

## 关于

Schrodinger Skills 是一个持续更新的 AI Skills 合集。每个 skill 都经过实际使用验证，确认好用才开源出来。

如果你有好的 skill 想贡献，欢迎提 PR。有问题或建议，欢迎在 Issues 里说。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@sljdxde](https://github.com/sljdxde)

</div>
