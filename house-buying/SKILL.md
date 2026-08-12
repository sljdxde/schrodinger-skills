---
name: house-buying
description: Use when evaluating Chinese residential property purchases, school-district homes, target communities, transaction prices, school outcomes, student-source quality, community demographics, housing-price forecasts, or buy/hold/watch recommendations.
version: 1.0.0
---

# House Buying

面向中国住宅购房决策的尽调与分析 skill。目标不是替用户“算命式预测房价”，而是用可核验公开信息，把目标楼盘、学校、片区、价格和风险放到同一张证据表里，给出明确但带置信度的建议。

## 核心原则

先查证据，再下判断。凡是涉及房价、学校、政策、人口和升学的数据，都必须标注来源、发布日期或获取时间，并在报告中生成**可点击的原始链接（真实 URL）**；找不到公开证据时写“未查到公开数据”，不要补故事。

城市由用户声明，面向全国房源；同一小区的价格必须给月度时间轴，不能用单一“当前均价”代表趋势。

**最终交付物是单份自包含 HTML 报告**：SVG 走势图、表格、引用链接全部内嵌在同一 .html 文件里；不输出 markdown 分片、不依赖外部图片或本地路径。

## 使用前自检更新

每次使用本 skill 前，先运行：

```bash
python scripts/update_self.py --apply
```

该脚本会检查 GitHub 上 `house-buying` 目录是否有更新，发现更新时先备份本地 skill，再自动同步最新文件。若脚本显示已更新，重新读取当前 `SKILL.md` 和相关 references 后再继续分析；若网络或环境导致更新失败，说明失败原因并继续使用当前版本。

## 工作流

1. 自检更新：执行上面的 `scripts/update_self.py --apply`，必要时重新加载 skill。
2. 交互式需求采集：先按 `references/intake-questionnaire.md` 判断信息是否足够。缺城市、目标对象、购房目的、预算、首付比例或孩子入学年份时，必须先追问，不要直接联网跑完整报告。
3. 建证据台账：按“事实/数据、来源、时间、适用范围、置信度、备注”记录关键证据。当前数据必须联网核验；不能联网时说明验证受限。
4. 采集数据：按 `references/data-source-playbook.md` 执行，覆盖成交、挂牌、库存、政策、城市基本面和可比楼盘。**先用用户声明的城市（如上海、北京、杭州）圈定数据源**：全国通用源优先贝壳、我爱我家；并用 `python scripts/data_sources.py sources --city <城市>` 调出该城预置的政府公开源、政务 APP 与本地小程序（`scripts/city_sources.json` 已内置全国省会 + 自治区首府 + 直辖市）。按 `references/school-district-workflow.md` 用 `scripts/data_sources.py` 编排取数，网页源遇到反爬时按 `data-source-playbook.md` 的反爬通道处理（配置 endpoint/token/cookie、浏览器化请求或本机 Playwright 渲染公开页面，不破解验证码、不做高频批量抓取）。
5. 计算学区溢价：涉及学区房时，按 `references/school-premium-comparison.md` 对比目标学区房与周边非学区房，量化教育溢价；并在报告结尾按 `references/report-template.md` 的「学区 vs 非学区差异比较与后续走势」专章，给出差异比较与后续走势判断。
6. 补齐教育与社区：涉及学区房或用户提到孩子入学时，必须按 `references/school-and-community-analysis.md` 采集学校升学情况、学校生源、小区人口与居住画像，并按 `references/school-tier-reference.md` 给出目标学校**梯队定位（第一/二/三/四梯队 + 评级依据）**。
7. 做价格预测：使用 `references/forecasting-framework.md`，先基于近 12-36 个月月度价格时间轴判断动量与波动区间，再输出基准/乐观/悲观三情景，分 6-12 个月、1-3 年、3-10 年给出区间和置信度。
8. 形成结论：使用 `references/report-template.md`，先给结论，再给证据、风险、可执行建议和继续观察指标。

## 交互式启动规则

- 用户信息不足时，先问一轮精简问题，最多 8 个，不要用“我先分析一下”绕过需求采集。
- 城市和目标对象缺失时停止追问；目标对象可以是小区、楼盘、学校或片区。
- 预算、购房目的、孩子入学年份缺失时优先追问；如果用户明确“不涉及学区”，入学年份可记为“无”。
- 户型面积、月供上限、通勤、决策时间和备选小区缺失时，可以继续分析，但必须在报告“用户输入摘要/关键假设”中标注；**首付比例为必填，缺失必须先追问，不再追问首套/二套**。
- 如果用户一次性给足城市、目标对象、购房目的、预算和入学年份，直接进入证据采集，只把其他缺口列为假设。

