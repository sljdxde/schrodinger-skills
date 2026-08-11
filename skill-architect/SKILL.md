---
name: skill-architect
description: Use when the user wants to turn a vague need or personal/domain experience into a working, installable AI Agent Skill — runs a comprehensive first-principles interview (10 facets: identity, audience, goal, input, process, analysis framework, output spec, boundaries, knowledge, interaction/quality) as a decision tree with question clusters, produces a Skill Blueprint, compiles it into a schrodinger-skills package (SKILL.md + agents/openai.yaml + scripts/update_self.py + references/), and evaluates the result with a 4-dimension rubric.
---

# Skill Architect

把用户的**模糊需求**或**个人/领域经验**变成**可直接安装的 AI Agent Skill** 的 Meta Skill。它不是 Skill 生成器，而是「AI 帮用户设计能力」的协作者：先通过动态访谈补全用户自己都没意识到的能力缺口，再产出蓝图、编译成包、做质量评估。

设计理念来自 `references/` 背后的产品定义：传统方式是「用户描述能力 → AI 生成 Skill」，瓶颈是用户不知道自己缺什么；Skill Architect 反过来，由 AI 主动分析、领域补全、持续追问，最后才生成 Skill。

## 核心原则

- **先理解，后设计，再实现**：绝不拿到一句话就生成 SKILL.md。先跑访谈，把目标、受众、边界、能力、输入、输出、数据、交互全部厘清。
- **全覆盖，不是随便问问**：按第一性原理拆出 10 个必须定义清楚的维度（身份/受众/目标/输入/流程/分析框架/输出规格/边界/数据/交互质量），每个维度一次抛出一簇问题，靠决策树分支下钻，不靠来回拉锯。
- **动态追问，不是固定问卷**：每面只问「当前最缺」的簇；已能推断的列为假设请确认，不堆砌无关问题。
- **明确边界**：每个 Skill 必须同时写「包含」与「不包含」——边界不清的 Skill 比没有更糟。
- **可核验、不编造**：涉及事实、数据、判断时给依据与置信度；拿不到公开证据就写「未查到」，不补故事。
- **产出必须可落仓库**：Compiler 产出的包使用与 `house-buying` / `memory-forge` 完全相同的布局，立即可被 Claude Code / Codex / Cursor 安装，且自带自检更新。

## 使用前自检更新

每次使用本 skill 前，先运行：

```bash
python scripts/update_self.py --apply
```

该脚本会检查 GitHub 上 `skill-architect` 目录是否有更新，发现更新时先备份本地 skill，再自动同步最新文件。若脚本显示已更新，重新读取当前 `SKILL.md` 和相关 references 后再继续；若网络或环境导致更新失败，说明失败原因并继续使用当前版本。

## 何时触发

当用户说出以下意图之一时，使用此 skill：

- 「帮我做一个 XXX 助手 / 专家」（只有模糊目标，不知道 Skill 该含什么能力）
- 「我把多年 XXX 经验想变成 AI 顾问 / 专家」
- 「我想沉淀一套 XXX 流程 / 方法论成数字资产」
- 「帮我把这个领域知识做成 Skill」

先判断用户走 **Path A（Need→Skill，需求驱动）** 还是 **Path B（Experience→Skill，经验沉淀）**，再进入对应访谈流（见 `references/interview-engine.md`）。

## 工作流

1. **自检更新**：执行上面的 `scripts/update_self.py --apply`，必要时重新加载 skill。
2. **分流判断**：一句话判断用户是 Path A（有需求说不清）还是 Path B（有经验想沉淀）。两者都不像时，先用一轮追问澄清。
3. **动态访谈（10 维度决策树）**：
   - 按 `references/interview-engine.md` 的 10 维度（F0 身份 → F1 受众 → F2 目标/类型 → F3 输入 → F4 流程 → F5 分析框架⚠️条件 → F6 输出规格⚠️条件 → F7 边界 → F8 数据 → F9 交互质量）逐面抛簇提问。
   - **F5 分析框架**：仅当 Skill 是「分析/决策」型时必问——分析维度、打分方式、证据严谨度、对标/可视化。
   - **F6 输出规格**：只要 Skill 有产出物就必问——交付形态（md / html / json / 对话 / 多文件 / 下载）、结构、篇幅、语气、文件名约定；按格式再下钻（HTML 问交互、多文件问命名）。
   - Path B 的经验（案例/判断规则/踩坑）统一映射到同一张维度表，不另起炉灶。
