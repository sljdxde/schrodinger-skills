---
name: memory-forge
description: Use when the user pastes or uploads study material (notes, articles, lecture text, .txt/.md/.docx/.pdf) and wants to understand and remember it — generates one-concept-per-card knowledge cards, plain-language stories and analogies, complementary diagrams, mnemonics, interactive self-test quizzes, and a spaced-repetition (SM-2) review schedule; can open a real browser or search the web to explain unfamiliar terms with authoritative diagrams.
version: 1.4.0
---

# Memory Forge

把任意学习材料（粘贴的大段文字、`.txt` / `.md` / `.docx` / `.pdf`）重新锻造成「好懂 + 好记」的东西。它不替你做笔记摘要，而是用记忆科学把知识点拆成一张张小卡片、配故事/类比/互补图示、出测验、排复习计划——因为人脑对纯文字记忆很烂，对画面和故事好得多。

## 核心原则

- **一概念一卡**：每张卡只装一个知识点，避免挤爆工作记忆（Miller/Cowan：工作记忆约 4 个组块）。
- **抽象必配故事或类比**：每个抽象概念都给一个具体画面（故事优势：Bower & Clark 93% vs 13% 死记；Heath & Aaker 63% vs 5%）。
- **视觉必须互补，绝不装饰**：图要提供文字没有的结构/空间信息（双重编码）；放装饰图或把文字再说一遍会触发冗余效应，反而伤记忆。
- **先问题，后揭示**：每张卡正面是问题/提示，先让大脑检索，再翻背面看答案（测试效应：检索练习 > 重读）。
- **复习用 SM-2 扩展间隔**：默认第 0 天学，之后 +1 / +6 / +16 / +40… 天复习；每次自评 0–5 分，分数驱动下次间隔。
- **让学习者产出**：填空、自己举例子，比被动读记得牢（生成效应）。
- **联网解释必标来源 + 日期**：凡是去网上查的权威解释/图，都要写清出处和获取时间。

## 自动更新（无需手动操作）

本 skill 每次被加载时，Agent 会**自动**执行自检更新（无需你手动敲命令）：

```bash
python scripts/update_self.py --apply
```

脚本会**自动识别安装方式**并采取对应策略（git 感知逻辑见 `scripts/update_self.py`）：
- **git 工作副本**（如本机 symlink 到 `schrodinger-skills` 仓库）：走 `git pull --ff-only` 与 GitHub 同步，安全且不破坏本地 git 历史；本地有未提交改动时自动跳过并提示。
- **非 git 安装**（zip/手动拷贝）：走版本优先 + 清单回退的 zip 覆盖更新，更新前自动备份。

任何网络/代理失败都会**静默降级**（说明原因并继续使用当前版本），不会阻塞分析。

**更新失败汇总**：若本次会话中本 skill（或同批其他 skill）的自动更新因 GitHub 拉取超时等网络异常失败，Agent 会在**所有任务完成后**调用 `python scripts/update_self.py --report`，统一输出失败原因与手动更新步骤（`git pull --ff-only` 或重新安装），不会中途打断你的任务。

> 最近一次更新：2026-08-17（v1.4.0）— **成长系统 v2 大版本升级**：15 级指数曲线（Roguelike 启发）+ 六维 RPG 属性雷达（Lv.5 解锁）+ 连击系统（Lv.10 解锁，最高 2x XP 加成）+ 19 枚勋章含铜/银/金/钻石四阶位 + 里程碑通知 + 完美主义/速学者/连击大师等特殊成就；**Bug 修复**：移动端布局全面适配（荣誉墙纵向堆叠/表格横向滚动/超窄屏双列统计）+ 选择题答案解析强制作答后显示（`[hidden]` CSS 兜底 + init 强制隐藏）。
> 2026-08-13（v1.3.0）— 迭代：费曼标准讲解 / 自测解析支持**离线朗读(TTS)**（Web Speech API，零网络）；荣誉墙新增**重置进度**按钮；填空题答案容错（忽略中英文标点、大小写、空格）；统一设计系统（Claude Design 暖陶土 + 玻璃拟态吸顶荣誉墙）与费曼「复述」标准讲解面板完工。
> 2026-08-13（v1.2.0）— 用于验证自动更新机制在**独立安装（如 codex）**上能否从 GitHub 正常同步；若你在新安装中看到此说明，说明自动更新已成功生效。

## 工作流

