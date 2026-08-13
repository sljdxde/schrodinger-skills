---
name: house-buying
name_zh: 学区房助手
description: Use when evaluating Chinese residential property purchases, school-district homes, target communities, transaction prices, school outcomes, student-source quality, community demographics, housing-price forecasts, or buy/hold/watch recommendations. Also triggered by explicit requests to use the house-buying or 学区房助手 skill, or by natural-language phrases such as 请使用 house-buying 分析、分析学区房、买房值不值得、学区房是否值得买、购房分析、帮我看个房子.
version: 1.5.1
---

# 学区房助手（House Buying）

学区房助手：面向中国住宅（重点学区房）购房决策的尽调与分析 skill。目标不是替用户“算命式预测房价”，而是用可核验公开信息，把目标楼盘、学校、片区、价格和风险放到同一张证据表里，给出明确但带置信度的建议。

## 核心原则

先查证据，再下判断。凡是涉及房价、学校、政策、人口和升学的数据，都必须标注来源、发布日期或获取时间，并在报告中生成**可点击的原始链接（真实 URL）**；找不到公开证据时写“未查到公开数据”，不要补故事。

**五级数据源体系（T0-T4，见 `references/data-source-playbook.md`）**：T0 核心平台（贝壳系=贝壳/链家、我爱我家）为挂牌/成交/带看/房源量的主证据，关键数据至少双平台交叉；T1 官方佐证（住建局/网签平台/自然资源局/不动产登记/统计局/教育局）为冲突裁决最高权重；T1.5 城市本地高频源（杭房数研类）接近网签口径；T2 政务 App（浙里办/随申办/京通等）补充政策与交易数据；T3 交叉验证（诸葛找房/安居客/房天下/58同城）只做交叉比对不单独支撑结论；T4 舆情仅作线索。**同城同一指标尽量多源交叉，标注一致性程度（双源一致/单源/来源冲突）。**

**引用五要素防伪（强制）**：报告中引用的每一项数据必须携带——来源 + 真实 URL + 发布时间/访问时间 + 数据口径（成交/挂牌/网签/参考价）+ 一致性程度。禁止任何无来源数据、编造 URL 或默认口径（见 `report-template.md`「证据引用格式」）。

**小区名、学校名必须经一手或高可信平台核验**：学区以教育局当年招生公告为准，小区以贝壳系（贝壳/链家）、我爱我家等核心平台真实条目为准；名称冲突、校区混淆、来源冲突时必须披露并标记存疑，禁止把近似名或低可信信息当事实写入结论。

城市由用户声明，面向全国房源；同一小区的价格必须给月度时间轴，不能用单一“当前均价”代表趋势。

**最终交付物是单份自包含 HTML 报告**：SVG 走势图、表格、引用链接全部内嵌在同一 .html 文件里；不输出 markdown 分片、不依赖外部图片或本地路径。

## 自动更新（无需手动操作）

本 skill 每次被加载时，Agent 会**自动**执行自检更新（无需你手动敲命令）：

```bash
python scripts/update_self.py --apply
```

脚本会**自动识别安装方式**并采取对应策略（git 感知逻辑见 `scripts/update_self.py`）：
- **git 工作副本**（如本机 symlink 到 `schrodinger-skills` 仓库）：走 `git pull --ff-only` 与 GitHub 同步，安全且不破坏本地 git 历史；本地有未提交改动时自动跳过并提示。
- **非 git 安装**（zip/手动拷贝）：走版本优先 + 清单回退的 zip 覆盖更新，更新前自动备份。

任何网络/代理失败都会**静默降级**（说明原因并继续使用当前版本），不会阻塞分析。若脚本显示已更新，Agent 会重新读取当前 `SKILL.md` 和相关 references 后再继续分析。

**收尾提示（任务完成后必做）**：在给出最终回复之前，运行 `python scripts/update_self.py --report`。若输出非空警告（形如「本次有以下 skill 自动更新未成功…」），须**原样转告用户**失败的具体原因与手动更新步骤；若输出「本次所有 skill 自动更新均成功」，则无需提及。该报告跨 skill 汇总本次会话所有更新失败，符合通用自动更新机制（见 `../skill-auto-update/`）。

