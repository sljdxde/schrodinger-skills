# Skill 自动更新机制 · 接入指南

`schrodinger-skills/skill-auto-update/updater.py` 是一个**通用**自动更新模块，仓库内任意 skill 都能套用。本文件说明如何接入，使「无论 skill 以何种方式被引用，每次用户使用时都触发一次更新检查；网络异常时中止更新但不阻塞任务，并在任务结束后提示失败原因与手动步骤」。

---

## 1. 机制提供什么

| 公开接口 | 作用 |
|---|---|
| `ensure_skill_updated(skill_name, skill_dir)` | 每次 skill 被使用时调用；执行更新流程；**捕获网络异常（GitHub pull 超时 / 连接错误）后仅中止更新、绝不抛异常**，返回 `UpdateResult`（`can_continue=True`） |
| `record_outcome(skill_name, status, error, skill_dir)` | 供已有自定义更新逻辑的 skill 桥接：把本次结果登记进共享注册表 |
| `format_update_report()` | 所有任务完成后调用；返回「失败原因 + 手动更新步骤」文本；无失败返回 `None` |
| `collect_update_issues()` / `collect_all_outcomes()` | 读取本次会话的失败 / 全部更新结果 |

**跨 skill 共享注册表**：默认落盘到 `~/.workbuddy/skill_update_registry.json`。因此不同 skill 的更新失败能在**同一个报告**里汇总（即使各 skill 各自 import 一份模块副本，文件是共享的）。

---

## 2. 为什么必须显式接入（而非系统钩子）

WorkBuddy **没有**「skill 加载时自动执行钩子脚本」的系统级机制。可靠入口只有一个：让每个 skill 在自己的 `SKILL.md` 第 1 步 + `update_self.py` 里调用上述接口。

> 无论用户是 `/skill`、自然语句（如「请使用 house-buying 分析…」）、还是被别的 skill **间接依赖**，只要该 skill 被实际使用，就会走到它的 `SKILL.md` 工作流第 1 步 → 触发更新检查。这就是「以何种方式引用都能触发」的落地方式。

---

## 3. 接入步骤（3 步）

### 步骤 A：每个 skill 准备 `scripts/update_self.py`

**模式 1 — 零自定义（推荐新 skill）**
直接委派给共享模块，并加 `--report` 出口：

```python
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skill-auto-update"))
import updater

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_NAME = SKILL_DIR.name  # 或显式写死 skill 名

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--report", action="store_true")
    args = p.parse_args()
    if args.report:
        print(updater.format_update_report() or "（本次所有 skill 自动更新均成功，无失败项）")
    else:  # --apply（默认）
        r = updater.ensure_skill_updated(SKILL_NAME, str(SKILL_DIR))
        print(json.dumps(r.__dict__, ensure_ascii=False, indent=2))
```

**模式 2 — 已有自定义更新逻辑（如 `house-buying`）**
保留自有逻辑，仅在 `--apply` 完成后把结果桥接到注册表（参考 `house-buying/scripts/update_self.py` 的 `_bridge_to_shared_registry`）：

```python
_shared_updater.record_outcome(
    SKILL_NAME, _shared_updater.UpdateStatus.ABORTED_NETWORK,
    error="GitHub 拉取失败：…", skill_dir=str(SKILL_DIR),
)
```

### 步骤 B：`SKILL.md` 工作流第 1 步

```
1. 自动自检更新：加载本 skill 后第一步必须执行 `python scripts/update_self.py --apply`
   （脚本按 git / 非 git 自动选策略，网络失败静默降级，不阻塞分析）。
```

### 步骤 C：`SKILL.md` 收尾提示

```
完成全部分析、给出最终回复前，运行 `python scripts/update_self.py --report`；
若输出非空警告，须原样转告用户失败原因与手动更新步骤；若提示「均成功」则无需提及。
```

---

## 4. 行为保证（已由 `test_updater.py` 用 TDD 覆盖）

- **触发**：每次使用都触发一次检查（`collect_all_outcomes` 可见记录）。
- **异常中止**：GitHub 拉取超时 / 连接错误被捕获，返回 `ABORTED_NETWORK`，**不抛异常**。
- **任务继续**：`UpdateResult.can_continue` 恒为 `True`，调用方无感继续原有任务。
- **最终提示**：`format_update_report()` 输出含具体失败原因 + 手动 `git pull` 步骤。
- **通用性**：对任意 `skill_name` 生效，绝不硬编码某一个。

---

## 5. 测试

```bash
cd schrodinger-skills/skill-auto-update
python -m unittest test_updater -v
```

覆盖场景：触发记录、网络超时中止不抛、连接错误中止、任务可继续、最终报告含原因+手动步骤、机制通用（非硬编码）、仅收集失败项、无失败返回 None。
