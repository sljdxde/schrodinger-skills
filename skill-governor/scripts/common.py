#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


def default_agents_home() -> Path:
    return Path(os.environ.get("AGENTS_HOME", Path.home() / ".agents"))