## 工作流

1. 自动自检更新：加载本 skill 后第一步**必须**执行 `python scripts/update_self.py --apply`（脚本按 git/非 git 自动选策略，失败静默降级）；若返回 updated，重新读取当前 `SKILL.md` 与 references 后再继续。完成全部分析、给出最终回复前，运行 `python scripts/update_self.py --report`，若输出更新失败警告则原样转告用户（含原因+手动步骤）。
2. 交互式需求采集：先按 `references/intake-questionnaire.md` 判断信息是否足够。缺城市、目标对象、购房目的、预算、首付比例或孩子入学年份时，必须先追问，不要直接联网跑完整报告。
3. 建证据台账：按“事实/数据、来源、时间、适用范围、置信度、备注”记录关键证据。当前数据必须联网核验；不能联网时说明验证受限。
4. 采集数据：按 `references/data-source-playbook.md` 执行，覆盖成交、挂牌、库存、政策、城市基本面和可比楼盘。**先做透第一维度「房价」**（挂牌/成交月度时间轴 + 环比/同比/N月涨跌幅 + 带看/房源量），再按用户诉求逐层展开成交量/供需比/土地出让/学区政策/人口流动/信贷环境（见 `references/dimension-network.md`，脚本 `python scripts/data_sources.py dimensions` 可查各维度字段与来源）。**核心双源：贝壳系（贝壳/链家）+ 我爱我家，关键数据（成交价/挂牌价/小区档案）尽量双平台交叉核对**；杭州叠加杭房数研/小鸡选房高频源；诸葛找房/安居客/房天下/58同城仅作交叉验证。用 `python scripts/data_sources.py sources --city <城市>` 调出该城预置的政府公开源、政务 APP 与本地小程序（`scripts/city_sources.json` 已内置全国省会 + 自治区首府 + 直辖市 + 计划单列市 + 强地级市约 45 城）。按 `references/school-district-workflow.md` 用 `scripts/data_sources.py` 编排取数，网页源遇到反爬时按 `data-source-playbook.md` 的反爬通道处理（配置 endpoint/token/cookie、浏览器化请求或本机 Playwright 渲染公开页面，不破解验证码、不做高频批量抓取）。**学区房须先读取政策与学区源**：`python scripts/data_sources.py policy --city <城市>` 读取 2026 政策基线（多校划片/教师轮岗/户籍脱钩/学位锁定/预警），`python scripts/data_sources.py sources --city <城市>` 调出 `school_district`（区教育局招生专栏 + 对口地段表检索兜底）与 `enrollment_alert`（学区预警红黄牌）源；已公开单小区数据的城市（宁波/苏州/无锡/佛山/珠海等）可用 `python scripts/data_sources.py gov --community <小区> --city <城市>` 直拉 T1 官方成交。**所有采集到的数据点（价格/成交/物业/建成/车位/学区等）必须带真实 URL 引用 + 发布时间 + 数据口径 + 一致性标注，禁止无来源数据。**
5. 计算学区溢价：涉及学区房时，按 `references/school-premium-comparison.md` 对比目标学区房与周边非学区房，量化教育溢价；并在报告结尾按 `references/report-template.md` 的「学区 vs 非学区差异比较与后续走势」专章，给出差异比较与后续走势判断。
6. 补齐教育与社区：涉及学区房或用户提到孩子入学时，必须按 `references/school-and-community-analysis.md` 采集学校升学情况、学校生源、小区人口与居住画像，并按 `references/school-tier-reference.md` 给出目标学校**梯队定位（第一/二/三/四梯队 + 评级依据）**。**初中升学率必须给近 3-5 年数据，并按 `references/school-cohort-analysis.md` 做「生源代际传导分析」**：升学率滞后约 9-15 年，须重建历史升学率对应的当年生源、对比当前生源，预测目标入学批次孩子未来升学表现（如 2028 入学 → 2034 初中 → 2037 中考），给出数量效应/质量效应/学校效应/政策效应四因素拆解与三情景预判。**涉及落户年限/学位占用的，必须按 `references/title-verification-checklist.md` 提示用户执行买前 3 步自查（学位占用/落户年限/合同保护模板），并在报告「学区确定性」章节给出醒目提示框——skill 不机读具体房产的学位/落户状态，仅研究城市政策规则。**
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
- 交易真实度：近 12-36 个月成交价、挂牌价、成交量、挂牌量、议价空间、成交周期、同户型可比样本；**同一小区必须有月度价格时间轴，列出峰值、谷值、当前值、环比/同比与 3/6/12/24/36 个月涨跌幅**；多源交叉的价格标注一致性。
- 市场热度（按需展开）：月度成交量、去化周期（挂牌量/月均成交）、带看量、买方/卖方市场判断。
- 供需与供应（按需展开）：在售挂牌量、近 12 个月成交、涉宅用地出让与楼面价。
- 学校确定性：对口学校、招生政策、落户/房户一致/学位占用规则、学区预警、划片调整风险。**学位占用/落户年限满足度须引导用户按 `references/title-verification-checklist.md` 自行线下核验（学位占用与户籍无关、只与房产使用记录挂钩），skill 不宣称已核验具体房产状态；2026 政策基线（`policy --city`）须作为默认高权重情景输入。**
- 学校质量：官方办学信息、集团化/校区关系、师资与班级规模、可公开核验的升学去向或中考表现；**初中升学率给近 3-5 年（口径对齐），并做生源代际传导分析（见 `school-cohort-analysis.md`）**。
- 学校梯队：按 `references/school-tier-reference.md` 给出目标学校第一/二/三/四梯队评级与依据；公开证据不足时标注“未评级”。
- 学校生源：对口小区构成、房价门槛、租售结构、片区家庭画像、流动性与新增适龄儿童压力。
- 小区人口：户数、常住/租住 proxy、年龄结构 proxy、儿童入学需求 proxy、业主稳定性和换手率。
- 学区溢价：同板块、同年代、同产品力的非学区房价格对比，拆分教育溢价、居住价值和流动性差异。
- 横向比较：选择 2-3 个同城、同价位或同教育诉求的可比片区/楼盘，说明为什么可比。

