#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill Compiler（skill-architect skill 的编译模块）。

读取一份 blueprint.json（字段定义见 ../references/blueprint-schema.md），在
<out>/<name>/ 下脚手架出一个符合 schrodinger-skills 布局、可直接安装的 skill 包：

    <name>/
        SKILL.md                  # frontmatter(name/description) + 中文正文
        agents/openai.yaml        # interface 注册块
        scripts/update_self.py    # 复制本 skill 的 boilerplate 并把 SKILL_NAME 换成新名
        references/<slug>.md      # 每个 reference 一个 stub
        evaluations/self-eval.md  # 评估占位（由 evaluator 填写）

本脚本只负责「结构化编排与文件生成」，不替用户做领域决策；能力、边界、
workflow 都来自 blueprint。纯标准库，Python 3.9+。

用法：
    python scripts/compile_skill.py --blueprint examples/sample-blueprint.json --out ./skills
    python scripts/compile_skill.py --blueprint bp.json --out ./skills --force   # 覆盖已存在目录
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
UPDATER_SOURCE = SKILL_ROOT / "scripts" / "update_self.py"

DISPLAY_NAME_TITLECASE = True  # SKILL.md 一级标题用 Display Name 原样

REQUIRED_TOP_LEVEL = {
    "name": str,
    "description": str,
    "capabilities": list,
    "workflow": list,
    "boundaries": dict,
}

ALLOWED_REFERENCE_FIELDS = {"title", "outline"}


def slugify(name: str) -> str:
    """把名字规范成小写连字符 slug（skill 目录名 / frontmatter name）。"""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError(f"invalid skill name: {name!r}")
    return slug


def validate(bp: dict) -> None:
    """校验 blueprint 的必填结构与类型，失败抛 ValueError。"""
    for field, ftype in REQUIRED_TOP_LEVEL.items():
        if field not in bp:
            raise ValueError(f"blueprint missing required field: {field!r}")
        if not isinstance(bp[field], ftype):
            raise ValueError(f"blueprint field {field!r} must be {ftype.__name__}, got {type(bp[field]).__name__}")

    if not bp["capabilities"]:
        raise ValueError("blueprint 'capabilities' must not be empty")
    if not bp["workflow"]:
        raise ValueError("blueprint 'workflow' must not be empty")

    if "include" not in bp["boundaries"] or "exclude" not in bp["boundaries"]:
        raise ValueError("blueprint 'boundaries' must contain both 'include' and 'exclude' lists")
    for key in ("include", "exclude"):
        if not isinstance(bp["boundaries"][key], list):
            raise ValueError(f"blueprint 'boundaries.{key}' must be a list")

    for ref in bp.get("references", []):
        if not isinstance(ref, dict):
            raise ValueError("blueprint 'references' entries must be objects")
        extra = set(ref) - ALLOWED_REFERENCE_FIELDS
        if extra:
            raise ValueError(f"unexpected reference fields: {sorted(extra)}")
        if not ref.get("title"):
            raise ValueError("each reference entry needs a 'title'")

    criteria = bp.get("evaluation_criteria")
    if criteria is not None and not isinstance(criteria, list):
        raise ValueError("blueprint 'evaluation_criteria' must be a list")


def _bullet(items) -> str:
    return "\n".join(f"- {str(i).strip()}" for i in items if str(i).strip())


def _workflow_text(workflow: list) -> str:
    """把 workflow 渲染成编号小节。条目可以是字符串或 {title, detail} 对象。"""
    lines: list[str] = []
    for idx, step in enumerate(workflow, start=1):
        if isinstance(step, dict):
            title = str(step.get("title", f"步骤 {idx}")).strip()
            detail = str(step.get("detail", "")).strip()
        else:
            title = str(step).strip()
            detail = ""
        lines.append(f"### {idx}. {title}")
        if detail:
            lines.append("")
            lines.append(detail)
        lines.append("")
    return "\n".join(lines).rstrip()


def _references_text(references: list) -> str:
    lines = [f"- `references/{slugify(r['title'])}.md`：{r.get('outline', '').strip() or '(待补充)'}" for r in references]
    return "\n".join(lines)


def _kv_list_block(pairs) -> str:
    """把 [(标题, 内容), ...] 渲染成「**标题：** 内容」的小节块。"""
    lines: list[str] = []
    for title, content in pairs:
        if content is None or str(content).strip() == "":
            continue
        if isinstance(content, list):
            joined = "；".join(str(x).strip() for x in content if str(x).strip())
            if not joined:
                continue
            lines.append(f"- **{title}**：{joined}")
        else:
            lines.append(f"- **{title}**：{str(content).strip()}")
    return "\n".join(lines)


