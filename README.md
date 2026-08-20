<div align="center">

**中文** · [English](./README.en.md)

# Schrodinger Skills

#### 实用的 AI Skills 合集，开箱即用

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-8-10B981?style=for-the-badge)](#-skills)
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
| [House-Buying](./house-buying) | 全国 47 城住宅购房尽调与决策分析：贝壳官方 CLI 真实数据、五级数据源体系、引用溯源防伪、价格动量、学区溢价、生源代际传导与价格预测 | [SKILL.md](./house-buying/SKILL.md) |
| [Layout-Analysis](./layout-analysis) | 户型分析：从网页链接 / 户型图 / 手填数据出发，评估空间利用、动线、采光通风、私密性与改造潜力，给出评分与适用人群 | [SKILL.md](./layout-analysis/SKILL.md) |
| [Skills-Doctor](./skills-doctor) | 诊断和治理本地 AI Agent Skills，检测风险、冲突、重复、僵尸等问题并生成修复建议 | [SKILL.md](./skills-doctor/SKILL.md) |
| [Memory-Forge](./memory-forge) | 把任意学习材料锻造成好懂好记的知识卡/故事/脑图/自测，并给出 SM-2 复习计划与成长体系 | [SKILL.md](./memory-forge/SKILL.md) |
| [MTD-Download](./mtd-download) | 基于 curl 的多线程/分块并行下载大文件，自动探测断点续传、抗 WAF/限流、带进度与速度显示 | [SKILL.md](./mtd-download/SKILL.md) |
| [Skill-Architect](./skill-architect) | 通过第一性原理 10 维度决策树访谈，把模糊需求或个人经验设计成可安装的 AI Skill，编译成包并做质量评估 | [SKILL.md](./skill-architect/SKILL.md) |
| [Milestone-Gate](./milestone-gate) | 复杂任务的里程碑门控：开局拆里程碑与验收标准，每阶段交付物让你确认，不达标回退重做，避免「只看到结果、最后全重来」 | [SKILL.md](./milestone-gate/SKILL.md) |
| [Personal-Knowledge-Base](./personal-knowledge-base) | Codex + Obsidian + `ob` CLI 的本地个人知识库组合包，包含 `ob-llm-wiki` 与 `ob` 两个 skill | [README.md](./personal-knowledge-base/README.md) |

---

## 安装方式

在 Claude Code、Codex、Cursor 等支持 Skill 的 Agent 里，直接说：

```
帮我安装这个 skill：https://github.com/sljdxde/schrodinger-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想装的那个。Agent 会自己 clone 到对应目录，不用你操心路径。

`Personal-Knowledge-Base` 是组合包，安装时要把整个目录交给 Agent，并明确要求同时安装两个组件：

```
请安装 schrodinger-skills 的 personal-knowledge-base 整套能力，包含 ob-llm-wiki 和 ob；不要只安装其中一个目录。
```

---

## Skills

### [House-Buying](./house-buying)

中国住宅（重点学区房）购房尽调与决策分析工具。适合评估具体楼盘、学区房、片区对比和买入时机，强制联网核验成交、挂牌、学校、政策、升学、生源、小区人口、学区溢价与城市基本面数据，最终产出单份自包含 HTML 报告。

**核心能力：**

- **全国 47 城预置数据源**：省会 + 首府 + 直辖市 + 计划单列市 + 强地级市（含深圳/苏州/宁波/青岛/洛阳等），每城住建、网签、不动产登记、统计、教育等官方源 URL 均经联网核验，新增城市零成本接入
- **贝壳官方 CLI 集成**：加载时自动探测本机是否安装并鉴权 Beike CLI（`beike-check`），优先走官方真实通道拉取挂牌 / 成交 / 均价走势 / 小区档案（全部带真实 ke.com 详情 URL）；未安装可一键跳过并退回联网检索兜底，绝不编造
- **五级数据源体系（T0–T4）+ T1.5**：T0 贝壳系（贝壳/链家）+ 我爱我家为强制双源交叉；T1 官方源（住建/网签/不动产/统计/教育）在冲突裁决中权重最高；T1.5 城市本地高频源（杭房数研/小鸡选房类）接近网签口径；T2 政务 App（浙里办/随申办/京通等）；T3 诸葛找房/安居客/房天下/58 同城仅作交叉验证；T4 舆情为线索级
- **引用五要素防伪（强制）**：每一项数据强制携带 来源 + 真实 URL + 发布时间/访问时间 + 数据口径 + 一致性程度；多源冲突按「时间最新 > 口径最权威 > 最接近一手（官方网签/政务网）」裁决，差异 ≤5% 视为一致、>5% 并列披露、硬冲突标「存疑」
- **单一维度展开**：先把「房价」维度做透（挂牌/成交月度时间轴 + 环比/同比/N 月涨跌幅 + 带看/房源量），再按诉求逐层扩展成交、供需比、土地出让、学区政策、人口流动、信贷环境
- **多平台统一检索入口**：`python scripts/data_sources.py search` 一次跑「贝壳 CLI 优先 + 我爱我家 + 可选 T3 交叉」，返回每平台状态与近 10 条真实成交；CLI 无成交时支持用户手动录入（`gen_styled_report.py --chengjiao`）
- **月度价格时间轴**：内嵌 SVG 走势图（挂牌 vs 成交双序列），含峰值/谷值/当前值、波动幅度与样本量（样本不足不编造）
- **学区房专项**：与周边非学区/弱学区房价格对比量化教育溢价；学校梯队评级（第一/二/三/四梯队 + 评级依据）；**生源代际传导分析**（初中升学率滞后约 9–15 年，重建历史生源对比当前生源预测未来）；落户年限/学位占用买前自查清单与合同模板
- **2026 政策基线快照**：多校划片/教师轮岗/户籍脱钩/学位锁定/预警逐城结构化，作为默认高权重情景输入
- **三情景价格预测**：基准/乐观/悲观，分 6–12 个月、1–3 年、3–10 年给出区间与置信度
- **脚本生成的自包含 HTML 报告**：视觉样式由用户选定，内置 warm / editorial / cinematic / glass / data / olive 六套主题（内容一致、仅 CSS 不同），SVG 图/表格/引用链接全部内嵌，不依赖外部资源
- 明确给出 买入 / 谨慎可买 / 观望 / 不建议买入 结论（带置信度）

**使用方式：**

对 Agent 说：

```
请使用 house-buying 分析杭州耀江文鼎苑是否值得买，自住+学区，预算400万以内
```

或指定其他城市：

```
请使用 house-buying 分析上海张江汤臣豪园是否值得买，自住+学区，预算800万以内，城市：上海
```

Agent 会先探测贝壳 CLI 状态 → 采集需求 → 联网核验公开数据 → 生成带月度价格时间轴的证据台账、风险评估、横向对比和购买建议，并在交付报告前让你选择视觉主题。

---

### [Layout-Analysis](./layout-analysis)

面向通用买家的户型分析工具。无论从网页链接、户型图图片还是手动字段拿到房源，都能输出「优缺点 + 改造建议 + 采光通风朝向 + 综合评分」的完整报告。

**核心能力：**

- **三种输入入口**：网页链接（抓取贝壳等页面）、户型图图片（读图解析）、手动字段（面积/户型/朝向/尺寸）；缺关键信息先追问，不凭空分析
- **户型解析**：提取房间清单、各房间面积与尺寸、朝向、开窗、承重墙线索，落成结构化数据
- **五维度分析**：空间利用 / 动线 / 采光通风 / 私密性 / 改造潜力，每项给可核验依据
- **综合评分**：各维度 0–5 分加权出总分，给出优缺点清单与适用人群（自住/改善/投资）
- **改造建议**：标注承重/剪力墙风险、公共区域限制，不确定处提示需现场确认
- **多户型横向对比**（可选）
- **边界清晰**：不含房价评估与投资建议、法律/产权/学区判断、装修报价/施工/风水

**使用方式：**

对 Agent 说：

```
用 layout-analysis 分析这个户型：<网页链接 / 户型图图片 / 户型数据>
```

或直接粘贴面积、户型、朝向、尺寸等字段。Agent 会先追问缺失信息，再输出「概览 → 逐维度分析 → 改造建议 → 评分卡 → 总评与适用人群」的完整报告。

---

### [Skills-Doctor](./skills-doctor)

诊断和治理本地 AI Agent Skills 的工具。支持 Claude Code、Codex、Cursor、OpenCode 等多种生态，检测风险、冲突、重复、僵尸等问题并生成修复建议。

**核心能力：**

- 7 种诊断：风险（rm -rf / curl / .env 访问 / child_process 等）、冲突、重复、版本漂移、僵尸、描述质量、结构警告
- 生成修复提示（`fix` 命令，可按类型/严重程度筛选）
- 支持 Markdown / HTML / JSON 报告导出
- CI 集成（`--ci --fail-on`）
- 配套 npm 包 `agent-skill-doctor`，自动检查并更新到最新版

**使用方式：**

对 Agent 说：

```
请使用 agent-skill-doctor 诊断我的本地 Agent Skills
```

Agent 会自动运行诊断、生成报告、输出修复计划。也可以直接跑命令：

```bash
# 完整诊断（中文）
agent-skill-doctor diagnose --lang zh

# 定向查询
agent-skill-doctor risks --json
agent-skill-doctor conflicts --json
agent-skill-doctor duplicates --json
agent-skill-doctor zombies --json

# 生成报告
agent-skill-doctor report --format md --lang zh
agent-skill-doctor report --format html --lang en --output ./reports/report.html

# 生成修复提示
agent-skill-doctor fix --lang zh
agent-skill-doctor fix --type risk --severity high --lang zh

# CI 集成：高严重程度即失败
agent-skill-doctor diagnose --ci --fail-on high
```

默认扫描 `~/.agent/skills`、`~/.agents/skills`、`~/.codex/skills`、`~/.claude/skills`、`~/.cursor/skills`、`~/.opencode/skills` 等目录。

---

### [Memory-Forge](./memory-forge)

把任意学习材料（粘贴文字、`.txt` / `.md` / `.docx` / `.pdf`）重新锻造成好懂好记的东西。用记忆科学把知识点拆成一张张小卡片，配故事 / 类比 / 互补图示、出测验、排复习计划——因为人脑对纯文字记忆很烂，对画面和故事好得多。

**核心能力：**

- 一概念一卡：每张卡只装一个知识点，避免挤爆工作记忆
- 抽象概念必配故事 / 类比；视觉必须和文字互补（不是装饰图）
- 翻转知识卡：正面问题 → 翻面大白话 + 要点 + 助记符
- 知识脑图：把全篇关系画成可点击高亮的树
- 自测区：先答再揭晓解析（测试效应）
- SM-2 / 艾宾浩斯复习计划：0–5 自评即时算下次间隔
- 联网深潜：遇到陌生术语主动搜权威解释 + 配图，标来源日期
- 成长体系：内置等级 / 经验 / 勋章墙 / 连续学习 streak（进度存浏览器本地），可按材料主题加定制勋章，提升坚持与代入感
- 双轨交付：对话内即时讲解 + 导出离线自包含 HTML / Markdown 学习包
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

---

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

---

### [MTD-Download](./mtd-download)

基于系统 `curl` 的多线程下载工具。把一个大文件按字节区间切成固定小分块并行下载，服务器支持 `Range` 时显著提速；不支持、文件过小、命中 WAF/限流或拿不到大小时自动退回单线程流式下载。纯标准库 + 系统 `curl`，不需要 `pip install` 任何依赖。

**核心能力：**

- 探测优先：先用 `curl -sIL` 拿 `content-length` 与 `accept-ranges`，能分段且文件 > 4MB 才开多线程
- 固定小分块 + 高并发 + 块级容错：默认代理环境 2MB / 否则 5MB（`--chunk` 可调），每块独立下载、独立重试（默认 5 次），单块失败不影响其它块，从源头规避「单连接限速 + 大块 Range 挂死」
- 每线程独立重定向：规避 CDN 鉴权过期，避免把 HTML 错误页当文件数据写入
- Range 内容非零校验：实测分块 >95% 为零则判定该 CDN 的 Range 实现有缺陷，自动退化单线程
- 抗 WAF / 限流自动回退单线程：命中 418/429/401/403/407/503 立即中止并发并降级，避免放大封禁
- 断点续传（`--resume`）：多线程模式记录已完成块，中断后只补剩余；还会扫描已存在文件里的大零空洞并视为未完成块自愈补下
- 下载后完整性校验：合并后扫描大段连续零字节（零空洞）+ 格式校验（PDF 头尾 / `file` 探测 HTML 错误页），绝不交付满尺寸但内部损坏的文件
- 代理绕过 / 镜像源：`--noproxy` 直连；`--mirror ghproxy` 把 URL 包成 `https://ghproxy.net/<URL>` 直连；GitHub `blob` 链接自动转 `raw.githubusercontent.com` 真直链
- 进度走 stderr（不污染 stdout）；退出码 0/1；可选 `--sha256` 官方校验；macOS 下载后自动清除 Gatekeeper 隔离标记

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

# 调整分块大小（小分块抗 CDN 限速挂死）
python scripts/mtd.py <URL> --chunk 2

# 断点续传（中断后只补未完成块并自愈零空洞）
python scripts/mtd.py <URL> --resume

# 绕过透明代理直连（海外 CDN 大文件被代理截断时）
python scripts/mtd.py <URL> --noproxy

# 走 ghproxy 镜像直连（GitHub 大文件）
python scripts/mtd.py "https://github.com/owner/repo/blob/main/big.pdf" --mirror ghproxy

# 下载后比对官方 SHA256（不一致直接报错，保留文件供排查）
python scripts/mtd.py <URL> --sha256 <官方十六进制值>
```

Agent 会先运行探测，再按策略完成下载并报告结果。

---

### [Skill-Architect](./skill-architect)

把「模糊需求」或「个人/领域经验」变成**可直接安装的 AI Skill** 的 Meta Skill。核心思路：用户往往知道要解决什么问题，却不知道 Skill 该含什么能力——所以 AI 先当产品经理 + 领域专家做一次**第一性原理访谈**，再产出蓝图、编译成包、跑质量评估。

**核心能力：**

- 第一性原理拆维：把一个 Skill 必须定义清楚的 10 个维度（身份/受众/目标/输入/流程/分析框架/输出规格/边界/数据/交互质量）作为访谈骨架，绝不漏面
- 决策树 + 问题簇：每面一次抛出 3–6 题成簇提问，靠分支下钻，不靠来回拉锯；已能推断的列为假设，不堆砌无关问题
- 条件分支：分析/决策型 Skill 必深挖「分析框架」（维度/打分/证据严谨度/可视化）；有产出物的必问「输出规格」（md / html / json / 对话 / 多文件，并按格式再下钻交互与命名）
- 双路径访谈：Path A（Need→Skill，需求驱动）+ Path B（Experience→Skill，经验沉淀），经验统一映射到同一张维度表
- 领域补全库：内置 学习 / 旅行 / 投资 / 创作 能力清单 + 通用模板，帮用户发现「不知道要什么」
- 访谈即产出：结论落成 `blueprint.json` 的 `input_spec`/`output_spec`/`analysis`/`interaction_model` 等字段，由 `compile_skill.py` 直接渲染进生成包的「输入 / 分析框架 / 输出规格 / 交互方式」章节
- `compile_skill.py` 全量脚手架：产出与 house-buying 等完全同构的包（SKILL.md + agents/openai.yaml + update_self.py + references/ + evaluations/），立即可装
- 4 维评分评估：专业度 / 完整度 / 任务成功率 / 错误率，产出 `evaluations/self-eval.md`

**使用方式：**

对 Agent 说：

```
请用 skill-architect 帮我做一个买房助手
```

或经验沉淀：

```
我在房产行业干了 20 年，想把经验变成 AI 顾问
```

Agent 会先访谈、产出蓝图，再编译成包并评估。也可直接跑脚本：

```bash
python scripts/compile_skill.py --blueprint examples/sample-blueprint.json --out ./skills
```

---

### [Milestone-Gate](./milestone-gate)

复杂任务的里程碑门控流程。开局把目标拆成带「交付物 + 验收标准」的有序里程碑，每完成一段先给你看中间交付物，你确认达标才往下走；不达标只退回当前里程碑重做（保留已达标的前序），把「最后一把赌结果」变成「每段都可纠偏」，从而省下 token 与时间。

**核心能力：**

- 里程碑分解：将复杂任务拆成可核验的交付物序列，开局即让用户看到全貌与验收标准
- 验收标准：每个里程碑都有明确达标判据，模糊的「差不多」不算达标
- 阶段交付与确认：每个里程碑完成后通过预览/卡片呈现中间交付物，并请求用户确认
- 纠偏重做：不达标退回当前里程碑重做，已达标的前序保留，绝不推翻重来
- 进度可视化：用任务清单持续展示进度，随时掌握状态
- 危险前置：在不可逆/高成本/外部副作用步骤前主动暂停，与既有安全规则协同

**使用方式：**

对 Agent 说：

```
用 milestone-gate 帮我做 X，分步确认
```

或直接描述复杂任务并说「先规划」「分步做」，Agent 会自动施加里程碑门控；也可显式调用。

---

## 关于

Schrodinger Skills 是一个持续更新的 AI Skills 合集。每个 skill 都经过实际使用验证，确认好用才开源出来。多数 skill 内置自动更新机制（加载时自动与 GitHub 同步最新版本，网络失败静默降级），无需手动维护。

如果你有好的 skill 想贡献，欢迎提 PR。有问题或建议，欢迎在 Issues 里说。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@sljdxde](https://github.com/sljdxde)

</div>
