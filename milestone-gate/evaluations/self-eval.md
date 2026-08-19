# Self-Eval — milestone-gate

按 evaluator 4 维 rubric 自评（skill-architect v2 之后）。

## 评分卡

| 维度 | 得分 | 说明 |
|---|---|---|
| professionalism（专业度） | 8/10 | 流程源自 WorkBuddy agent_loop / result_presentation / personal_files_safety 的真实规则，非凭空编造；引用了既有安全机制而非重新发明。 |
| completeness（完整度） | 9/10 | 必填字段齐全：name/description/capabilities/workflow/boundaries 均合规；含 input_spec/output_spec/interaction_model/references；两篇 references 已填实而非 stub。 |
| task_success（任务成功率） | 待实测 | 需在 1–2 个真实复杂任务（如建站/数据分析）中实测「里程碑拆分→确认→重做」闭环是否顺滑。 |
| error_rate（错误率） | 待实测 | 需实测危险操作是否被安全规则正确拦截、不达标回退是否保留前序里程碑。 |

## 关键设计决策

- **定位**：本 skill 是「过程编排」而非「领域能力」，刻意只管里程碑与验收，不做业务判断。避免与领域专家/技能重叠。
- **与 Plan 模式的区别**：不要求用户手动切到 Plan 模式，在 Craft 模式下自动施加「画里程碑 + 阶段确认」。
- **省 token 的核心机制**：不达标只回退「当前里程碑」，已达标的前序里程碑保留，不推翻重来。
- **安全协同**：显式声明不覆盖个人文件安全规则，叠加危险前置警告与回收站机制。

## 已识别缺口 / 下一步

- references 偏「规则」还需补 1–2 个真实案例（如「建站任务里程碑拆分样例」），方便用户直接套用。
- 待在真实多步任务中灰度试用，确认触发判据（第 1 节）是否过宽/过窄。
- 若发布到非 schrodinger-skills 仓库，需改 `scripts/update_self.py` 的 REPO_OWNER/REPO_NAME。
