#!/usr/bin/env python3
"""Generate an interactive HTML report from skill-governor scan results.

Reads skill-registry.yaml and skill-state.yaml, analyses plugin vs standalone
skills, detects conflicts, and produces a self-contained HTML report with
automated recommendations and cleanup commands.

Usage:
    python3 scripts/html_report.py [--registry PATH] [--state PATH] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.common import default_agents_home
from scripts.reconcile import load_simple_yaml

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "report_template.html"

# ── Chinese descriptions for well-known capabilities ──────────────────────
CAP_CN = {
    "document.pdf": "PDF 文档处理",
    "document.presentation": "演示文稿制作",
    "document.spreadsheet": "电子表格处理",
    "document.word": "Word 文档处理",
    "web.browsing": "网页浏览与搜索",
    "git.workflow": "Git 工作流",
    "development.workflow": "开发工作流",
    "meta.skill-governance": "技能治理（元管理）",
    "communication.email": "邮件通信",
    "news.ai": "AI 资讯",
}


def _cap_cn(cap_id: str) -> str:
    return CAP_CN.get(cap_id, cap_id)


def _dir_key(path: str) -> str:
    """Return the skill-directory root (parent of the skill folder)."""
    p = Path(path)
    return str(p.parent)


def _dir_label(dir_key: str) -> str:
    """Human-friendly label for a scan directory."""
    d = Path(dir_key)
    home = Path.home()
    try:
        rel = d.relative_to(home)
        return "~/" + str(rel).replace("\\", "/")
    except ValueError:
        return dir_key


def _trash_cmd(path: str) -> str:
    """Return a shell command to move a path to trash/recycle bin."""
    if sys.platform == "darwin":
        return f'osascript -e \'tell application "Finder" to delete (POSIX file "{path}" as alias)\''
    elif sys.platform.startswith("win"):
        # PowerShell: use Shell.Application to recycle
        return f'(New-Object -ComObject Shell.Application).Namespace(0).MoveHere("{path}")'
    else:
        return f'gio trash "{path}"'


def _rm_cmd(path: str) -> str:
    if sys.platform.startswith("win"):
        return f'rmdir /s /q "{path}"'
    return f'rm -rf "{path}"'


def build_report_data(registry: dict, state: dict) -> dict:
    installed = state.get("skills", {})

    # ── 1. Directory scan info ────────────────────────────────────────────
    dir_groups: dict[str, list[dict]] = defaultdict(list)
    for name, info in sorted(installed.items()):
        dk = _dir_key(info.get("path", ""))
        dir_groups[dk].append({
            "name": name,
            "plugin": info.get("pluginName"),
            "source": info.get("source", "local"),
            "is_symlink": info.get("is_symlink", False),
            "real_path": info.get("real_path", info.get("path", "")),
        })

    scan_dirs = []
    for dk in sorted(dir_groups.keys()):
        items = dir_groups[dk]
        plugins = set(it["plugin"] for it in items if it["plugin"])
        link_count = sum(1 for it in items if it["is_symlink"])
        scan_dirs.append({
            "path": dk,
            "label": _dir_label(dk),
            "count": len(items),
            "link_count": link_count,
            "real_count": len(items) - link_count,
            "plugins": sorted(plugins),
            "skills": items,
        })

    # ── 2. Plugin groups ─────────────────────────────────────────────────
    plugin_map: dict[str, list[dict]] = defaultdict(list)
    for name, info in sorted(installed.items()):
        pn = info.get("pluginName")
        if pn:
            plugin_map[pn].append({
                "name": name,
                "path": info.get("path", ""),
                "capability": info.get("capability", ""),
                "description": info.get("description", ""),
            })

    plugins = []
    for pn in sorted(plugin_map.keys()):
        skills = plugin_map[pn]
        caps = sorted(set(s["capability"] for s in skills))
        plugins.append({
            "name": pn,
            "skill_count": len(skills),
            "skills": skills,
            "capabilities": caps,
        })

    # ── 3. Capabilities with conflict analysis & recommendations ─────────
    capabilities = []
    for cap_id, cap in registry.get("capabilities", {}).items():
        primary = cap.get("primary")
        candidates = []
        for name, info in cap.get("candidates", {}).items():
            skill_state = installed.get(name, {})
            candidates.append({
                "name": name,
                "status": info.get("status", "unknown"),
                "source": info.get("source", "local"),
                "path": info.get("path", skill_state.get("path", "")),
                "real_path": skill_state.get("real_path", info.get("path", "")),
                "is_symlink": skill_state.get("is_symlink", False),
                "description": skill_state.get("description", ""),
                "pluginName": info.get("pluginName"),
            })
        candidates.sort(key=lambda c: (0 if c["status"] == "active" else 1, c["name"]))

        # Analysis
        active_list = [c for c in candidates if c["status"] == "active"]
        plugin_candidates = [c for c in candidates if c["pluginName"]]
        standalone_candidates = [c for c in candidates if not c["pluginName"]]
        has_conflict = len(active_list) > 1

        # Recommendation
        recommendation = None
        suggested_primary = primary
        if has_conflict:
            if plugin_candidates:
                # Prefer plugin skill
                suggested_primary = plugin_candidates[0]["name"]
                others = [c["name"] for c in active_list if c["name"] != suggested_primary]
                recommendation = {
                    "action": "prefer-plugin",
                    "primary": suggested_primary,
                    "demote": others,
                    "reason": f"插件 {plugin_candidates[0]['pluginName']} 提供的 {suggested_primary} 更可靠，建议保留它作为主技能",
                }
            else:
                # All standalone — keep current primary, demote others
                suggested_primary = primary or active_list[0]["name"]
                others = [c["name"] for c in active_list if c["name"] != suggested_primary]
                recommendation = {
                    "action": "resolve-conflict",
                    "primary": suggested_primary,
                    "demote": others,
                    "reason": f"多个独立技能冲突，建议保留 {suggested_primary}（当前 primary）",
                }
        elif len(active_list) == 1 and len(standalone_candidates) > 1:
            # No conflict but multiple standalones — suggest cleanup
            shadows = [c for c in standalone_candidates if c["status"] == "shadow"]
            if len(shadows) >= 2:
                recommendation = {
                    "action": "cleanup-shadows",
                    "keep": active_list[0]["name"],
                    "remove": [c["name"] for c in shadows],
                    "reason": f"有 {len(shadows)} 个 shadow 技能可以清理以减少混乱",
                }

        capabilities.append({
            "id": cap_id,
            "label": _cap_cn(cap_id),
            "primary": primary,
            "suggested_primary": suggested_primary,
            "candidates": candidates,
            "has_conflict": has_conflict,
            "recommendation": recommendation,
        })
    capabilities.sort(key=lambda c: (0 if c["has_conflict"] else 1, c["id"]))

    # ── 4. Uncategorized with auto-classify suggestions ─────────────────
    uncategorized = []
    for name, info in registry.get("uncategorized", {}).items():
        skill_state = installed.get(name, {})
        desc = skill_state.get("description", "")
        # Try to suggest a capability based on description keywords
        suggested_cap = _suggest_capability(name, desc)
        uncategorized.append({
            "name": name,
            "status": info.get("status", "review-required"),
            "reason": info.get("reason", ""),
            "path": info.get("path", skill_state.get("path", "")),
            "description": desc,
            "pluginName": skill_state.get("pluginName"),
            "suggested_cap": suggested_cap,
        })
    uncategorized.sort(key=lambda s: s["name"])

    # ── 5. Cleanup plan ─────────────────────────────────────────────────
    cleanup_plan = _build_cleanup_plan(installed, capabilities, uncategorized)

    # ── 6. Summary ───────────────────────────────────────────────────────
    total = len(installed)
    plugin_count = sum(1 for s in installed.values() if s.get("pluginName"))
    standalone_count = total - plugin_count
    conflict_count = sum(1 for c in capabilities if c["has_conflict"])

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_skills": total,
        "plugin_count": plugin_count,
        "standalone_count": standalone_count,
        "total_capabilities": len(capabilities),
        "conflict_count": conflict_count,
        "uncategorized_count": len(uncategorized),
        "scan_dirs": scan_dirs,
        "plugins": plugins,
        "capabilities": capabilities,
        "uncategorized": uncategorized,
        "cleanup_plan": cleanup_plan,
    }


def _suggest_capability(name: str, desc: str) -> str:
    """Best-effort capability suggestion for uncategorized skills."""
    hay = f"{name} {desc}".lower()
    if any(t in hay for t in ["search", "搜索", "浏览", "browser", "web"]):
        return "web.browsing"
    if any(t in hay for t in ["git", "commit", "pr", "release"]):
        return "git.workflow"
    if any(t in hay for t in ["test", "debug", "build", "测试", "调试", "构建"]):
        return "development.workflow"
    if any(t in hay for t in ["pdf", "文档", "document"]):
        return "document.pdf"
    if any(t in hay for t in ["slide", "ppt", "演示"]):
        return "document.presentation"
    if any(t in hay for t in ["sheet", "excel", "表格", "csv"]):
        return "document.spreadsheet"
    if any(t in hay for t in ["image", "图", "screenshot", "截图"]):
        return "web.browsing"
    if any(t in hay for t in ["note", "笔记", "knowledge", "知识"]):
        return "development.workflow"
    return ""


def _build_cleanup_plan(installed: dict, capabilities: list, uncategorized: list) -> dict:
    """Generate actionable cleanup recommendations."""
    actions = []

    # 1. For each conflict resolution
    for cap in capabilities:
        rec = cap.get("recommendation")
        if not rec:
            continue
        if rec["action"] == "prefer-plugin":
            for name in rec.get("demote", []):
                skill = installed.get(name, {})
                actions.append({
                    "type": "demote",
                    "skill": name,
                    "path": skill.get("path", ""),
                    "is_plugin": bool(skill.get("pluginName")),
                    "command": "",  # demote is just a policy change
                    "reason": f"与插件技能冲突，降级为 shadow",
                })
        elif rec["action"] == "cleanup-shadows":
            for name in rec.get("remove", []):
                skill = installed.get(name, {})
                path = skill.get("path", "")
                actions.append({
                    "type": "remove-standalone",
                    "skill": name,
                    "path": path,
                    "is_plugin": False,
                    "command": _rm_cmd(path),
                    "reason": "多余的 shadow 技能，可安全删除",
                })

    # 2. Group plugin cleanup
    plugin_dirs = set()
    for name, info in installed.items():
        if info.get("pluginName"):
            plugin_dirs.add((_dir_key(info.get("path", "")), info["pluginName"]))

    # 3. Uncategorized — suggest skip or classify
    for u in uncategorized:
        if u.get("suggested_cap"):
            actions.append({
                "type": "classify",
                "skill": u["name"],
                "path": u.get("path", ""),
                "capability": u["suggested_cap"],
                "reason": f"根据描述建议归类到 {u['suggested_cap']}",
            })

    return {
        "actions": actions,
        "plugin_dirs": [{"path": p, "plugin": pn} for p, pn in sorted(plugin_dirs)],
    }


def generate_html(data: dict) -> str:
    tpl = TEMPLATE_PATH.read_text(encoding="utf-8")
    return tpl.replace("__REPORT_DATA__", json.dumps(data, ensure_ascii=False))


def main() -> None:
    agents_home = default_agents_home()
    parser = argparse.ArgumentParser(description="Generate interactive HTML skill report.")
    parser.add_argument("--registry", type=Path, default=agents_home / "skill-registry.yaml")
    parser.add_argument("--state", type=Path, default=agents_home / "skill-state.yaml")
    parser.add_argument("--output", "-o", type=Path, default=agents_home / "skill-report.html")
    args = parser.parse_args()

    if not args.registry.exists():
        print(f"Error: registry not found at {args.registry}", file=sys.stderr)
        print("Run reconcile.py first.", file=sys.stderr)
        sys.exit(1)

    registry = load_simple_yaml(args.registry)
    state = load_simple_yaml(args.state)
    data = build_report_data(registry, state)
    html = generate_html(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Report: {args.output}")
    print(f"Skills: {data['total_skills']} ({data['plugin_count']} plugin, "
          f"{data['standalone_count']} standalone) | "
          f"Conflicts: {data['conflict_count']} | Uncategorized: {data['uncategorized_count']}")


if __name__ == "__main__":
    main()
