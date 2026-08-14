# 端到端示例（examples）

下面走一遍完整流程，证明 skill 怎么工作。假设用户上传 `frontend-notes.md`（内容：DOM、div、事件委托），说「帮我学懂并记住，出个能下载的包」。

## 第 1 步：输入采集

- `.md` → `Read` 直接读，拿到三段：DOM、div、事件委托。
- 受众默认进阶偏小白；导出=是；语言=中文。
- 不追问（信息够）。

## 第 2 步：概念解析

抽 3 个概念：
- `DOM`（文档对象模型）—— 用户可能不熟 → 标 `web_deepdive`
- `div`（块级容器标签）—— 半熟
- `事件委托`（利用冒泡批量监听）—— 不熟 → 标 `web_deepdive`

关系：根「前端核心」→ 分类「结构（DOM、div）」+「行为（事件委托）」。

## 第 3 步：Web 深潜（DOM、事件委托）

调 `web-access` 取 MDN：
- DOM 树示意图 → 手绘内联 SVG（document → html → body → div 的树）。
- 事件流（捕获→目标→冒泡）→ 画一条从上到下的流向 SVG。
- 标来源：`MDN Web Docs；获取：2026-08-01`。

## 第 4 步：逐概念锻造（节选 DOM 卡）

```
term: DOM（文档对象模型）
card_front: DOM 是什么？用一句话 + 一个类比说明。
card_back: 浏览器把 HTML 解析成一棵「树」对象，JS 能增删改查这棵树。
plain:
  - 每个标签变成一个「节点」，父子关系就是树的枝干
  - JS 通过 document.getElementById 等 API 操作节点
  - 改了树，页面就跟着变（这就是「动态网页」的原理）
story: 把 DOM 想成家谱树：document 是老祖宗，<html> 是它的孩子，<body> 再往下，
       你改某个子孙（节点），整棵树的展示就变——JS 就是那个能修剪枝叶的园丁。
mnemonic: DOM = Document Object Map（文档对象地图）
visual: { "type": "svg", "svg": "<svg>...家谱树...</svg>" }
quiz: { "q": "DOM 把页面表示成什么结构？", "type": "mc",
        "options": ["树","栈","队列","图"], "answer": 0,
        "explain": "DOM 是树形结构，标签间是父子/兄弟嵌套关系。" }
feynman: 用自己的话讲：为什么改 JS 就能改页面？
web_source: "来源：MDN Web Docs《DOM》；获取：2026-08-01"
```

## 第 5 步：复习计划

每个概念默认 `ef=2.5` → `intervals: [1, 6, 16, 40]`。

## 第 6 步：预览 + 交付

- Inline：先用 Visualizer `show_widget` 渲染 DOM 翻转卡（可点正/反）+ 1 道自测。
- 导出：写 `payload.json`（3 概念 + 复习），运行
  ```bash
  python scripts/build_package.py --in payload.json --out memory-forge-package.html
  ```
  落盘后把路径给用户。

包内章节：故事区 → 3 张翻转卡（含 DOM/事件流内联 SVG）→ 3 道自测（即时判分）→ 复习计划（0–5 自评、SM-2 即时算下次间隔）。完全离线。

> 这个示例对应的真实测试，见本 skill 在「中心荣誉与资质」材料上的走查（开发完成后由 Agent 实跑验证）。
