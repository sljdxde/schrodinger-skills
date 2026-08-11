---
name: layout-analysis
description: Use when the user wants a floor-plan (户型) analysis of a residential property — accepts a property web link, a floor-plan image, or manually filled layout data; evaluates space utilization, layout flow, orientation/lighting/ventilation, privacy, and renovation potential, and produces a scored full report with pros/cons and fit-for-whom.
---

# Layout Analysis

面向通用买家的户型分析 skill：无论从网页链接、户型图图片还是手动字段拿到房源，都能输出「优缺点 + 改造建议 + 采光通风朝向 + 综合评分」的完整报告。

## 核心原则

- 先拿到完整的房间清单、面积、尺寸、朝向与开窗信息，信息不足先追问，不凭空分析。
- 所有结论给依据：尺寸比例、朝向、采光面、动线距离都可核验，不编造户型细节。
- 改造建议必须说明可行性（承重/剪力墙风险、公共区域限制），不确定时标注需现场确认。

## 使用前自检更新

每次使用本 skill 前，先运行：

```bash
python scripts/update_self.py --apply
```

该脚本会检查 GitHub 上对应目录是否有更新，发现更新时先备份本地 skill，再自动同步最新文件。若脚本显示已更新，重新读取当前 `SKILL.md` 和相关 references 后再继续；若网络或环境导致更新失败，说明失败原因并继续使用当前版本。

## 何时触发

当用户想分析某个房源的户型（给网页链接、户型图或户型数据）时使用本 skill。

## 工作流

### 1. 输入采集

接受网页链接（抓取贝壳等页面）、户型图图片（读图解析）或手动字段（面积/户型/朝向/尺寸）；缺关键信息先追问。

### 2. 户型解析

提取房间清单、各房间面积与尺寸、朝向、开窗、承重墙线索，落成结构化数据。

### 3. 维度分析

按空间利用/动线/采光通风/私密性/改造潜力五个维度逐项分析，每项给依据。

### 4. 综合评分

各维度 0-5 分打分，加权出总分；给出优缺点清单与适用人群（自住/改善/投资）。

### 5. 输出完整报告

报告结构：概览 → 逐维度分析 → 改造建议 → 评分卡 → 总评与适用人群。

## Skill 边界

**包含：**

- 户型空间与动线分析
- 采光、通风、朝向、噪音、隐私分析
- 改造与装修建议（可行性标注）
- 多户型横向对比（可选）

**不包含：**

- 房价评估与投资建议
- 法律、产权、学区判断
- 装修报价、施工与风水

## 参考文件

- `references/input-parsing.md`：网页链接抓取规则、户型图读图解析要点、手动字段清单与追问策略。
- `references/dimension-checklist.md`：五大分析维度（空间利用/动线/采光通风/私密性/改造潜力）的判断标准与评分锚点。
- `references/renovation-feasibility.md`：可拆改性判断（承重/剪力墙、管线位置）、常见改造手法与风险标注。
- `references/report-template.md`：完整报告结构与评分卡模板。
