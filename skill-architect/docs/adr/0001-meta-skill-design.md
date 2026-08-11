# 0001 — skill-architect 作为完整 Meta Skill 落地

- 状态：Accepted
- 日期：2026-08-11
- 相关：`SKILL.md`、`scripts/compile_skill.py`、`references/`

## 背景

`Skill_Architect_Product_Design.md` 描述了一个把「模糊需求/个人经验 → 可执行 AI Skill」的引导式创建系统，含 4 个模块：Interview Engine、Domain Knowledge Engine、Skill Compiler、Skill Evaluator，以及 Path A（Need→Skill）/ Path B（Experience→Skill）两条路径。仓库现有 skill 均为「单一领域工具」，无 Meta Skill。

## 决策

1. **完整 Meta Skill**：一次覆盖整条链路（访谈 → 蓝图 → 编译 → 评估），而非只做一个模块。理由：4 个模块是流水线关系，拆开单卖价值减半；Compiler 的产出格式与仓库布局完全同构，是集成点。
2. **双路径**：Agent 按用户信号分流 Path A / Path B，共用同一份 blueprint → compile 管线。理由：文档 §5/§6 都已给出完整流程，双路径让普通用户与专家都能用。
3. **blueprint.json 交接**：访谈产物落成结构化 JSON，`compile_skill.py --blueprint` 消费。理由：机器可读、可重复、改蓝图重编译即可迭代。
4. **全量脚手架**：生成 SKILL.md（frontmatter + 中文正文）、agents/openai.yaml、scripts/update_self.py（复制本 skill boilerplate 并替换 SKILL_NAME）、references/ 各 stub、evaluations/self-eval.md。理由：兑现「生成包立即可装、自带自检更新」的集成承诺。
5. **评分 rubric 评估**：4 维（专业度/完整度/任务成功率/错误率）自评 + 写 self-eval.md，零外部依赖。理由：保持仓库纯标准库风格；双模型 API 对比需密钥且违背零依赖约定。

## 后果

- 生成包是**脚手架**：references 为 stub，需用户/Agent 后续填实；SKILL.md 已含「待补充」标记。
- 生成包的 update_self.py 默认指向本仓库（sljdxde/schrodinger-skills）；发布到别处需改 REPO_OWNER/REPO_NAME。
- 本 skill 自身遵守仓库自检更新约定（scripts/update_self.py --apply）。
