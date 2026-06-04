#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path


def default_agents_home() -> Path:
    return Path(os.environ.get("AGENTS_HOME", Path.home() / ".agents"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the latest Skill Governor report.")
    parser.add_argument(
        "--report",
        type=Path,
        default=default_agents_home() / "skill-registry-report.md",
    )
    args = parser.parse_args()
    if not args.report.exists():
        raise SystemExit(f"Report not found: {args.report}. Run reconcile first.")
    print(args.report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
