#!/usr/bin/env python3
"""Skill 版本号管理工具（语义化版本，规则见 docs/versioning.md）。

版本存放位置：
- 普通 skill：SKILL.md frontmatter 的 ``version:`` 字段
- 组合包（bundle）：目录根的 ``VERSION`` 文件

用法：
    python tools/bump_version.py house-buying --part patch    # 1.0.0 -> 1.0.1
    python tools/bump_version.py --all --part minor           # 全部 skill 一起 bump
    python tools/bump_version.py skill-architect --set 1.2.0  # 直接设定（仅单个）
    python tools/bump_version.py --init-missing 1.0.0         # 只给缺版本的补初始版本
    python tools/bump_version.py --check                      # lint：所有 skill 是否声明版本
    python tools/bump_version.py --self-test                  # 离线自测

约定：每次修改某个 skill 的内容，都要 bump 它的版本（patch=修复/文档，
minor=能力或参考文件变化，major=接口/行为不兼容变化）。纯标准库，Python 3.9+。
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "tools", "docs"}

STRICT_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
LOOSE_SEMVER_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
FRONTMATTER_VERSION_RE = re.compile(
    r"^(version:\s*)[\"']?([0-9]+(?:\.[0-9]+){0,2}(?:[-+][0-9A-Za-z.-]+)?)[\"']?\s*$",
    re.MULTILINE,
)


def normalize_semver(text: str) -> str | None:
    """把 1.2 / 1.2.3 / 1.2.3-beta 统一成 X.Y.Z；解析不了返回 None。"""
    match = LOOSE_SEMVER_RE.search(text)
    if not match:
        return None
    patch = match.group(3) or "0"
    return f"{int(match.group(1))}.{int(match.group(2))}.{int(patch)}"


def bump(version: str, part: str) -> str:
    match = STRICT_SEMVER_RE.match(version)
    if not match:
        raise ValueError(f"not a strict semver: {version!r}")
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"unknown part: {part!r}")
    return f"{major}.{minor}.{patch}"


def frontmatter_bounds(text: str) -> tuple[int, int] | None:
    """返回 frontmatter 内容的 [start, end) 区间（不含 --- 分隔线），没有返回 None。"""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    return (3, end)


def read_version(target_dir: Path, kind: str) -> str | None:
    if kind == "version_file":
        version_path = target_dir / "VERSION"
        if not version_path.is_file():
            return None
        return normalize_semver(version_path.read_text(encoding="utf-8", errors="replace"))
    skill_md = target_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    bounds = frontmatter_bounds(text)
    if not bounds:
        return None
    match = FRONTMATTER_VERSION_RE.search(text[bounds[0]:bounds[1]])
    return normalize_semver(match.group(2)) if match else None


def write_version(target_dir: Path, kind: str, new_version: str) -> None:
    if not STRICT_SEMVER_RE.match(new_version):
        raise ValueError(f"refusing to write non-semver: {new_version!r}")
    if kind == "version_file":
        (target_dir / "VERSION").write_text(new_version + "\n", encoding="utf-8")
        return
    skill_md = target_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    bounds = frontmatter_bounds(text)
    if not bounds:
        raise ValueError(f"{skill_md} has no frontmatter to hold a version field")
    fm = text[bounds[0]:bounds[1]]
    if FRONTMATTER_VERSION_RE.search(fm):
        fm = FRONTMATTER_VERSION_RE.sub(lambda m: f"{m.group(1)}{new_version}", fm, count=1)
    else:
        fm = fm + f"\nversion: {new_version}"
    skill_md.write_text(text[:bounds[0]] + fm + text[bounds[1]:], encoding="utf-8")


def discover_targets(repo_root: Path) -> list[tuple[str, Path, str]]:
    """找出所有 (名称, 目录, 类型)；类型为 skill_md 或 version_file。"""
    targets: list[tuple[str, Path, str]] = []
    for skill_md in sorted(repo_root.rglob("SKILL.md")):
        if any(part in SKIP_DIRS for part in skill_md.relative_to(repo_root).parts):
            continue
        targets.append((skill_md.parent.name, skill_md.parent, "skill_md"))
    for version_file in sorted(repo_root.rglob("VERSION")):
        if any(part in SKIP_DIRS for part in version_file.relative_to(repo_root).parts):
            continue
        targets.append((version_file.parent.name, version_file.parent, "version_file"))
    return targets


def find_target(name: str, repo_root: Path) -> tuple[str, Path, str]:
    for target in discover_targets(repo_root):
        if target[0] == name:
            return target
    raise ValueError(f"skill not found: {name!r} (have: {', '.join(t[0] for t in discover_targets(repo_root))})")


def cmd_check(repo_root: Path) -> int:
    targets = discover_targets(repo_root)
    missing = 0
    print(f"{'skill':<28}{'kind':<14}{'version'}")
    for name, path, kind in targets:
        version = read_version(path, kind)
        if version is None:
            missing += 1
            version = "MISSING"
        print(f"{name:<28}{kind:<14}{version}")
    if missing:
        print(f"\n{missing} target(s) missing a version. Fix: python tools/bump_version.py --init-missing 1.0.0", file=sys.stderr)
        return 1
    print("\nall targets have versions")
    return 0


def cmd_init_missing(repo_root: Path, initial: str) -> int:
    if not STRICT_SEMVER_RE.match(initial):
        print(f"error: --init-missing needs strict semver, got {initial!r}", file=sys.stderr)
        return 1
    changed = 0
    for name, path, kind in discover_targets(repo_root):
        if read_version(path, kind) is None:
            write_version(path, kind, initial)
            print(f"init {name}: {initial}")
            changed += 1
    print(f"initialized {changed} target(s)")
    return 0


def cmd_bump(name: str, part: str | None, set_version: str | None, repo_root: Path) -> int:
    tname, path, kind = find_target(name, repo_root)
    current = read_version(path, kind)
    if set_version:
        if not STRICT_SEMVER_RE.match(set_version):
            print(f"error: --set needs strict semver, got {set_version!r}", file=sys.stderr)
            return 1
        new_version = set_version
    else:
        if current is None:
            print(f"error: {tname} has no version; use --set or --init-missing first", file=sys.stderr)
            return 1
        new_version = bump(current, part or "patch")
    write_version(path, kind, new_version)
    print(f"{tname}: {current or 'MISSING'} -> {new_version}")
    return 0


def self_test() -> int:
    failures: list[str] = []

    if bump("1.0.0", "patch") != "1.0.1":
        failures.append("patch bump wrong")
    if bump("1.0.9", "minor") != "1.1.0":
        failures.append("minor bump wrong")
    if bump("1.9.9", "major") != "2.0.0":
        failures.append("major bump wrong")
    if normalize_semver("0.2") != "0.2.0":
        failures.append("normalize 0.2 wrong")
    if normalize_semver("garbage") is not None:
        failures.append("normalize garbage should be None")

    with tempfile.TemporaryDirectory(prefix="bump-version-test-") as tmp_name:
        skill = Path(tmp_name) / "demo-skill"
        skill.mkdir()
        skill_md = skill / "SKILL.md"
        skill_md.write_text("---\nname: demo-skill\ndescription: x\n---\n\n# Demo\n", encoding="utf-8")
        if read_version(skill, "skill_md") is not None:
            failures.append("missing version should read None")
        write_version(skill, "skill_md", "1.0.0")
        if read_version(skill, "skill_md") != "1.0.0":
            failures.append("insert version failed")
        text = skill_md.read_text(encoding="utf-8")
        if "description: x\nversion: 1.0.0\n---" not in text:
            failures.append("version inserted in wrong place")
        write_version(skill, "skill_md", "1.1.0")
        if read_version(skill, "skill_md") != "1.1.0":
            failures.append("replace version failed")
        if skill_md.read_text(encoding="utf-8").count("version:") != 1:
            failures.append("duplicate version lines")

        bundle = Path(tmp_name) / "demo-bundle"
        bundle.mkdir()
        write_version(bundle, "version_file", "0.1.0")
        if read_version(bundle, "version_file") != "0.1.0":
            failures.append("VERSION file roundtrip failed")

    if failures:
        for failure in failures:
            print(f"self-test failed: {failure}", file=sys.stderr)
        return 1
    print("self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump or lint skill versions (semver).")
    parser.add_argument("skill", nargs="?", help="skill 目录名（如 house-buying）")
    parser.add_argument("--part", choices=["major", "minor", "patch"], default="patch", help="bump 哪一段（默认 patch）")
    parser.add_argument("--set", dest="set_version", help="直接设定版本号（仅单个 skill）")
    parser.add_argument("--all", action="store_true", help="对所有 skill 执行 bump")
    parser.add_argument("--init-missing", metavar="VERSION", help="给所有缺版本的 skill 补初始版本")
    parser.add_argument("--check", action="store_true", help="lint：检查所有 skill 是否声明版本")
    parser.add_argument("--self-test", action="store_true", help="离线自测")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.check:
        return cmd_check(REPO_ROOT)
    if args.init_missing:
        return cmd_init_missing(REPO_ROOT, args.init_missing)
    if args.all:
        rc = 0
        for name, _, _ in discover_targets(REPO_ROOT):
            rc = cmd_bump(name, args.part, None, REPO_ROOT) or rc
        return rc
    if not args.skill:
        parser.error("需要提供 skill 名，或用 --all / --check / --init-missing / --self-test")
    return cmd_bump(args.skill, args.part, args.set_version, REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