## 必查清单

每次完整购房分析至少覆盖这些问题：

- 楼盘基本面：位置、建成年代、产品类型、户数、物业、车位、容积率、维护状态、通勤与配套。
- 交易真实度：近 12-36 个月成交价、挂牌价、成交量、挂牌量、议价空间、成交周期、同户型可比样本；**同一小区必须有月度价格时间轴，列出峰值、谷值、当前值和月均波动幅度**。
- 学校确定性：对口学校、招生政策、落户/房户一致/学位占用规则、学区预警、划片调整风险。
- 学校质量：官方办学信息、集团化/校区关系、师资与班级规模、可公开核验的升学去向或中考表现。
- 学校梯队：按 `references/school-tier-reference.md` 给出目标学校第一/二/三/四梯队评级与依据；公开证据不足时标注“未评级”。
- 学校生源：对口小区构成、房价门槛、租售结构、片区家庭画像、流动性与新增适龄儿童压力。
- 小区人口：户数、常住/租住 proxy、年龄结构 proxy、儿童入学需求 proxy、业主稳定性和换手率。
- 学区溢价：同板块、同年代、同产品力的非学区房价格对比，拆分教育溢价、居住价值和流动性差异。
- 横向比较：选择 2-3 个同城、同价位或同教育诉求的可比片区/楼盘，说明为什么可比。

## 数据可信度

按来源强弱给结论加权：

- 高：政府统计公报、教育局招生文件、住建局/网签平台、学校官方发布、上市公司/机构原始数据库。
- 中：贝壳/链家成交记录、我爱我家等主流房产平台、主流媒体、可信研究机构。
- 低：自媒体、论坛、业主群转述、未标注来源的榜单。

低可信信息只能作为线索，不能单独支撑结论。涉及学校升学率、重点率、班级水平等敏感指标时，优先使用公开官方材料；若只能找到民间口径，必须标注“非官方、仅作情绪/口碑参考”。

## 输出要求

- **产物：单份自包含 HTML 报告**（`.html`）。SVG 走势图、表格、引用链接全部内嵌；交付前自查无未替换的占位符（如 `<!--...PLACEHOLDER-->`）与外部依赖。
- 开头 5 行内给出结论：建议买入/谨慎可买/继续观望/不建议买入。
- 明确适用前提：自住、学区、改善、投资的结论可能不同。
- 所有价格统一单位，区分成交价、挂牌价、评估价和网传价。
- 价格时间轴必须内嵌 `scripts/data_sources.py` 生成的 SVG 走势图（挂牌 vs 成交双序列），并标注峰/谷/当前值与样本量；样本不足 5 套的月份用空心点，不连实线。
- 涉及学区时给出目标学校**梯队评级**（第一/二/三/四梯队）与依据，见 `references/school-tier-reference.md`。
- 关键事实与数字后标注引用（上标编号），文末生成**可点击参考资料列表**（真实 URL；`data_sources.py` 的 `render_citations()` 可直接生成）。
- 给出建议价格带、谈判抓手、触发买入/放弃的观察指标。
- 不构成投资建议；提醒用户结合贷款、税费、家庭现金流和实地看房。

## 参考文件

- `references/data-source-playbook.md`：全国城市数据源、搜索关键词、价格时间轴要求、证据台账、质量分级和反爬取数通道（含 `杭房数研`/`小鸡选房` 取数机制）。
- `references/school-district-workflow.md`：学区/直接给小区两种入口的标准取数与分析流程，配套 `scripts/data_sources.py`。
- `references/intake-questionnaire.md`：交互式需求采集、必填字段和追问策略。
- `references/school-premium-comparison.md`：学区房与周边非学区房价格对比、溢价计算和解释规则。
- `references/school-and-community-analysis.md`：学校升学、学校生源、小区人口与隐私边界。
- `references/school-tier-reference.md`：学校梯队评级框架（第一/二/三/四梯队）与主要城市示例。
- `references/forecasting-framework.md`：价格预测模型、情景假设和置信度规则。
- `references/report-template.md`：最终报告结构、评分表和「橄榄手记」HTML 视觉规范（单文件自包含、引用可点击）。
- `references/hangzhou-reference.md`：杭州学区房分析参考，使用时必须联网更新；其他城市按 `data-source-playbook.md` 的通用框架补充当地官方来源。
