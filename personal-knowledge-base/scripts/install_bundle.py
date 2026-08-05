#!/usr/bin/env python3
"""Install the two skills in this bundle into an Agent skill directory."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


AGENT_ROOTS = {
    "codex": Path.home() / ".codex" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "cursor": Path.home() / ".cursor" / "skills",
    "opencode": Path.home() / ".opencode" / "skills",
}
COMPONENTS = ("ob-llm-wiki", "ob")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the personal knowledge-base skill bundle.")
    parser.add_argument("--agent", choices=sorted(AGENT_ROOTS), default="codex")
    parser.add_argument("--target-root", type=Path, help="Override the Agent skill directory.")
    parser.add_argument("--replace", action="store_true", help="Back up and replace existing component directories.")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without changing files.")
    return parser.parse_args()


def backup_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(tempfile.gettempdir()) / "personal-knowledge-base-backups" / stamp


def main() -> int:
    args = parse_args()
    bundle_root = Path(__file__).resolve().parents[1]
    target_root = (args.target_root or AGENT_ROOTS[args.agent]).expanduser().resolve()
    destinations = [target_root / name for name in COMPONENTS]
    existing = [path for path in destinations if path.exists()]

    if existing and not args.replace:
        names = ", ".join(str(path) for path in existing)
        raise SystemExit(f"Existing components found: {names}. Re-run with --replace to back them up and replace them.")

    backup_root = backup_path() if existing and args.replace else None
    print(f"source: {bundle_root}")
    print(f"target: {target_root}")
    if backup_root:
        print(f"backup: {backup_root}")

    if args.dry_run:
        for name in COMPONENTS:
            print(f"would install: {name}")
        return 0

    target_root.mkdir(parents=True, exist_ok=True)
    if backup_root:
        backup_root.mkdir(parents=True, exist_ok=True)
        for path in existing:
            shutil.move(str(path), str(backup_root / path.name))

    for name in COMPONENTS:
        shutil.copytree(bundle_root / name, target_root / name)
        print(f"installed: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
