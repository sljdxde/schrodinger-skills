<div align="center">

**中文** · [English](./README.en.md)

# Schrodinger Skills

#### 实用的 AI Skills 合集，开箱即用

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-3-10B981?style=for-the-badge)](#-skills)
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
| [Memory Forge](./memory-forge) | 把任意学习材料锻造成好懂好记的知识卡/故事/脑图/自测，并给出艾宾浩斯复习计划 | [SKILL.md](./memory-forge/SKILL.md) |

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

### [Memory Forge](./memory-forge)

把任意学习材料（粘贴文字、`.txt` / `.md` / `.docx` / `.pdf`）重新锻造成好懂好记的东西。用记忆科学把知识点拆成一张张小卡片，配故事 / 类比 / 互补图示、出测验、排复习计划——因为人脑对纯文字记忆很烂，对画面和故事好得多。

**核心能力：**
- 一概念一卡：每张卡只装一个知识点，避免挤爆工作记忆
- 抽象概念必配故事 / 类比；视觉必须和文字互补（不是装饰图）
- 翻转知识卡：正面问题 → 翻面大白话 + 要点 + 助记符
- 知识脑图：把全篇关系画成可点击高亮的树
- 自测区：先答再揭晓解析（测试效应）
- 艾宾浩斯 / SM-2 复习计划：0–5 自评即时算下次间隔
- 联网深潜：遇到陌生术语主动搜权威解释 + 配图，标来源日期
- 双轨交付：对话内即时讲解 + 导出离线自包含 HTML / Markdown 学习包

**使用方式：**

对 Agent 说：
```
用 memory-forge 帮我把这份前端笔记学懂并记住，出一个能下载的包
```
或直接粘贴 / 上传材料：
```
（粘贴一段学习资料或上传 docx/pdf）帮我快速记住里面的要点
```

Agent 会先抽取概念，再逐步生成卡片、故事、脑图、自测和复习计划，最后给出对话内讲解和可下载的学习包。

**自动更新：**
- 使用前运行 `python scripts/update_self.py --apply`
- 自动检查并同步 GitHub 上的 `memory-forge` skill 目录

---

## 关于

Schrodinger Skills 是一个持续更新的 AI Skills 合集。每个 skill 都经过实际使用验证，确认好用才开源出来。

如果你有好的 skill 想贡献，欢迎提 PR。有问题或建议，欢迎在 Issues 里说。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@sljdxde](https://github.com/sljdxde)

</div>
