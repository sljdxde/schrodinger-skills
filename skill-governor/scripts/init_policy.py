#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.common import default_agents_home


DEFAULT_POLICY = """version: 1
policies:
  newStandaloneSkill: shadow
  newPluginSkill: dependency-only
  keepManualPrimary: true
  requireReviewForBroadDescriptions: true
capabilities:
  document.pdf:
    primary: pdf
  document.presentation:
    primary: slides
  document.spreadsheet:
    primary: spreadsheet
  document.word:
    primary: word-document-processor
  web.browsing:
    primary: web-access
  git.workflow:
    primary: git-master
  development.workflow:
    primary: systematic-debugging
  meta.skill-governance:
    primary: skill-governor
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a Skill Governor policy.")
    parser.add_argument(
        "--policy",
        type=Path,
        default=default_agents_home() / "skill-policy.yaml",
        help="Path to the user-editable policy file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing policy file.",
    )
    args = parser.parse_args()
    if args.policy.exists() and not args.force:
        print(f"Policy already exists: {args.policy}")
        return
    args.policy.parent.mkdir(parents=True, exist_ok=True)
    args.policy.write_text(DEFAULT_POLICY, encoding="utf-8")
    print(f"Policy initialized: {args.policy}")


if __name__ == "__main__":
    main()
