# CONTEXT.md — skill-architect skill 领域词汇表

本文件只定义术语（通用语言），不含实现细节。实现决策见 `docs/adr/`。

## 术语

- **Meta Skill (元技能)**：以「创建/评估其他 Skill」为职责的 Skill。本 skill 是 Meta Skill，其产物是普通 Skill。

- **Path A：Need → Skill (需求驱动)**：用户有一个需求但说不清 Skill 该含什么能力。流程：目标澄清 → 领域补全 → 边界设计 → Skill Blueprint。

- **Path B：Experience → Skill (经验沉淀)**：专家/从业者拥有隐性经验想资产化。流程：领域建模 → 案例提取 → 判断规则提取 → 失败经验提取。

- **动态追问 (Dynamic Follow-up)**：Interview Engine 的核心机制。每次用户回答后分析缺失信息，只生成「当前最缺」的下一问；不是固定问卷。

- **领域补全 (Domain Completion)**：AI 主动列出该领域通常包含的能力清单（如买房含区域/学区/通勤/价格/风险等），让用户发现「自己不知道要什么」。

- **Skill Blueprint (技能蓝图)**：访谈产出的结构化设计对象，含 name / description / capabilities / workflow / boundaries / references / evaluation_criteria。是 Interview Engine 与 Skill Compiler 之间的交接物。

- **Skill Compiler (技能编译器)**：消费 `blueprint.json`，产出本仓库布局的完整 skill 包（`scripts/compile_skill.py`）。

- **skill-package (技能包)**：一个可安装 skill 的目录：`SKILL.md` + `agents/openai.yaml` + `scripts/update_self.py` + `references/` + `evaluations/`。

- **Skill Evaluator (技能评估器)**：用 4 维 rubric（专业度 / 完整度 / 任务成功率 / 错误率）对生成包自评，输出评分卡并写入 `evaluations/self-eval.md`。

- **Skill 边界 (Skill Boundary)**：每个 Skill 必须同时声明「包含」与「不包含」，防止能力范围失控。

- **判断规则 (Decision Rule)**：Path B 从案例中提取的 `IF(条件) → THEN(动作)` 规则，是专家经验的机器可读化形式。

- **负面案例 (Negative Example)**：Path B 提取的失败经验三元组：错误案例 / 原因 / 避免方式。
