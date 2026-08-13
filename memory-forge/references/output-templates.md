# 输出模板与 JSON Schema（output-templates）

本文件规定每张卡片 / 故事 / 脑图 / 测验 / 复习计划的**内容结构**，以及喂给 `scripts/build_package.py` 的 **JSON 载荷格式**。Agent 产出内容时照这个结构填，再交给脚本渲染成离线 HTML（或 Markdown）。

## 1. 知识卡（concept card）

```
term:        概念名（含必要限定，如「DOM（文档对象模型）」）
card_front:  一张卡正面的引导问题/提示（先让大脑检索）
card_back:   一句话大白话定义（费曼式，术语当场重定义）
plain:       2–4 个要点，用大白话，带一个生活类比
story:       一个具体小故事/类比（抽象概念必填）
mnemonic:    口诀 / 首字句 / 挂钩（清单类必填，单概念可空）
visual:      互补视觉：{ "type": "svg", "svg": "<svg>...</svg>" }
              —— 必须是结构/空间/关系图，不是装饰
quiz:        [{ "q": 题面, "options": [...], "answer": 索引, "explain": 解析 }]
feynman:     一句「用自己的话讲一遍」的提示语
feynman_answer: （可选）点击「复述 / 看标准讲解」后展开的标准讲解；
              不填则由脚本用 card_back + plain + story 自动合成
```

**反面教材**：卡背面放一段 300 字论文摘抄 + 一张无关配图 → 违规（一卡多概念、装饰图、不互补）。

## 2. 故事 / 叙事（narrative，整包层面）

整份材料给一个「总类比 / 总故事」作为开篇叙事区，把零散事实裹进一个画面里（故事优势 93% vs 13%）。结构：

```
narrative_title:  总故事标题
narrative_body:   一段 150–300 字的具体叙事，含人物/场景/冲突/解决
```

例：把「一个数据中心的能力」比喻成「一支球队的荣誉室 + 训练体系 + 装备库」。

## 3. 脑图（mindmap）

```
mindmap:
  root:   主题名
  nodes:  [{ "id": "n1", "parent": null, "label": "分类A" },
           { "id": "n2", "parent": "n1", "label": "概念1" }, ...]
```

规则：根 1 个；一级是 2–6 个分类；二级是概念。脚本按 parent 递归做左→右树布局。

## 4. 自测（quiz）

每概念 1 题即可（先答后揭晓）。题型优先「生成答案」类：

- **填空**：`{ "q": "DOM 把页面表示成____结构", "type": "fill", "answer": "树", "explain": "..." }`
- **单选**：`{ "q": "...", "type": "mc", "options": [...], "answer": 0, "explain": "..." }`

整包统计正确率，错的点回对应卡片复习。

## 5. 复习计划（review_schedule）

每个概念一行：

```
review_schedule:
  - { "concept_id": "c1", "term": "DOM", "ef": 2.5, "intervals": [1, 6, 16, 40] }
```

`intervals` 可由 Agent 按 SM-2（默认 EF=2.5, q=5）直接算好，也可只给 `ef` 让脚本算。包内每个条目带 0–5 自评控件，打分后用 SM-2 在浏览器里即时重算「下次：+N 天」（不跨会话持久化）。

## 6. build_package.py 的完整 JSON Schema

```json
{
  "title": "学习包标题",
  "source": "材料来源描述（如：用户上传 frontend-notes.md / 粘贴文本）",
  "audience": "受众（小白/进阶）",
  "generated_at": "YYYY-MM-DD",
  "narrative": {
    "title": "总故事标题",
    "body": "总叙事正文"
  },
  "concepts": [
    {
      "id": "c1",
      "term": "概念名",
      "card_front": "引导问题",
      "card_back": "一句话大白话",
      "plain": ["要点1", "要点2"],
      "story": "类比/故事",
      "mnemonic": "口诀（可空字符串）",
      "visual": { "type": "svg", "svg": "<svg ...>...</svg>" },
      "quiz": { "q": "题面", "type": "mc", "options": ["A","B"], "answer": 0, "explain": "解析" },
      "feynman": "用自己的话讲一遍的提示",
      "feynman_answer": "（可选）标准讲解：点击「复述 / 看标准讲解」后展开，供对照自评",
      "web_source": "（可选）联网来源+日期"
    }
  ],
  "mindmap": {
    "root": "主题",
    "nodes": [
      { "id": "n1", "parent": null, "label": "分类A" },
      { "id": "n2", "parent": "n1", "label": "概念1" }
    ]
  },
  "review_schedule": [
    { "concept_id": "c1", "term": "概念名", "ef": 2.5, "intervals": [1, 6, 16, 40] }
  ]
}
```

字段说明：
- `plain` 是**字符串数组**（每条一个要点）；为空数组时卡片只显示 `card_back`。
- `visual.svg` 必须是合法 SVG 字符串；脚本用 `html.escape` 处理文字，但 SVG 内部属性请用双引号且避免 `<` `>` 之外的特殊字符；若不需要图，给 `{"type":"none"}`。
- `quiz.type` 支持 `"mc"`（options+answer 索引）与 `"fill"`（answer 为字符串）。
- `web_source` 仅当该概念走联网深潜时填，格式如 `来源：MDN Web Docs；获取：2026-08-01`。

## 7. 调用脚本

```bash
# 生成离线 HTML 学习包
python scripts/build_package.py --in payload.json --out memory-forge-package.html

# 生成 Markdown 版（低成本附加，便于贴笔记/打印）
python scripts/build_package.py --in payload.json --format md --out memory-forge-package.md
```

脚本纯 Python 标准库，无第三方依赖；离线保证：所有 CSS/JS/SVG 内联，无任何外链 CDN。

## 8. 荣誉体系（gamification，可选）

给学习包注入「养成感」：等级 + 经验（XP）+ 勋章墙 + 连续学习 streak，进度存浏览器本地（单个 HTML 包内持久化）。设计细则与默认集见 `references/gamification.md`。结构：

```json
"gamification": {
  "levels":  [ {"level":1,"title":"初心学徒","min_xp":0}, ... ],
  "xp_rules": { "flip_card":3, "quiz_correct":12, "quiz_wrong":3, "review_rate":10, "feynman_done":8 },
  "badges":  [
    { "id":"first_pack","name":"启程","icon":"sprout",
      "desc":"打开学习包即得","trigger":"on_generate" },
    { "id":"streak3","name":"三日之约","icon":"flame",
      "desc":"连续 3 天学习","trigger":"streak>=3" }
  ]
}
```

- 不提供 `gamification` 时脚本用**内置默认集**（7 级 + 11 枚勋章，见 gamification.md）。
- `trigger` 枚举：`on_generate` / `quiz_correct_first` / `quiz_all_correct` / `review_rate_first` / `review_count>=N` / `all_review_ge4` / `feynman_all` / `streak>=N` / `level>=N` / `web_deepdive>=1`。
- `icon` 用**图标名**（Lucide stroke，脚本内联为 SVG，不用 emoji）：`sprout` `snowflake` `target` `sunrise` `shield` `trophy` `pen-line` `flame` `sparkles` `scroll` `compass` `medal` `book` `award` 等；未知名将回退到 `medal`。
- 脚本**自动剔除不可能获得的勋章**（包内无联网深潜 → 不显示「知识猎人」；无费曼卡片 → 不显示「费曼小能手」；无自测 → 不显示「火眼金睛」），保证勋章墙「每一枚都拿得到」。
- Agent 可按材料主题加 `badges`（如荣誉材料加「荣誉满墙」），增强代入感。
