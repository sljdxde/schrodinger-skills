# Blueprint Schema — blueprint.json 字段定义

`compile_skill.py` 消费的输入文件。访谈（Interview Engine）结束后，把结论落成这个 JSON 再编译。

## 完整字段

```jsonc
{
  // 必填
  "name": "travel-assistant",              // skill 目录名 & frontmatter name，小写连字符
  "description": "Use when ...",           // 英文描述，以 "Use when" 起头写触发条件
  "capabilities": ["行程规划", "预算控制"],  // 3-8 条能力，每条可独立验证
  "workflow": [                            // 每步 {title, detail} 或字符串
    { "title": "输入采集", "detail": "问清天数/预算/偏好" },
    "输出行程单"
  ],
  "boundaries": {                          // 必须同时有 include/exclude
    "include": ["行程规划", "预算分摊"],
    "exclude": ["代订机票", "签证代办"]
  },

  // 可选
  "display_name": "Travel Assistant",      // SKILL.md 标题与 openai.yaml display_name；缺省用 name
  "intro": "一句话介绍这个 skill 的定位。",
  "trigger": "当用户想规划旅行时使用本 skill……",
  "audience": "自由行用户，多为规划经验有限的小白到进阶。", // F1：使用者画像与水平
  "principles": ["先确认预算再排行程", "……"],  // 缺省给通用三条
  "input_spec": {                         // F3：输入与数据来源
    "channels": ["用户打字", "上传行程偏好表"],
    "formats": ["text", "csv"],
    "required": ["目的地", "天数", "总预算"],
    "optional": ["同行人", "偏好风格", "出行日期"],
    "missing_behavior": "缺失必填项时先追问，不假设"
  },
  "output_spec": {                        // F6：输出规格（有产出物时必填）
    "format": "Markdown 行程单（可下载 .md）",
    "structure": ["每日动线", "预算实况", "备选", "风险标注", "行前清单"],
    "length": "详细",
    "tone": "通俗带解释",
    "language": "简体中文",
    "deliverables": ["output/<目的地>行程单.md"]
  },
  "analysis": {                           // F5：分析框架（仅分析/决策型必填）
    "dimensions": ["地理位置", "价格", "评分", "风险"],
    "scoring": "多目标权衡打分（位置/价格/评分）",
    "rigor": "风险信息必须标来源与获取时间",
    "benchmarks": "同城市同档酒店横向比",
    "visualization": "预算分摊表 + 酒店权衡表"
  },
  "interaction_model": {                  // F9：交互与质量
    "mode": "开工前先问清一簇需求",
    "clarification": "一次性问整簇，不逐条追问",
    "ambiguity": "信息不足先问，不假设"
  },
  "references": [                          // 每个生成 references/<title>.md stub
    { "title": "itinerary-playbook", "outline": "动线排序规则、时间预算分配、可替换景点……" }
  ],
  "data_sources": ["公开机票/酒店比价 API（需 key）", "目的地天气与签证官网"], // F8：外部数据/凭证
  "evaluation_criteria": ["professionalism", "completeness", "task_success", "error_rate"], // 传给 evaluator
  "self_update": true,                     // 是否生成「使用前自检更新」章节与 update_self.py；默认 true
  "short_description": "……",               // openai.yaml short_description；缺省用 description
  "default_prompt": "to plan trips……"      // openai.yaml default_prompt；缺省给通用
}
```

## 校验规则（compile_skill.py 强制）

| 字段 | 规则 |
|---|---|
| `name` | 必填，非空，编译时 slugify 成小写连字符 |
| `description` | 必填字符串，建议 "Use when ..." 开头 |
| `capabilities` | 必填非空数组 |
| `workflow` | 必填非空数组 |
| `boundaries` | 必填对象，且 `include`/`exclude` 都是数组 |
| `references[]` | 每个元素只允许 `title` / `outline` 两个键，`title` 必填 |
| `evaluation_criteria` | 若提供必须是数组 |
| `input_spec` / `output_spec` / `analysis` / `interaction_model` / `audience` / `data_sources` | 均为可选对象/字符串；字段宽松接受，不影响校验通过 |

任何一条不满足，脚本报错退出（exit 1），不会生成半成品。可选字段若提供，会被 `compile_skill.py` 渲染成 SKILL.md 的对应章节（见下）。

## 由访谈到蓝图的映射

| Interview 产出（维度） | blueprint 字段 |
|---|---|
| F0 用户一句话目标 + 场景 | `description` / `trigger` / `intro` |
| F1 用户与场景 | `audience` / `intro` |
| F2 领域补全勾选结果 | `capabilities` |
| F3 输入与数据来源 | `input_spec` |
| F4 工作流（输入→…→输出） | `workflow` / `principles` |
| F5 分析框架 | `analysis` |
| F6 输出规格 | `output_spec` |
| F7 边界设计（包含/不包含） | `boundaries` |
| F8 需要的参考材料 / 外部数据 | `references[]` / `data_sources` |
| F9 交互与质量 | `interaction_model` / `evaluation_criteria` |
| Path B 的判断规则/负面案例 | 高频规则进 `capabilities`，完整库进 `references` outline |