def _render_input_spec(spec: dict) -> str:
    """F3 输入与数据来源 → 章节。"""
    if not isinstance(spec, dict):
        return ""
    block = _kv_list_block([
        ("输入渠道", spec.get("channels")),
        ("输入格式", spec.get("formats")),
        ("必填项", spec.get("required")),
        ("选填项", spec.get("optional")),
        ("缺失关键项时", spec.get("missing_behavior")),
    ])
    return "## 输入与数据来源\n\n" + (block or "（待补充）") + "\n"


def _render_analysis(analysis: dict) -> str:
    """F5 分析框架 → 章节（仅分析/决策型）。"""
    if not isinstance(analysis, dict):
        return ""
    block = _kv_list_block([
        ("分析维度", analysis.get("dimensions")),
        ("打分/评级方式", analysis.get("scoring")),
        ("证据严谨度", analysis.get("rigor")),
        ("对标/对比", analysis.get("benchmarks")),
        ("可视化", analysis.get("visualization")),
    ])
    return "## 分析框架\n\n" + (block or "（待补充）") + "\n"


def _render_output_spec(spec: dict) -> str:
    """F6 输出规格 → 章节。"""
    if not isinstance(spec, dict):
        return ""
    block = _kv_list_block([
        ("交付形态", spec.get("format")),
        ("结构组成", spec.get("structure")),
        ("篇幅与详略", spec.get("length")),
        ("语气与语言", spec.get("tone")),
        ("交付物/文件名约定", spec.get("deliverables")),
    ])
    return "## 输出规格\n\n" + (block or "（待补充）") + "\n"


def _render_interaction(model) -> str:
    """F9 交互与质量 → 章节。"""
    if isinstance(model, dict):
        block = _kv_list_block([
            ("交互模式", model.get("mode")),
            ("澄清风格", model.get("clarification")),
            ("不确定时的处理", model.get("ambiguity")),
        ])
    elif isinstance(model, str) and model.strip():
        block = model.strip()
    else:
        return ""
    return "## 交互方式\n\n" + (block or "（待补充）") + "\n"


def render_skill_md(bp: dict, name: str, display_name: str) -> str:
    """按仓库 SKILL.md 惯例渲染正文（frontmatter + 中文结构）。"""
    caps = _bullet(bp["capabilities"])
    workflow = _workflow_text(bp["workflow"])
    include = _bullet(bp["boundaries"].get("include", []))
    exclude = _bullet(bp["boundaries"].get("exclude", []))
    refs = _references_text(bp.get("references", []))
    trigger = bp.get("trigger", "").strip()
    self_update = bool(bp.get("self_update", True))

    sections = [f"# {display_name}", ""]
    intro = bp.get("intro", "").strip()
    if intro:
        sections += [intro, ""]

    sections += ["## 核心原则", ""]
    principles = bp.get("principles") or [
        "先查证据，再下判断；涉及事实与数据必须标注来源或获取时间。",
        "边界清晰：只做「包含」清单里的事，不做「不包含」清单里的事。",
        "信息不足时先追问，不要用「我先分析一下」绕过需求采集。",
    ]
    sections += _bullet(principles).splitlines() + [""]

    if self_update:
        sections += [
            "## 使用前自检更新", "",
            "每次使用本 skill 前，先运行：", "",
            "```bash",
            "python scripts/update_self.py --apply",
            "```",
            "",
            "该脚本会检查 GitHub 上对应目录是否有更新，发现更新时先备份本地 skill，再自动同步最新文件。若脚本显示已更新，重新读取当前 `SKILL.md` 和相关 references 后再继续；若网络或环境导致更新失败，说明失败原因并继续使用当前版本。",
            "",
        ]

    sections += ["## 何时触发", ""]
    sections += [trigger if trigger else "（待补充：什么场景下使用本 skill，用一句话写清触发条件。）", ""]

    audience = bp.get("audience")
    if audience and str(audience).strip():
        sections += ["", f"**适用对象：** {str(audience).strip()}", ""]

    input_spec = bp.get("input_spec")
    if input_spec:
        sections += [_render_input_spec(input_spec), ""]

    sections += ["## 工作流", "", workflow, ""]

    analysis = bp.get("analysis")
    if analysis:
        sections += [_render_analysis(analysis), ""]

    output_spec = bp.get("output_spec")
    if output_spec:
        sections += [_render_output_spec(output_spec), ""]

    interaction = bp.get("interaction_model")
    if interaction:
        sections += [_render_interaction(interaction), ""]

    sections += ["## Skill 边界", ""]
    sections += ["**包含：**", "", include or "- （待补充）", ""]
    sections += ["**不包含：**", "", exclude or "- （待补充）", ""]

    sections += ["## 参考文件", ""]
    sections += [refs if refs else "- （待补充）", ""]
    data_sources = bp.get("data_sources")
    if isinstance(data_sources, list) and data_sources:
        sections += ["", "**外部数据与凭证（F8）：**", ""]
        sections += _bullet(data_sources).splitlines() + [""]
    elif isinstance(data_sources, str) and data_sources.strip():
        sections += ["", f"**外部数据与凭证（F8）：** {data_sources.strip()}", ""]

    frontmatter = f"---\nname: {name}\ndescription: {bp['description']}\n---"
    return frontmatter + "\n\n" + "\n".join(sections).rstrip() + "\n"


