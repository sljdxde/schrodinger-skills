#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.common import default_agents_home


@dataclass
class ReconcileResult:
    registry: dict[str, Any]
    state: dict[str, Any]
    report: str


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def load_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, raw_line in enumerate(lines):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        # Handle list items: "- value" or bare "-"
        if line.startswith("- ") or line == "-":
            item_value = parse_scalar(line[2:]) if line.startswith("- ") else None
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if isinstance(parent, dict) and not parent:
                # Empty dict placeholder — convert parent to a list
                if len(stack) >= 2:
                    grandparent = stack[-2][1]
                    for k, v in grandparent.items():
                        if v is parent:
                            grandparent[k] = []
                            stack[-1] = (stack[-1][0], grandparent[k])
                            parent = grandparent[k]
                            break
            if isinstance(parent, list):
                if item_value is None:
                    # Bare "-" — start a new dict item
                    new_item: dict[str, Any] = {}
                    parent.append(new_item)
                    stack.append((indent, new_item))
                else:
                    parent.append(item_value)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if isinstance(parent, list):
            continue
        if value:
            if value == "[]":
                parent[key] = []
            else:
                parent[key] = parse_scalar(value)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def dump_simple_yaml(data: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    for key in sorted(data.keys()) if indent else data.keys():
        value = data[key]
        prefix = " " * indent + str(key) + ":"
        if isinstance(value, dict):
            lines.append(prefix)
            lines.append(dump_simple_yaml(value, indent + 2).rstrip())
        elif isinstance(value, list):
            if not value:
                lines.append(prefix + " []")
            else:
                lines.append(prefix)
                for item in value:
                    if isinstance(item, dict):
                        lines.append(" " * (indent + 2) + "-")
                        lines.append(dump_simple_yaml(item, indent + 4).rstrip())
                    else:
                        lines.append(" " * (indent + 2) + f"- {item}")
        elif isinstance(value, bool):
            lines.append(prefix + f" {str(value).lower()}")
        elif value is None:
            lines.append(prefix + " null")
        else:
            text = str(value)
            if text == "" or text.startswith("[") or ":" in text:
                text = json.dumps(text)
            lines.append(prefix + f" {text}")
    return "\n".join(line for line in lines if line is not None) + "\n"


def resolve_ref(ref_path: Path) -> Path | None:
    """Read a SKILL.REF file and return the resolved canonical skill directory."""
    if not ref_path.exists():
        return None
    try:
        text = ref_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    # Support both raw path (single line) and YAML "ref: <path>" format
    target = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("ref:"):
            target = line.split(":", 1)[1].strip().strip("\"'")
        elif target is None:
            target = line.strip("\"'")
    if not target:
        return None
    resolved = Path(target)
    if not resolved.is_absolute():
        resolved = (ref_path.parent / resolved).resolve()
    return resolved if (resolved / "SKILL.md").exists() else None


def parse_frontmatter(skill_path: Path) -> dict[str, str]:
    text = skill_path.read_text(encoding="utf-8")
    match = re.match(r"---\s*\n(.*?)\n---", text, flags=re.DOTALL)
    if not match:
        return {"name": skill_path.parent.name, "description": ""}
    meta: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        if key.strip() in {"name", "description"}:
            meta[key.strip()] = str(parse_scalar(value)).strip()
    meta.setdefault("name", skill_path.parent.name)
    meta.setdefault("description", "")
    return meta


def _word_in(word: str, haystack: str) -> bool:
    return bool(re.search(r"\b" + re.escape(word) + r"\b", haystack))


def infer_capability(name: str, description: str) -> str:
    haystack = f"{name} {description}".lower()
    if any(term in haystack for term in ["skill governor", "installed agent skills", "skill-policy", "skill-registry"]):
        return "meta.skill-governance"
    if "pdf" in haystack:
        return "document.pdf"
    if any(term in haystack for term in ["pptx", "powerpoint", "slide deck", "slides"]):
        return "document.presentation"
    if any(term in haystack for term in ["spreadsheet", "excel", ".xlsx", "csv", "tsv"]):
        return "document.spreadsheet"
    if any(term in haystack for term in ["word document", "docx", "tracked changes", "ooxml"]):
        return "document.word"
    if any(_word_in(t, haystack) for t in ["web", "browser", "playwright", "search"]):
        return "web.browsing"
    if any(_word_in(t, haystack) for t in ["git", "commit", "pull request", "release"]):
        return "git.workflow"
    if any(_word_in(t, haystack) for t in ["test", "debug", "build"]):
        return "development.workflow"
    return "uncategorized"


def read_lock(lock_path: Path) -> dict[str, dict[str, Any]]:
    if not lock_path.exists():
        return {}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    skills = payload.get("skills", {})
    if isinstance(skills, dict):
        return skills
    return {}


def policy_skill_entry(policy: dict[str, Any], skill_name: str) -> dict[str, Any]:
    entry = policy.get("skills", {}).get(skill_name, {})
    return entry if isinstance(entry, dict) else {}


def resolved_capability(
    policy: dict[str, Any], skill_name: str, description: str
) -> str:
    override = policy_skill_entry(policy, skill_name).get("capability")
    if override:
        return str(override)
    return infer_capability(skill_name, description)


def scan_skills(skill_dirs: list[Path], lock_path: Path, policy: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    lock = read_lock(lock_path)
    found: dict[str, dict[str, Any]] = {}
    for skill_dir in skill_dirs:
        if not skill_dir.exists():
            continue
        # Collect SKILL.md and SKILL.REF entries
        skill_files: list[Path] = list(skill_dir.rglob("SKILL.md"))
        ref_files: list[Path] = list(skill_dir.rglob("SKILL.REF"))
        # Index SKILL.md by parent dir for dedup
        md_parents = {f.parent for f in skill_files}
        for skill_file in skill_files:
            meta = parse_frontmatter(skill_file)
            name = meta["name"].strip('"')
            lock_entry = lock.get(name, {})
            description = meta.get("description", "")
            found[name] = {
                "name": name,
                "description": description,
                "path": str(skill_file.parent),
                "capability": resolved_capability(policy or {}, name, description),
                "source": lock_entry.get("source", "local"),
                "sourceUrl": lock_entry.get("sourceUrl"),
                "pluginName": lock_entry.get("pluginName"),
            }
        for ref_file in ref_files:
            # Skip if a real SKILL.md already exists in the same directory
            if ref_file.parent in md_parents:
                continue
            canonical = resolve_ref(ref_file)
            if canonical is None:
                continue
            meta = parse_frontmatter(canonical / "SKILL.md")
            name = meta["name"].strip('"')
            # Skip if already found from a direct scan
            if name in found:
                continue
            lock_entry = lock.get(name, {})
            description = meta.get("description", "")
            found[name] = {
                "name": name,
                "description": description,
                "path": str(canonical),
                "ref": str(ref_file),
                "capability": resolved_capability(policy or {}, name, description),
                "source": lock_entry.get("source", "local"),
                "sourceUrl": lock_entry.get("sourceUrl"),
                "pluginName": lock_entry.get("pluginName"),
            }
    return found


def candidate_status(
    skill_name: str,
    capability_id: str,
    skill: dict[str, Any],
    capability: dict[str, Any],
    policy: dict[str, Any],
) -> str:
    explicit = (
        policy.get("capabilities", {})
        .get(capability_id, {})
        .get("candidates", {})
        .get(skill_name, {})
        .get("status")
    )
    if explicit:
        return explicit
    if skill.get("pluginName"):
        return policy.get("policies", {}).get("newPluginSkill", "dependency-only")
    primary = capability.get("primary")
    if primary == skill_name:
        return "active"
    if primary:
        return policy.get("policies", {}).get("newStandaloneSkill", "shadow")
    return "active"


def reconcile(
    skill_dirs: list[Path],
    lock_path: Path,
    policy_path: Path,
    registry_path: Path,
    state_path: Path,
    report_path: Path,
) -> ReconcileResult:
    policy = load_simple_yaml(policy_path)
    previous_registry = load_simple_yaml(registry_path)
    registry = {
        "version": previous_registry.get("version", 1),
        "capabilities": {},
        "uncategorized": {},
    }

    installed = scan_skills(skill_dirs, lock_path, policy)
    state = {"version": 1, "skills": installed}

    for capability_id, capability in previous_registry.get("capabilities", {}).items():
        for name, candidate in capability.get("candidates", {}).items():
            if name in installed:
                continue
            rebuilt_capability = registry["capabilities"].setdefault(capability_id, {})
            if capability.get("primary"):
                rebuilt_capability["primary"] = capability["primary"]
            rebuilt_capability.setdefault("candidates", {})
            rebuilt_capability["candidates"][name] = dict(candidate)
            rebuilt_capability["candidates"][name]["status"] = "missing"

    for name, skill in sorted(installed.items()):
        capability_id = skill["capability"]
        if capability_id == "uncategorized":
            registry["uncategorized"][name] = {
                "status": "review-required",
                "reason": "No confident capability match",
                "path": skill["path"],
            }
            continue
        policy_capability = policy.get("capabilities", {}).get(capability_id, {})
        capability = registry["capabilities"].setdefault(capability_id, {})
        if policy_capability.get("primary"):
            capability["primary"] = policy_capability["primary"]
        elif "primary" not in capability:
            previous_capability = previous_registry.get("capabilities", {}).get(
                capability_id, {}
            )
            if previous_capability.get("primary"):
                capability["primary"] = previous_capability["primary"]
        capability.setdefault("candidates", {})
        candidate = capability["candidates"].setdefault(name, {})
        candidate.update(
            {
                "status": candidate_status(name, capability_id, skill, capability, policy),
                "source": skill.get("source", "local"),
                "path": skill["path"],
            }
        )
        if skill.get("pluginName"):
            candidate["pluginName"] = skill["pluginName"]
        if skill.get("sourceUrl"):
            candidate["sourceUrl"] = skill["sourceUrl"]
        if "primary" not in capability and candidate["status"] == "active":
            capability["primary"] = name

    report = render_report(registry, installed)
    state_path.write_text(dump_simple_yaml(state), encoding="utf-8")
    registry_path.write_text(dump_simple_yaml(registry), encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    return ReconcileResult(registry=registry, state=state, report=report)


def render_report(registry: dict[str, Any], installed: dict[str, dict[str, Any]]) -> str:
    lines = ["# Skill Governor Report", ""]
    lines.append(f"- Installed skills scanned: {len(installed)}")
    lines.append("")
    lines.append("## Capability Conflicts")
    conflicts = 0
    for capability_id, capability in registry.get("capabilities", {}).items():
        active_candidates = [
            name
            for name, candidate in capability.get("candidates", {}).items()
            if candidate.get("status") == "active"
        ]
        if len(active_candidates) > 1:
            conflicts += 1
            lines.append(
                f"- {capability_id}: primary={capability.get('primary', '(none)')}; "
                f"candidates={', '.join(sorted(active_candidates))}"
            )
    if conflicts == 0:
        lines.append("- None")
    lines.append("")
    lines.append("## Review Required")
    if registry.get("uncategorized"):
        for name in sorted(registry["uncategorized"]):
            lines.append(f"- {name}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    codex_home = default_codex_home()
    agents_home = default_agents_home()
    parser = argparse.ArgumentParser(description="Reconcile installed agent skills.")
    parser.add_argument(
        "--skill-dir",
        action="append",
        type=Path,
        default=None,
        help="Skill directory to scan. Can be passed multiple times.",
    )
    parser.add_argument("--lock", type=Path, default=agents_home / ".skill-lock.json")
    parser.add_argument(
        "--policy", type=Path, default=agents_home / "skill-policy.yaml"
    )
    parser.add_argument(
        "--registry", type=Path, default=agents_home / "skill-registry.yaml"
    )
    parser.add_argument("--state", type=Path, default=agents_home / "skill-state.yaml")
    parser.add_argument(
        "--report", type=Path, default=agents_home / "skill-registry-report.md"
    )
    args = parser.parse_args()
    if args.skill_dir is None:
        args.skill_dir = [codex_home / "skills", agents_home / "skills"]
    return args


def main() -> None:
    args = parse_args()
    args.policy.parent.mkdir(parents=True, exist_ok=True)
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    result = reconcile(
        skill_dirs=args.skill_dir,
        lock_path=args.lock,
        policy_path=args.policy,
        registry_path=args.registry,
        state_path=args.state,
        report_path=args.report,
    )
    print(result.report)


if __name__ == "__main__":
    main()
