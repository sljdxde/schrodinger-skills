"""TDD 测试套件 —— skill 自动更新机制（skill-auto-update/updater.py）。

这些测试在 updater.py 实现之前编写，作为规格（spec）。运行时应全部失败（红），
实现完成后应全部通过（绿）。

覆盖的场景（来自需求）：
1. 触发：无论 skill 以何种方式被引用，使用时必须触发一次更新检查与执行流程。
2. 异常中止：GitHub 拉取超时 / 连接错误等网络异常被捕获，本次更新中止。
3. 任务继续：更新中止后不抛异常，调用方（用户的后续任务）可继续执行。
4. 最终提示：全部任务完成后，报告本次更新未成功的具体原因 + 手动更新步骤。
5. 通用性：机制适用于任意 skill，不硬编码某一个。

Seam（被测公开接口）：
- updater.ensure_skill_updated(skill_name, skill_dir) -> UpdateResult
- updater.format_update_report() -> str | None
- updater.collect_update_issues() -> list[UpdateResult]
- updater.collect_all_outcomes() -> list[UpdateResult]
- updater.clear_registry()  (测试用)

网络操作经 updater._run_update 这一接缝注入（测试中 mock），不真实联网。
"""

import os
import tempfile
import unittest
from unittest import mock

import updater


class TestSkillAutoUpdate(unittest.TestCase):
    def setUp(self):
        # 用临时文件作为共享注册表，避免污染真实环境。
        self._tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self._tmp.close()
        os.environ["SKILL_UPDATE_REGISTRY"] = self._tmp.name
        updater.clear_registry()

    def tearDown(self):
        os.environ.pop("SKILL_UPDATE_REGISTRY", None)
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    # ---- 场景 1：触发 ----
    def test_trigger_runs_update_flow_and_records_outcome(self):
        with mock.patch.object(
            updater, "_run_update", return_value=updater.UpdateStatus.UP_TO_DATE
        ) as m:
            result = updater.ensure_skill_updated("house-buying", "/tmp/fake-hb")
        self.assertTrue(result.triggered, "使用时必须标记 triggered")
        self.assertEqual(result.status, updater.UpdateStatus.UP_TO_DATE)
        m.assert_called_once_with(mock.ANY)  # 更新流程确实被执行了一次
        names = [r.skill_name for r in updater.collect_all_outcomes()]
        self.assertIn("house-buying", names, "触发结果应被记录到注册表")

    # ---- 场景 2 & 3：网络超时中止 + 任务可继续 ----
    def test_network_timeout_aborts_without_raising(self):
        with mock.patch.object(
            updater, "_run_update", side_effect=TimeoutError("git pull timed out")
        ):
            result = updater.ensure_skill_updated("house-buying", "/tmp/fake-hb")
        self.assertEqual(result.status, updater.UpdateStatus.ABORTED_NETWORK)
        self.assertIsNotNone(result.error)
        self.assertIn("TimeoutError", result.error)

    def test_connection_error_aborts(self):
        with mock.patch.object(
            updater, "_run_update", side_effect=ConnectionError("failed to reach github")
        ):
            result = updater.ensure_skill_updated("house-buying", "/tmp/fake-hb")
        self.assertEqual(result.status, updater.UpdateStatus.ABORTED_NETWORK)
        self.assertIsNotNone(result.error)

    def test_task_can_continue_after_abort(self):
        with mock.patch.object(
            updater, "_run_update", side_effect=TimeoutError("timeout")
        ):
            result = updater.ensure_skill_updated("house-buying", "/tmp/fake-hb")
        # 关键：更新中止绝不能阻塞用户后续任务，调用方拿到的就是一个可继续的信号。
        self.assertTrue(result.can_continue)

    # ---- 场景 4：最终提示 ----
    def test_final_report_includes_reason_and_manual_steps(self):
        with mock.patch.object(
            updater, "_run_update", side_effect=TimeoutError("git pull timed out")
        ):
            updater.ensure_skill_updated("house-buying", "/tmp/fake-hb")
        report = updater.format_update_report()
        self.assertIsNotNone(report, "有失败时应返回报告而非 None")
        self.assertIn("house-buying", report, "报告应点名失败的 skill")
        self.assertIn("git pull timed out", report, "报告应给出具体失败原因")
        self.assertIn("手动", report, "报告应给出手动更新步骤")

    # ---- 场景 5：通用性（不硬编码） ----
    def test_mechanism_is_generic_across_skills(self):
        for name in ("code-review", "tdd", "house-buying", "skills-doctor"):
            with mock.patch.object(
                updater, "_run_update", return_value=updater.UpdateStatus.UP_TO_DATE
            ):
                result = updater.ensure_skill_updated(name, "/tmp/fake-" + name)
            self.assertTrue(result.triggered, f"{name} 应被触发")
            names = [r.skill_name for r in updater.collect_all_outcomes()]
            self.assertIn(name, names, f"{name} 的结果应被记录")

    # ---- 辅助：只收集失败项 ----
    def test_collect_update_issues_returns_only_failures(self):
        with mock.patch.object(
            updater, "_run_update", return_value=updater.UpdateStatus.UP_TO_DATE
        ):
            updater.ensure_skill_updated("ok-skill", "/tmp/fake-ok")
        with mock.patch.object(
            updater, "_run_update", side_effect=ConnectionError("boom")
        ):
            updater.ensure_skill_updated("bad-skill", "/tmp/fake-bad")
        issues = updater.collect_update_issues()
        self.assertEqual(
            [r.skill_name for r in issues], ["bad-skill"], "只应收集失败项"
        )

    # ---- 辅助：无失败返回 None ----
    def test_no_issues_returns_none_report(self):
        with mock.patch.object(
            updater, "_run_update", return_value=updater.UpdateStatus.UP_TO_DATE
        ):
            updater.ensure_skill_updated("ok-skill", "/tmp/fake-ok")
        self.assertIsNone(
            updater.format_update_report(), "无失败时应返回 None"
        )


if __name__ == "__main__":
    unittest.main()
