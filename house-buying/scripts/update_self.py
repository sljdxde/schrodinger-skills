#!/usr/bin/env python3
"""Self-update helper for this skill.

Checks the GitHub copy of this skill folder and can replace the local copy after
creating a recoverable backup. No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SKILL_NAME = "house-buying"
REPO_OWNER = "sljdxde"
REPO_NAME = "schrodinger-skills"
REPO_BRANCH = "main"
NPM_PACKAGE = None
NPM_COMMAND = None

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}


TEXT_EXTENSIONS = {".md", ".py", ".yaml", ".yml", ".json", ".txt"}


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


def find_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def assert_skill_dir(path: Path) -> None:
    if path.name != SKILL_NAME:
        raise RuntimeError(f"Refusing to update unexpected skill directory: {path}")
    if not (path / "SKILL.md").is_file():
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


def check_status() -> tuple[dict[str, object], Path | None]:
    skill_dir = find_skill_dir()
    assert_skill_dir(skill_dir)
    with tempfile.TemporaryDirectory(prefix=f"{SKILL_NAME}-remote-") as tmp_name:
        remote_skill = download_remote_skill(Path(tmp_name))
        comparison = compare_manifests(manifest(skill_dir), manifest(remote_skill))
        status: dict[str, object] = {
            "skill": SKILL_NAME,
            "local_path": str(skill_dir),
            "source": f"https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/{REPO_BRANCH}/{SKILL_NAME}",
            "skill_update": comparison,
            "npm": None,
        }
        copy_for_apply = Path(tempfile.mkdtemp(prefix=f"{SKILL_NAME}-apply-")) / SKILL_NAME
        shutil.copytree(remote_skill, copy_for_apply)
        return status, copy_for_apply


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
    status, remote_copy = check_status()
    backup_path = None
    if status["skill_update"]["update_available"]:
        backup_path = str(replace_tree(remote_copy, skill_dir))
    status["applied"] = bool(status["skill_update"]["update_available"])
    status["backup"] = backup_path
    return status


def self_test() -> int:
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
            print("self-test failed: manifest comparison did not detect change", file=sys.stderr)
            return 1
    print("self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Check and update the {SKILL_NAME} skill.")
    parser.add_argument("--check", action="store_true", help="Check for available updates and print JSON status.")
    parser.add_argument("--apply", action="store_true", help="Apply available skill updates after creating a backup.")
    parser.add_argument("--allow-repo-working-copy", action="store_true", help="Allow replacing a skill folder inside a git working copy.")
    parser.add_argument("--self-test", action="store_true", help="Run local updater self-tests.")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.apply:
        print(json.dumps(apply_updates(args.allow_repo_working_copy), ensure_ascii=False, indent=2))
        return 0
    status, _ = check_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