def render_openai_yaml(bp: dict, name: str, display_name: str) -> str:
    short = bp.get("display_name") or display_name
    description = bp["description"]
    return (
        "interface:\n"
        f'  display_name: "{short}"\n'
        f'  short_description: "{bp.get("short_description", "").strip() or description}"\n'
        f'  default_prompt: "Use ${name} {bp.get("default_prompt", "").strip() or "to help the user with the declared task."}"\n'
    )


def copy_updater(target: Path, name: str) -> None:
    """把本 skill 的 update_self.py boilerplate 复制过去并把 SKILL_NAME 换成新名。"""
    source = UPDATER_SOURCE.read_text(encoding="utf-8")
    old_line = 'SKILL_NAME = "skill-architect"'
    new_line = f'SKILL_NAME = "{name}"'
    if old_line not in source:
        raise RuntimeError("updater boilerplate changed; expected line not found: " + old_line)
    target.write_text(source.replace(old_line, new_line), encoding="utf-8")


def write_reference_stub(target: Path, ref: dict) -> None:
    title = str(ref.get("title", "untitled")).strip()
    outline = str(ref.get("outline", "")).strip()
    body = [f"# {title}", ""]
    if outline:
        body += [outline, ""]
    body += [
        "## 内容",
        "",
        "（由 skill-architect 生成的 stub，后续由用户/Agent 按本文件标题与上面大纲补充完整内容。）",
        "",
    ]
    target.write_text("\n".join(body), encoding="utf-8")


def write_self_eval_stub(target: Path, name: str) -> None:
    target.write_text(
        f"""# self-eval — {name}

本文件由 skill-architect 的 evaluator 填写。评估维度（详见 references/evaluator.md）：

- 专业度 (professionalism)
- 完整度 (completeness)
- 任务成功率 (task success rate)
- 错误率 (error rate)

| 维度 | 裸模型基线 | 加载本 skill 后 | 提升 |
|---|---|---|---|
| 专业度 |  |  |  |
| 完整度 |  |  |  |
| 任务成功率 |  |  |  |
| 错误率 |  |  |  |

## 测试任务与结论

（列出 3–5 个代表性任务、观察到的差异与总体结论。）
""",
        encoding="utf-8",
    )


def compile_package(bp: dict, out_dir: Path, force: bool = False) -> Path:
    validate(bp)
    name = slugify(bp["name"])
    display_name = str(bp.get("display_name") or name).strip() or name
    pkg = out_dir / name

    if pkg.exists():
        if force:
            import shutil
            shutil.rmtree(pkg)
        else:
            raise FileExistsError(f"target package already exists: {pkg} (use --force to overwrite)")

    (pkg / "agents").mkdir(parents=True)
    (pkg / "scripts").mkdir(parents=True)
    (pkg / "references").mkdir(parents=True)
    (pkg / "evaluations").mkdir(parents=True)

    (pkg / "SKILL.md").write_text(render_skill_md(bp, name, display_name), encoding="utf-8")
    (pkg / "agents" / "openai.yaml").write_text(render_openai_yaml(bp, name, display_name), encoding="utf-8")
    copy_updater(pkg / "scripts" / "update_self.py", name)
    for ref in bp.get("references", []):
        write_reference_stub(pkg / "references" / f"{slugify(ref['title'])}.md", ref)
    write_self_eval_stub(pkg / "evaluations" / "self-eval.md", name)

    return pkg


def report(pkg: Path) -> None:
    print(f"compiled: {pkg}")
    for path in sorted(pkg.rglob("*")):
        if path.is_file():
            print(f"  {path.relative_to(pkg)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a blueprint.json into a schrodinger-skills package.")
    parser.add_argument("--blueprint", required=True, help="Path to blueprint.json")
    parser.add_argument("--out", required=True, help="Parent directory where <name>/ will be created")
    parser.add_argument("--force", action="store_true", help="Overwrite the target package if it already exists")
    args = parser.parse_args()

    blueprint_path = Path(args.blueprint)
    if not blueprint_path.is_file():
        print(f"error: blueprint not found: {blueprint_path}", file=sys.stderr)
        return 1

    try:
        bp = json.loads(blueprint_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in blueprint: {exc}", file=sys.stderr)
        return 1

    try:
        pkg = compile_package(bp, Path(args.out), force=args.force)
    except (ValueError, FileExistsError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    report(pkg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
