"""skill 自动更新机制（通用，可被所有 skill 套用）。

设计目标（来自需求）：
1. 触发：无论 skill 以何种方式被引用（直接调用 / 间接依赖 / 命令触发），每次用户使用
   时都必须触发一次更新检查与执行流程 —— 接入方式是在该 skill 的 SKILL.md 第 1 步与其
   update_self.py 中调用 ``ensure_skill_updated(<自己的名字>, <自己的目录>)``。
2. 异常中止：GitHub 拉取超时 / 连接错误等网络异常被捕获，仅中止「本次更新」，绝不抛给
   调用方，因此用户的后续任务可继续执行。
3. 最终提示：全部任务完成后调用 ``format_update_report()``，返回失败原因 + 手动更新步骤；
   若无失败则返回 None。
4. 通用性：机制面向任意 skill，不硬编码某一个。

Seam（可注入 / 被测试 mock 的接缝）：
- ``_run_update(skill_dir)``：真正执行更新的网络操作。网络失败时应抛出
  ``TimeoutError`` / ``ConnectionError`` / ``subprocess.TimeoutExpired``，由
  ``ensure_skill_updated`` 统一捕获。
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 公开类型
# ---------------------------------------------------------------------------


class UpdateStatus(str, Enum):
    UPDATED = "updated"
    UP_TO_DATE = "up_to_date"
    SKIPPED = "skipped"          # 本地有未提交改动等，主动跳过（非网络问题）
    ABORTED_NETWORK = "aborted_network"
    ABORTED_OTHER = "aborted_other"


# 网络异常白名单：这些被当作「网络故障」处理 —— 中止更新但不阻塞任务。
NETWORK_ERRORS = (TimeoutError, ConnectionError, subprocess.TimeoutExpired)


@dataclass
class UpdateResult:
    skill_name: str
    triggered: bool
    status: UpdateStatus
    error: Optional[str] = None
    manual_steps: Optional[str] = None
    # 更新失败绝不能阻塞用户的真实任务；调用方永远可以「继续」。
    can_continue: bool = True

    def is_failure(self) -> bool:
        return self.status in (UpdateStatus.ABORTED_NETWORK, UpdateStatus.ABORTED_OTHER)


# ---------------------------------------------------------------------------
# 会话级 / 跨 skill 共享注册表（落盘为 JSON，使不同 skill 副本也能聚合）
# ---------------------------------------------------------------------------

_DEFAULT_REGISTRY = Path.home() / ".workbuddy" / "skill_update_registry.json"


def _registry_file() -> Path:
    return Path(os.environ.get("SKILL_UPDATE_REGISTRY", _DEFAULT_REGISTRY))


def _load_registry() -> dict:
    p = _registry_file()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_registry(data: dict) -> None:
    p = _registry_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _record(result: UpdateResult) -> None:
    data = _load_registry()
    data[result.skill_name] = {
        "skill_name": result.skill_name,
        "triggered": result.triggered,
        "status": result.status.value,
        "error": result.error,
        "manual_steps": result.manual_steps,
        "can_continue": result.can_continue,
    }
    _save_registry(data)


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------


def ensure_skill_updated(
    skill_name: str, skill_dir: Optional[str] = None
) -> UpdateResult:
    """每次 skill 被使用时调用。

    执行一次更新检查与执行流程；若发生网络异常（GitHub pull 超时 / 连接错误），
    仅中止本次更新并返回，绝不向调用方抛出，从而保证用户的后续任务可继续执行。
    """
    skill_dir = Path(skill_dir) if skill_dir else _default_skill_dir(skill_name)

    try:
        status = _run_update(skill_dir)
    except NETWORK_ERRORS as exc:
        result = UpdateResult(
            skill_name=skill_name,
            triggered=True,
            status=UpdateStatus.ABORTED_NETWORK,
            error=f"更新中止：网络异常（{type(exc).__name__}）：{exc}",
            manual_steps=_manual_steps(skill_dir),
        )
        _record(result)
        return result
    except Exception as exc:  # noqa: BLE001 - 任何更新异常都不应阻断用户任务
        result = UpdateResult(
            skill_name=skill_name,
            triggered=True,
            status=UpdateStatus.ABORTED_OTHER,
            error=f"更新中止：{type(exc).__name__}：{exc}",
            manual_steps=_manual_steps(skill_dir),
        )
        _record(result)
        return result

    result = UpdateResult(skill_name=skill_name, triggered=True, status=status)
    _record(result)
    return result


def record_outcome(
    skill_name: str,
    status: UpdateStatus,
    error: Optional[str] = None,
    skill_dir: Optional[str] = None,
) -> UpdateResult:
    """供已有自定义更新逻辑的 skill 桥接：把本次更新结果登记进共享注册表。

    这样即便某个 skill 自带更新实现（而非调用 ``ensure_skill_updated``），
    其失败结果仍能汇入统一的 ``format_update_report()`` 提示。
    """
    result = UpdateResult(
        skill_name=skill_name,
        triggered=True,
        status=status,
        error=error,
        manual_steps=_manual_steps(Path(skill_dir)) if skill_dir else None,
    )
    _record(result)
    return result


def collect_update_issues() -> list[UpdateResult]:
    """返回本次会话中「更新失败」的 skill 列表（供最终报告使用）。"""
    out = []
    for item in _load_registry().values():
        r = _from_dict(item)
        if r.is_failure():
            out.append(r)
    return out


def collect_all_outcomes() -> list[UpdateResult]:
    """返回本次会话中所有被触发过的 skill 更新结果（含成功）。"""
    return [_from_dict(item) for item in _load_registry().values()]


def format_update_report() -> Optional[str]:
    """全部任务完成后调用。

    返回 None 表示本次没有更新失败；否则返回包含「失败原因 + 手动更新步骤」的提示文本。
    """
    issues = collect_update_issues()
    if not issues:
        return None
    lines = [
        "⚠️ 本次有以下 skill 自动更新未成功（已自动跳过，不影响你的任务）：",
    ]
    for r in issues:
        lines.append(f"• {r.skill_name}：{r.error}")
        lines.append(f"  手动更新步骤：{r.manual_steps}")
    lines.append(
        "提示：以上 skill 当前仍使用本地已有版本继续工作，待网络恢复后可手动更新。"
    )
    return "\n".join(lines)


def clear_registry() -> None:
    """测试 / 重置用：清空内存与落盘注册表。"""
    p = _registry_file()
    try:
        p.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 内部实现（真实更新逻辑；测试中经 _run_update 接缝被 mock）
# ---------------------------------------------------------------------------


def _from_dict(item: dict) -> UpdateResult:
    return UpdateResult(
        skill_name=item["skill_name"],
        triggered=item.get("triggered", True),
        status=UpdateStatus(item["status"]),
        error=item.get("error"),
        manual_steps=item.get("manual_steps"),
        can_continue=item.get("can_continue", True),
    )


def _default_skill_dir(skill_name: str) -> Path:
    """在未显式传入目录时，尽力定位 skill 安装目录。"""
    candidates = [
        Path.home() / ".workbuddy" / "skills" / skill_name,
        Path("/Users/yuzhou/.workbuddy/skills") / skill_name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _is_git_worktree(path: Path) -> bool:
    if (path / ".git").exists():
        return True
    return any((p / ".git").exists() for p in [path, *path.parents])


def _is_dirty(path: Path) -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path, capture_output=True, text=True, timeout=20,
        )
        return bool(out.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        return False


def _git_pull_ff_only(path: Path) -> None:
    """fast-forward pull；超时 / 连接错误会作为网络异常上浮。"""
    subprocess.run(
        ["git", "fetch", "--quiet", "origin"],
        cwd=path, check=True, timeout=60,
    )
    subprocess.run(
        ["git", "pull", "--ff-only", "--quiet"],
        cwd=path, check=True, timeout=60,
    )


def _run_update(skill_dir: Path) -> UpdateStatus:
    """真正的更新执行（接缝）。网络失败请抛出 NETWORK_ERRORS 中的异常。"""
    if _is_git_worktree(skill_dir):
        if _is_dirty(skill_dir):
            return UpdateStatus.SKIPPED  # 有未提交改动，安全跳过，不破坏本地工作
        _git_pull_ff_only(skill_dir)
        return UpdateStatus.UPDATED
    # 非 git 安装：此处可接 zip 覆盖逻辑；本机制默认视为已是最新。
    return UpdateStatus.UP_TO_DATE


def _manual_steps(skill_dir: Path) -> str:
    return (
        f"cd {skill_dir} && git pull --ff-only"
        f"（git 安装）；或重新运行 python update_self.py --apply"
    )
