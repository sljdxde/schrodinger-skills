#!/usr/bin/env python3
"""Self-update helper for this skill (version-aware).

Update strategy (see docs/versioning.md):

1. Version-first: read the local semantic version (the ``version:`` field in
   SKILL.md frontmatter, or a plain VERSION file when ``VERSION_FILE`` is set)
   and compare it with the remote copy fetched from raw.githubusercontent.com.
   A newer remote version means an update is available. Equal or older remote
   versions mean no update — this avoids downloading the whole repo archive.
2. Manifest fallback (legacy): if either side has no parseable version, fall
   back to the historical behavior — download the repo zip and compare file
   hashes. This keeps old skills and old remote copies fully compatible.

Applying an update replaces the local skill folder after creating a
recoverable backup. No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SKILL_NAME = "mtd-download"
REPO_OWNER = "sljdxde"
REPO_NAME = "schrodinger-skills"
REPO_BRANCH = "main"
VERSION_FILE = None  # None → read `version:` from SKILL.md frontmatter; e.g. "VERSION" for bundles
NPM_PACKAGE = None  # e.g. "agent-skill-doctor" for skills backed by an npm CLI
NPM_COMMAND = None

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}

TEXT_EXTENSIONS = {".md", ".py", ".yaml", ".yml", ".json", ".txt"}

SEMVER_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
FRONTMATTER_VERSION_RE = re.compile(
    r"^version:\s*[\"']?([0-9]+(?:\.[0-9]+){0,2}(?:[-+][0-9A-Za-z.-]+)?)[\"']?\s*$",
    re.MULTILINE,
)


# --------------------------------------------------------------------------
# Version helpers
# --------------------------------------------------------------------------

def parse_semver(text: str) -> tuple[int, int, int] | None:
    """从任意文本里提取第一个语义化版本，返回 (major, minor, patch)。缺 patch 补 0。"""
    match = SEMVER_RE.search(text)
    if not match:
        return None
    major, minor, patch = match.group(1), match.group(2), match.group(3)
    return (int(major), int(minor), int(patch) if patch else 0)


def format_semver(version: tuple[int, int, int]) -> str:
    return f"{version[0]}.{version[1]}.{version[2]}"


def frontmatter_block(text: str) -> str:
    """取出 Markdown 顶部的 YAML frontmatter（--- 到 --- 之间），没有则返回空串。"""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    return text[3:end]


def extract_version_from_skill_md(text: str) -> str | None:
    """只从 SKILL.md 的 frontmatter 里提取 version 字段（正文里的 version 字样不算）。"""
    match = FRONTMATTER_VERSION_RE.search(frontmatter_block(text))
    return match.group(1) if match else None


def read_local_version(skill_dir: Path) -> tuple[int, int, int] | None:
    """读取本地 skill 版本；读不到返回 None（走 manifest 回退）。"""
    if VERSION_FILE:
        version_path = skill_dir / VERSION_FILE
        if version_path.is_file():
            return parse_semver(version_path.read_text(encoding="utf-8", errors="replace"))
        return None
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    raw = extract_version_from_skill_md(skill_md.read_text(encoding="utf-8", errors="replace"))
    return parse_semver(raw) if raw else None


def remote_version_url() -> str:
    filename = VERSION_FILE or "SKILL.md"
    return (
        f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/"
        f"{REPO_BRANCH}/{SKILL_NAME}/{filename}"
    )


def fetch_remote_version(timeout: int = 20) -> tuple[int, int, int] | None:
    """小流量拉取远端版本文件并解析版本；任何失败都返回 None（回退 manifest）。"""
    try:
        with urllib.request.urlopen(remote_version_url(), timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    if VERSION_FILE:
        return parse_semver(text)
    raw = extract_version_from_skill_md(text)
    return parse_semver(raw) if raw else None


def version_relation(local: tuple[int, int, int], remote: tuple[int, int, int]) -> str:
    if remote > local:
        return "newer"
    if remote == local:
        return "equal"
    return "local_ahead"


# --------------------------------------------------------------------------
# Manifest (legacy) comparison
# --------------------------------------------------------------------------

def bytes_for_hash(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            return data.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
        except UnicodeDecodeError:
            return data
    return data


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(bytes_for_hash(path))
    return h.hexdigest()


def manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.is_file():
            result[rel.as_posix()] = sha256_file(path)
    return result


def compare_manifests(local: dict[str, str], remote: dict[str, str]) -> dict[str, object]:
    added = sorted(set(remote) - set(local))
    removed = sorted(set(local) - set(remote))
    changed = sorted(p for p in set(local) & set(remote) if local[p] != remote[p])
    return {
        "update_available": bool(added or removed or changed),
        "added": added,
        "removed": removed,
        "changed": changed,
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changed),
    }


# --------------------------------------------------------------------------
# npm companion package (only used when NPM_PACKAGE is set)
# --------------------------------------------------------------------------

def run_command(args: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, timeout=90)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "command timed out"


def parse_npm_version(text: str) -> str | None:
    match = re.search(r"(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)", text)
    return match.group(1) if match else None


def npm_status() -> dict[str, object]:
    latest_code, latest_out, latest_err = run_command(["npm", "view", NPM_PACKAGE, "version"])
    local_code, local_out, local_err = run_command([NPM_COMMAND, "--version"])
    latest = parse_npm_version(latest_out) if latest_code == 0 else None
    local = parse_npm_version(local_out) if local_code == 0 else None
    return {
        "package": NPM_PACKAGE,
        "command": NPM_COMMAND,
        "local_version": local,
        "latest_version": latest,
        "update_available": bool(latest and latest != local),
        "local_error": local_err if local_code != 0 else None,
        "latest_error": latest_err if latest_code != 0 else None,
    }


def install_latest_npm() -> dict[str, object]:
    code, out, err = run_command(["npm", "install", "-g", f"{NPM_PACKAGE}@latest"])
    return {"attempted": True, "success": code == 0, "stdout": out[-1000:], "stderr": err[-1000:]}


# --------------------------------------------------------------------------
# Filesystem plumbing
# --------------------------------------------------------------------------

def find_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def assert_skill_dir(path: Path) -> None:
    if path.name != SKILL_NAME:
        raise RuntimeError(f"Refusing to update unexpected skill directory: {path}")
    if VERSION_FILE:
        if not (path / VERSION_FILE).is_file():
            raise RuntimeError(f"Missing {VERSION_FILE} in {path}")
    elif not (path / "SKILL.md").is_file():
        raise RuntimeError(f"Missing SKILL.md in {path}")


def inside_git_worktree(path: Path) -> bool:
    return any((parent / ".git").exists() for parent in [path, *path.parents])


def download_remote_skill(tmp: Path) -> Path:
    url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{REPO_BRANCH}.zip"
    archive = tmp / "repo.zip"
    with urllib.request.urlopen(url, timeout=45) as response:
        archive.write_bytes(response.read())
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(tmp / "repo")
    root = tmp / "repo" / f"{REPO_NAME}-{REPO_BRANCH}"
    skill = root / SKILL_NAME
    assert_skill_dir(skill)
    return skill


def make_backup(skill_dir: Path) -> Path:
    backup_root = Path(tempfile.gettempdir()) / "schrodinger-skill-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix=f"{SKILL_NAME}-", dir=backup_root))
    backup_path = backup_dir / SKILL_NAME
    shutil.copytree(skill_dir, backup_path)
    return backup_path


def replace_tree(src: Path, dst: Path) -> Path:
    assert_skill_dir(src)
    assert_skill_dir(dst)
    backup = make_backup(dst)
    try:
        for child in dst.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in src.iterdir():
            target = dst / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
    except Exception:
        for child in dst.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in backup.iterdir():
            target = dst / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
        raise
    return backup


def _download_to_apply_copy() -> Path:
    """下载远端 skill 并复制到独立临时目录（供 apply 使用）。"""
    with tempfile.TemporaryDirectory(prefix=f"{SKILL_NAME}-remote-") as tmp_name:
        remote_skill = download_remote_skill(Path(tmp_name))
        copy_for_apply = Path(tempfile.mkdtemp(prefix=f"{SKILL_NAME}-apply-")) / SKILL_NAME
        shutil.copytree(remote_skill, copy_for_apply)
        return copy_for_apply


# --------------------------------------------------------------------------
# Check / apply
# --------------------------------------------------------------------------

def check_status() -> dict[str, object]:
    skill_dir = find_skill_dir()
    assert_skill_dir(skill_dir)
    local_version = read_local_version(skill_dir)
    remote_version = fetch_remote_version()
    status: dict[str, object] = {
        "skill": SKILL_NAME,
        "local_path": str(skill_dir),
        "source": f"https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/{REPO_BRANCH}/{SKILL_NAME}",
        "npm": npm_status() if NPM_PACKAGE else None,
    }

    if local_version is not None and remote_version is not None:
        relation = version_relation(local_version, remote_version)
        update_available = relation == "newer"
        status["skill_update"] = {
            "method": "version",
            "local_version": format_semver(local_version),
            "remote_version": format_semver(remote_version),
            "relation": relation,
            "update_available": update_available,
            "added": [],
            "removed": [],
            "changed": [],
            "added_count": 0,
            "removed_count": 0,
            "changed_count": 0,
            "note": (
                "remote version is newer; run --apply to download and replace"
                if update_available
                else ("local copy is ahead of remote" if relation == "local_ahead" else "up to date")
            ),
        }
        return status

    # Legacy fallback: full manifest comparison (keeps old skills/remotes working).
    with tempfile.TemporaryDirectory(prefix=f"{SKILL_NAME}-remote-") as tmp_name:
        remote_skill = download_remote_skill(Path(tmp_name))
        comparison = compare_manifests(manifest(skill_dir), manifest(remote_skill))
    comparison["method"] = "manifest"
    comparison["local_version"] = format_semver(local_version) if local_version else None
    comparison["remote_version"] = format_semver(remote_version) if remote_version else None
    status["skill_update"] = comparison
    return status


def apply_updates(allow_repo_working_copy: bool = False) -> dict[str, object]:
    skill_dir = find_skill_dir()
    assert_skill_dir(skill_dir)
    if inside_git_worktree(skill_dir) and not allow_repo_working_copy:
        return {
            "skill": SKILL_NAME,
            "local_path": str(skill_dir),
            "applied": False,
            "reason": "inside_git_worktree",
            "message": "Refusing to replace a git working copy. Re-run with --allow-repo-working-copy if intentional.",
        }
    status = check_status()
    backup_path = None
    if status["skill_update"]["update_available"]:
        backup_path = str(replace_tree(_download_to_apply_copy(), skill_dir))
    status["applied"] = bool(status["skill_update"]["update_available"])
    status["backup"] = backup_path
    if NPM_PACKAGE and status.get("npm") and status["npm"].get("update_available"):
        status["npm"]["install"] = install_latest_npm()
    return status


# --------------------------------------------------------------------------
# Self test
# --------------------------------------------------------------------------

def self_test() -> int:
    failures: list[str] = []

    # 1. Manifest comparison (historical behavior).
    with tempfile.TemporaryDirectory(prefix=f"{SKILL_NAME}-test-") as tmp_name:
        tmp = Path(tmp_name)
        a = tmp / "a"
        b = tmp / "b"
        a.mkdir()
        b.mkdir()
        (a / "SKILL.md").write_text("one\n", encoding="utf-8")
        (b / "SKILL.md").write_text("two\n", encoding="utf-8")
        diff = compare_manifests(manifest(a), manifest(b))
        if not diff["update_available"] or diff["changed_count"] != 1:
            failures.append("manifest comparison did not detect change")

    # 2. Semver parsing.
    cases = {
        "1.2.3": (1, 2, 3),
        "0.2": (0, 2, 0),
        "version: 1.10.4": (1, 10, 4),
        "1.2.3-beta.1": (1, 2, 3),
        "no version here": None,
    }
    for text, expected in cases.items():
        if parse_semver(text) != expected:
            failures.append(f"parse_semver({text!r}) != {expected}")

    # 3. Frontmatter-scoped version extraction (body mentions must not count).
    with_version = "---\nname: x\ndescription: y\nversion: 1.2.3\n---\n\n# Body\n"
    quoted = '---\nname: x\nversion: "0.3.0"\n---\n'
    body_only = "---\nname: x\n---\n\n正文提到 version: 9.9.9 不应被识别\n"
    no_fm = "# 没有 frontmatter\nversion: 1.0.0\n"
    if extract_version_from_skill_md(with_version) != "1.2.3":
        failures.append("frontmatter version not extracted")
    if extract_version_from_skill_md(quoted) != "0.3.0":
        failures.append("quoted frontmatter version not extracted")
    if extract_version_from_skill_md(body_only) is not None:
        failures.append("body version should not be picked up")
    if extract_version_from_skill_md(no_fm) is not None:
        failures.append("version outside frontmatter should not be picked up")

    # 4. read_local_version: SKILL.md frontmatter mode and VERSION file mode.
    with tempfile.TemporaryDirectory(prefix=f"{SKILL_NAME}-test-") as tmp_name:
        tmp = Path(tmp_name)
        skill = tmp / SKILL_NAME
        skill.mkdir()
        (skill / "SKILL.md").write_text(with_version, encoding="utf-8")
        got = read_local_version(skill)
        if VERSION_FILE:
            if got is not None:
                failures.append("VERSION_FILE mode should ignore SKILL.md")
            (skill / VERSION_FILE).write_text("2.0.1\n", encoding="utf-8")
            if read_local_version(skill) != (2, 0, 1):
                failures.append("VERSION file not read")
        else:
            if got != (1, 2, 3):
                failures.append("local version from SKILL.md not read")

    # 5. Version decision semantics: newer → update; equal/local_ahead → no update.
    if version_relation((1, 0, 0), (1, 0, 1)) != "newer":
        failures.append("newer remote not detected")
    if version_relation((1, 0, 0), (1, 0, 0)) != "equal":
        failures.append("equal remote not detected")
    if version_relation((1, 2, 0), (1, 0, 9)) != "local_ahead":
        failures.append("local_ahead not detected")

    if failures:
        for failure in failures:
            print(f"self-test failed: {failure}", file=sys.stderr)
        return 1
    print("self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Check and update the {SKILL_NAME} skill.")
    parser.add_argument("--check", action="store_true", help="Check for available updates and print JSON status.")
    parser.add_argument("--apply", action="store_true", help="Apply available skill updates after creating a backup.")
    parser.add_argument("--allow-repo-working-copy", action="store_true", help="Allow replacing a skill folder inside a git working copy.")
    parser.add_argument("--self-test", action="store_true", help="Run local updater self-tests.")
    parser.add_argument("--version", action="store_true", help="Print the local skill version.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.version:
        skill_dir = find_skill_dir()
        assert_skill_dir(skill_dir)
        local_version = read_local_version(skill_dir)
        print(json.dumps({
            "skill": SKILL_NAME,
            "version": format_semver(local_version) if local_version else None,
        }, ensure_ascii=False))
        return 0
    if args.apply:
        print(json.dumps(apply_updates(args.allow_repo_working_copy), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(check_status(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