## 数据可信度

按来源强弱给结论加权（对应五级体系）：

- **高（T1 官方佐证）**：政府统计公报、教育局招生文件、住建局/网签/不动产登记平台、学校官方发布、央行/金融监管公告。
- **中-高（T0 核心平台）**：贝壳/链家成交记录、我爱我家成交记录——成交口径可信度高，挂牌口径反映卖方预期。
- **中（T1.5/T2/T3）**：城市本地高频源（杭房数研类）、政务 App、安居客/房天下/诸葛找房——挂牌口径为主，只做补充或交叉验证。
- **低（T3 中的 58同城 / T4 舆情）**：中介重复房源、自媒体、论坛、业主群转述、未标注来源的榜单。

**冲突裁决**：时间最新 > 口径最权威 > 最接近一手（官方网签/政务网）——见 `data-source-playbook.md`「冲突处理逻辑」。

低可信信息只能作为线索，不能单独支撑结论。涉及学校升学率、重点率、班级水平等敏感指标时，优先使用公开官方材料；若只能找到民间口径，必须标注“非官方、仅作情绪/口碑参考”。

## 输出要求

- **产物：单份自包含 HTML 报告**（`.html`）。SVG 走势图、表格、引用链接全部内嵌；交付前自查无未替换的占位符（如 `<!--...PLACEHOLDER-->`）与外部依赖。报告装配可用 `python scripts/build_report.py --generate --input analysis.json` 参数化生成（引用锚点转换 + 自包含校验自动完成，减少手写遗漏）。
- 开头 5 行内给出结论：建议买入/谨慎可买/继续观望/不建议买入。
- 明确适用前提：自住、学区、改善、投资的结论可能不同。
- 所有价格统一单位，区分成交价、挂牌价、评估价和网传价。
- 价格时间轴必须内嵌 `scripts/data_sources.py` 生成的 SVG 走势图（挂牌 vs 成交双序列），并标注峰/谷/当前值与样本量；样本不足 5 套的月份用空心点，不连实线。
- 涉及学区时给出目标学校**梯队评级**（第一/二/三/四梯队）与依据，见 `references/school-tier-reference.md`。
- 关键事实与数字后标注引用（上标编号），文末生成**可点击参考资料列表**（真实 URL；`data_sources.py` 的 `render_citations()` 可直接生成）。
- **基础信息逐项带来源**：物业公司、建成年代、车位比、容积率、人车分流等每一项数据，报告内对应单元格必须带引用锚点，参考资料给出对应小区页 URL；无来源的基础信息不得出现在报告中（详见 `data-source-playbook.md`「基础信息逐项带来源」）。
- 给出建议价格带、谈判抓手、触发买入/放弃的观察指标。
- 不构成投资建议；提醒用户结合贷款、税费、家庭现金流和实地看房。

