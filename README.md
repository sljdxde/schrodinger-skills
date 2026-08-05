<div align="center">

**中文** · [English](./README.en.md)

# Schrodinger Skills

#### 实用的 AI Skills 合集，开箱即用

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-6-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![OpenCode](https://img.shields.io/badge/OpenCode-Skill-3B82F6?style=flat-square)
![Cursor](https://img.shields.io/badge/Cursor-Skill-8B5CF6?style=flat-square)

</div>

每个 Skill 都是 Agent 能直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 开放标准。Claude Code、Codex、OpenCode、Cursor 都能装。

安装方式很简单——对 Agent 说一句话就行，不用操心路径和配置。

本仓库中提供自检更新机制的 skill 会在运行时检查 GitHub 上对应目录是否更新，必要时备份并同步本地 skill；带外部工具依赖的 skill 还会检查对应工具包版本。组合包会额外提供明确的安装入口。

自检更新需要本机可运行 `python`；`Skills-Doctor` 的 npm 包自动更新还需要本机可运行 `npm`。

---

## 目录

| 名字 | 一句话 | 链接 |
|---|---|---|
| [House-Buying](./house-buying) | 中国住宅购房尽调与决策分析，覆盖成交、学区溢价、升学、生源、小区人口和价格预测 | [SKILL.md](./house-buying/SKILL.md) |
| [Skills-Doctor](./skills-doctor) | 诊断和治理本地 AI Agent Skills，检测风险、冲突、重复、僵尸等问题 | [SKILL.md](./skills-doctor/SKILL.md) |
| [Memory-Forge](./memory-forge) | 把任意学习材料锻造成好懂好记的知识卡/故事/脑图/自测，并给出艾宾浩斯复习计划 | [SKILL.md](./memory-forge/SKILL.md) |
| [MTD-Download](./mtd-download) | 基于 curl 的多线程/分块并行下载大文件，自动探测断点续传支持，带进度与速度显示 | [SKILL.md](./mtd-download/SKILL.md) |
| [Personal-Knowledge-Base](./personal-knowledge-base) | Codex + Obsidian + `ob` CLI 的本地个人知识库组合包，包含 `ob-llm-wiki` 与 `ob` 两个 skill | [README.md](./personal-knowledge-base/README.md) |

---

## 安装方式

在 Claude Code、Codex、Cursor 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想装的那个。Agent 会自己 clone 到对应目录，不用你操心路径。

个人知识库是组合包，安装时要把整个目录交给 Agent，并明确要求同时安装两个组件：

```
请安装 schrodinger-skills 的 personal-knowledge-base 整套能力，包含 ob-llm-wiki 和 ob；不要只安装其中一个目录。
```

---

## Skills

### [House-Buying](./house-buying)

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

### [Skills-Doctor](./skills-doctor)

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

### [Memory-Forge](./memory-forge)

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
- 养成体系：内置等级 / 经验 / 勋章墙 / 连续学习 streak（进度存浏览器本地），可按材料主题加定制勋章，提升坚持与代入感
- 视觉主题：`--theme claude`（默认，暖象牙底 + 陶土色点缀 + 衬线大标题的 Claude Design 风）/ `--theme editorial`（暖米纸 + 衬线大标题的杂志风）/ `--theme swiss`（近白底 + 单一克莱因蓝 + 全程无衬线 + 直角的瑞士国际主义风）；三套均离线、零 emoji、可随时切换

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

### [Personal-Knowledge-Base](./personal-knowledge-base)

面向 **Codex + Obsidian + 本地 `ob` CLI** 的个人知识库组合包。Codex 负责理解问题、选择最小读取范围、提炼可复用结论和维护索引；`ob` 负责把所有读写限制在当前 Obsidian vault；Obsidian 负责人工浏览、链接导航和最终确认。

**包含两个需要一起安装的 skill：**
- `ob-llm-wiki`：知识库启动、检索、摄取、结构化、审计和对话归档
- `ob`：vault 检查、定位、列目录、读取、搜索、写入、移动和删除

**能做到：**
- 从个人/工作范围、标签和目录中检索已有知识，只读取必要笔记
- 把对话结论、资料和研究结果沉淀到 `raw/`、`concepts/`、`entities/`、`comparisons/`、`queries/`
- 自动维护 `index.md`、`log.md`、wikilink 和 `#个人` / `#工作` 范围标签
- 审计缺目录、断链、孤立笔记、索引漂移和标签冲突
- 在多个 vault 存在时先确认，不猜错目标库；对敏感内容执行最小读取和最小输出

**安装方式：**

对 Agent 说：

```
请把这个目录作为一个组合包安装：
https://github.com/sljdxde/schrodinger-skills/tree/main/personal-knowledge-base
需要同时安装其中的 ob-llm-wiki 和 ob 两个 skill。
```

更完整的能力说明、目录结构和使用示例见 [personal-knowledge-base/README.md](./personal-knowledge-base/README.md)。

### [MTD-Download](./mtd-download)

基于系统 `curl` 的多线程下载工具。把一个大文件按字节区间切成多段并行下载，服务器支持 `Range` 时显著提速；不支持、文件过小或拿不到大小时自动退回单线程流式下载。纯标准库 + 系统 `curl`，不需要 `pip install` 任何依赖。

**核心能力：**
- 自动探测文件大小与服务器 `Range` 支持，能分段且文件 > 4MB 才开多线程
- 多线程用 `os.pwrite` 按绝对偏移写，区间互不越界，服务器无视 Range 也只保留本段
- 单线程回退：不支持 Range / 文件 ≤ 4MB / 拿不到大小都能下
- 实时进度条（进度 / 已下 / 速度 / ETA），输出走 stderr 不污染 stdout
- 分块失败自动重试 3 次；整体失败清理不完整的输出文件，不留损坏文件
- 退出码成功 `0`、失败 `1`，方便脚本判断

**使用方式：**

对 Agent 说：
```
用 mtd-download 下载这个大文件：https://example.com/big-file.iso
```

或直接运行：
```bash
# 默认 16 线程，自动从 URL 推断文件名
python scripts/mtd.py <URL>

# 指定线程数与输出名
python scripts/mtd.py <URL> -t 32 -o myfile.iso
```

Agent 会先运行探测，再按策略完成下载并报告结果。

**自动更新：**
- 使用前运行 `python scripts/update_self.py --apply`
- 自动检查并同步 GitHub 上的 `mtd-download` skill 目录

---

## 关于

Schrodinger Skills 是一个持续更新的 AI Skills 合集。每个 skill 都经过实际使用验证，确认好用才开源出来。

如果你有好的 skill 想贡献，欢迎提 PR。有问题或建议，欢迎在 Issues 里说。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@sljdxde](https://github.com/sljdxde)

</div>
