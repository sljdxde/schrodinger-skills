# Schrodinger Skills

> *"Skills 之间不应互相观测——直到你主动选择，它们都是叠加态。"*

Schrodinger Skills 是 [余明宸 (sljdxde)](https://github.com/sljdxde) 开源的 AI Skills 合集，遵循 [Agent Skills](https://agentskills.io) 开放标准。

每个 skill 以文件夹形式独立存在，核心是一个 `SKILL.md` 文件。安装时只需对 Agent 说一句话。

---

## Skills

### skill-governor

*当你的 Agent 装了太多插件，不知道该用哪个的时候——让 Skill Governor 来做裁判。*

| 属性 | 值 |
|------|-----|
| 兼容平台 | Claude Code / Codex / OpenCode / Cursor |
| 复杂度 | 中 |
| 有脚本 | `reconcile.py`, `init_policy.py`, `report.py`, `create_ref.py` |
| 有参考资料 | `references/` 目录 |

**功能**：扫描已安装的 Agent Skills，通过策略文件合并冲突，生成路由注册表和冲突报告。支持单目录保存 + 引用（`SKILL.REF`），避免跨目录重复。

**适合**：安装了多个 Agent 插件、需要统一管理 skill 路由的用户。

**不适合**：只装了一两个 skill、没有冲突场景的用户。

---

## 安装

对你的 Agent 说：

```
帮我安装这个 skill：https://github.com/sljdxde/schrodinger-skills/tree/main/skill-governor
```

---

## 注册表

| Skill | ClawHub | Tessl |
|-------|---------|-------|
| skill-governor | v0.1.0 | 0.1.0 |

---

## License

[MIT](LICENSE)