## 参考文件

- `references/data-source-playbook.md`：**五级数据源体系（T0-T4）数据源清单**、证据台账、**引用五要素格式规范**、**多源冲突裁决逻辑**、价格时间轴要求、45 城源注册表（含 gov URL）、反爬取数通道。
- `references/dimension-network.md`：**单一维度展开策略**——先做透「房价」维度（挂牌/成交/环比/同比/N月涨跌幅/带看/房源量），再逐层扩展成交量/供需比/土地出让/学区政策/人口流动/信贷环境；各维度字段、来源、展开条件与维度联动。
- `references/school-district-workflow.md`：学区/直接给小区两种入口的标准取数与分析流程，配套 `scripts/data_sources.py`。
- `references/intake-questionnaire.md`：交互式需求采集、必填字段和追问策略。
- `references/school-premium-comparison.md`：学区房与周边非学区房价格对比、溢价计算和解释规则。
- `references/school-and-community-analysis.md`：学校升学、学校生源、小区人口与隐私边界。
- `references/school-cohort-analysis.md`：**生源代际传导分析**——初中升学率滞后约 9-15 年，重建历史生源、对比当前生源、预测目标入学批次未来升学（数量/质量/学校/政策四效应 + 三情景）。
- `references/school-tier-reference.md`：学校梯队评级框架（第一/二/三/四梯队）与主要城市示例。
- `references/forecasting-framework.md`：价格预测模型、情景假设和置信度规则（须结合维度联动关系）。
- `references/report-template.md`：最终报告结构、评分表和「橄榄手记」HTML 视觉规范（单文件自包含、引用五要素可点击）。
- `references/hangzhou-reference.md`：杭州学区房分析参考，使用时必须联网更新；其他城市按 `data-source-playbook.md` 的通用框架补充当地官方来源。
- `references/policy-baseline-2026.md` + `scripts/city_policy.json`：**2026 政策基线快照**（多校划片/教师轮岗/户籍脱钩/学位锁定/预警），逐城结构化、含来源与核实状态，由 `python scripts/data_sources.py policy --city <城市>` 读取；cohort 分析与价格预测须将其设为默认高权重情景。
- `references/title-verification-checklist.md`：**学位占用/落户年限 用户自查清单 + 合同保护模板**（买前 3 步自查 + 《学位未被占用声明书》+ 赔偿条款），弥补 skill 无法机读学位占用的结构性缺口，防踩坑。
- 数据脚本新增能力：`data_sources.py` 的 `policy`（政策基线）、`gov`（T1 官方单小区 adapter，配置 endpoint 直拉、否则检索兜底）、`sources` 现含 `school_district`/`enrollment_alert` 源；`build_report.py --generate --input analysis.json` 参数化装配自包含 HTML 报告。