1. **自动自检更新**：加载本 skill 后第一步**必须**执行 `python scripts/update_self.py --apply`（脚本按 git/非 git 自动选策略，失败静默降级）；若返回 updated，重新读取当前 `SKILL.md` 与 references 后再继续。
2. **输入采集**：按 `references/input-parsing.md` 摄取材料。粘贴文本直接用；`.txt` / `.md` 用 `Read`；`.docx` 调 `markitdown-skill` 转 md 再读；`.pdf` 先 `Read`，失败退回 `markitdown-skill`。材料过长先分段（chunk）抽取再合并去重。
3. **确认需求（最多问一轮，≤5 个问题）**：受众基础（小白/进阶）、是否需要导出学习包、输出语言（默认中文）、是否有重点章节。信息基本够就直接开工，别用「我先看看」绕过。
4. **概念解析**：把材料拆成概念清单 + 它们的关系；按熟悉度判断哪些概念需要联网深潜（见第 5 步）。
5. **Web 深潜（按需）**：遇到材料里没讲清、或用户明显不熟的术语（如例子里的「发改大脑」「无感监测」），调 `web-access` 取权威解释 + 图（官方文档 / Wikipedia / 行业站点），浓缩进卡片背面；图转内联 SVG 或 `ImageGen` 示意图；标来源 + 日期。规则见 `references/web-deepdive.md`。
6. **逐概念锻造记忆辅助**（严格遵循 `references/memory-science.md` 的 15 条规则）：对每个概念产出
   - 知识卡：正面 = 一个引导问题；背面 = 大白话解释 + 2–4 个要点 + 助记符/口诀。
   - 故事或类比（抽象概念必给）。
   - 互补视觉（结构图 / 示意图 / 关系图），不要装饰图。
   - 自测题（1 道，MCQ 或填空，附解析）。
   - 复习条目（`id` + `EF=2.5, n=0, I=1`）。
   - 费曼自述提示（「用自己的话讲一遍」）。
7. **关系梳理（可选）**：用根节点 + 分类 + 概念把全篇关系理清，作为卡片间的索引线索（学习包以翻转卡呈现，不单独出结构图）。
8. **组装复习计划**：按默认 `EF=2.5` 预生成排程（公式见 `memory-science.md`）。
9. **生成荣誉体系**（遵循 `references/gamification.md`）：默认给一套等级 + 经验 + 勋章墙 + 连续学习 streak；可**按材料主题加定制勋章**（如荣誉材料加「荣誉满墙」、前端材料加「DOM 驯服者」），让收集有语境代入感。把 `gamification` 段写进 `payload.json`，脚本会自动剔除拿不到的勋章（如包内无联网深潜则不显示「知识猎人」）。
10. **预览确认**：先内联渲染 1–2 张翻转卡 + 1 道自测 + 荣誉条，确认方向再继续。用 Visualizer `show_widget`（与导出同源）。
11. **双轨交付**：
    - **Inline**：用 `show_widget` 继续把其余卡片/故事/自测在对话里讲清楚。
    - **导出**：把结构化内容写成 `payload.json`，运行
      ```bash
      python scripts/build_package.py --in payload.json --out memory-forge-package.html
      ```
      （或 `--format md` 出 Markdown 版），用 `Write` 落盘并把路径给用户。包内全部 CSS/JS/SVG 内联，离线可用。
    - **视觉主题**（默认 `claude`）：`--theme claude` 暖象牙底 + 陶土色点缀 + 衬线大标题（Claude Design 风）；`--theme editorial` 暖米纸 + 衬线大标题（杂志风）；`--theme swiss` 近白底 + 单一克莱因蓝 + 全程无衬线 + 直角（瑞士国际主义风）。三套都只用系统字体、零外链、零 emoji。

## 何时追问

- 受众基础缺失：小白需要更多类比/铺垫，进阶可省略基础解释。
- 是否导出、语言、重点：缺失时给默认值（导出=是，语言=中文）并说明。
- 材料本身杂乱、无明确主题：先和用户输入摘要对齐，再开锻。

## 输出要求

- 每张卡只讲一件事；解释用大白话，术语第一次出现必须马上用简单话重定义。
- 视觉和文字互补，不重复、不堆砌装饰。
- 自测题先让答再揭晓解析；鼓励用户自己举例子。
- 复习计划给出明确日期（以「今天」为 D0 推算），不是模糊的「以后复习」。
- 不编造材料里没有的事实；联网补充的内容必须标来源。

## 参考文件

- `references/memory-science.md`：记忆科学证据 + 15 条可落地设计规则（含 SM-2 公式、艾宾浩斯留存率）。
- `references/input-parsing.md`：各输入格式摄取规则、分段阈值、概念抽取与熟悉度判断。
- `references/output-templates.md`：卡片 / 故事 / 测验 / 复习计划模板，以及 `build_package.py` 的 JSON schema。
- `references/web-deepdive.md`：何时联网、可信源优先级、取文取图、图转内联 SVG、标来源日期。
- `references/gamification.md`：荣誉体系设计——等级 / 经验 / 勋章墙 / 连续学习 streak 的实证与默认集、trigger 枚举、定制方式。
- `references/examples.md`：端到端示例（前端资料走完整流程）。