4. **产出 Skill Blueprint**：把访谈结论落成一个结构化对象，字段见 `references/blueprint-schema.md`（name / description / capabilities / workflow / boundaries / references / evaluation_criteria）。可直接用 `examples/sample-blueprint.json` 作模板。
5. **编译成包**：运行
   ```bash
   python scripts/compile_skill.py --blueprint <blueprint.json> --out <目标父目录>
   ```
   脚本会在 `<目标父目录>/<name>/` 下生成完整包（SKILL.md、agents/openai.yaml、scripts/update_self.py、references/ 各 stub、evaluations/self-eval.md）。用法见 `references/compile-guide.md`。
6. **质量评估**：按 `references/evaluator.md` 的 4 维 rubric（专业度 / 完整度 / 任务成功率 / 错误率）对生成包自评，输出评分卡并把结论写入生成包的 `evaluations/self-eval.md`。
7. **交付与迭代**：把生成包路径交给用户，说明边界与下一步（补充 references 内容、联网核验、灰度试用）。用户改 blueprint 后可重跑第 5 步重编译。

## 交互式启动规则

- 用户信息不足时，按「决策树」逐面抛出问题簇（每面 3–6 题），不要用「我先分析一下」绕过需求采集。
- **10 维度全覆盖**：F0 身份、F1 受众、F2 目标/类型、F3 输入、F4 流程、F7 边界、F8 数据、F9 交互质量 每个 Skill 必过；F5 分析框架（分析/决策型必问）、F6 输出规格（有产出物必问）。
- Path A 至少要确认：目标对象、使用场景、希望 Skill 帮到哪一步、产出形态（md/html/…）、输入从哪来、要不要联网/API。
- Path B 至少要确认：用户角色、最常被问/最常被求助的任务、1–2 个成功案例、踩过的坑、经验里的判断规则。
- 若用户一次性给足目标 + 场景 + 边界 + 输出，其余缺口列为假设请确认，直接进蓝图。

## 必查清单

每次完整产出 Skill 至少覆盖：

- 是否有清晰的 `name`（小写连字符）与英文 `description`（以 "Use when..." 起头，写明触发条件）。
- 是否有 3–8 条明确能力（capabilities），每条可独立验证。
- 是否同时写了「包含」与「不包含」边界。
- **是否有 `input_spec`**：输入渠道、必填/选填、格式、缺失行为。
- **是否有 `output_spec`**（有产出物时）：交付形态（md/html/json/对话/多文件）、结构、篇幅、语气、文件名约定。
- **是否有 `analysis`**（分析/决策型时）：分析维度、打分方式、证据严谨度、对标/可视化。
- 是否有 `interaction_model`：交互模式、澄清风格、不确定时的处理。
- 是否有 ≥1 个 reference（哪怕只是 stub），覆盖核心方法论或数据来源。
- 生成的包是否通过 `compile_skill.py` 的结构校验（frontmatter 合法、目录齐全、新章节渲染正确）。
- 是否跑过 evaluator 并写入 `evaluations/self-eval.md`。

## 适用边界

- 本 skill 产出的是 **Skill 脚手架 + 蓝图**，不是开箱即用的领域专家；references 的 stub 需要用户/ Agent 后续填实。
- 不替用户做业务决策（如「买哪只股票」），只把能力结构化。
- 生成的 `scripts/update_self.py` 默认指向本仓库（sljdxde/schrodinger-skills），若发布到别的仓库请改 `REPO_OWNER` / `REPO_NAME`（见 `references/compile-guide.md`）。

## 参考文件

- `references/interview-engine.md`：Path A 四阶段 + Path B 四步的访谈脚本与动态追问规则。
- `references/domain-playbooks.md`：内置 学习 / 旅行 / 投资 / 创作 起步能力清单 + 通用领域模板，用于「领域补全」。
- `references/blueprint-schema.md`：`blueprint.json` 完整字段定义与示例。
- `references/compile-guide.md`：`compile_skill.py` 用法、生成包结构、改名与发布说明。
- `references/evaluator.md`：4 维评分 rubric 与 `self-eval.md` 产出规范。
- `examples/sample-blueprint.json`：一个可直接拿来跑编译的示例蓝图（旅行助手）。
