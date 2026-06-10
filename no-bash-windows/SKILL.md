---
name: no-bash-windows
description: >-
  Activate when working on native Windows (non-WSL) to avoid bash-only commands.
  Use this skill when the shell is PowerShell or cmd.exe, the OS is Windows, or
  when a command fails due to bash/Linux syntax. Covers: Windows, PowerShell,
  bash compatibility, WSL avoidance, grep, sed, awk, rm -rf, export, source,
  chmod, path separator, script execution policy, npm scripts on Windows,
  Python venv on Windows, xargs, /dev/null, /tmp.
compatibility: Windows (non-WSL). Assumes PowerShell 7+ or Windows PowerShell.
---

# No Bash Windows

## Purpose

Avoid bash-only commands on native Windows. Prefer PowerShell, Python, Node.js, and npm scripts. Do not assume WSL is available.

## When to Use

- Shell is PowerShell or cmd.exe
- OS is Windows without WSL
- A command fails because it uses bash/Linux syntax
- Running project setup, tests, build, lint, or scripts on Windows

## Core Rules

1. Prefer PowerShell syntax over bash syntax.
2. Prefer project scripts (npm/pnpm/yarn) over ad-hoc shell commands.
3. Prefer cross-platform Node.js or Python scripts for complex file/text operations.
4. Never use bash-only commands unless a bash shell is explicitly available.
5. Do not use `rm -rf`, `grep`, `sed`, `awk`, `xargs`, `export`, `source`, `chmod`, `/tmp`, `/dev/null`, or `VAR=value command` in PowerShell.
6. Use Windows-compatible path handling (backslash, relative `.\`).
7. If a command fails, diagnose shell compatibility before retrying.
8. For destructive operations, use safer PowerShell equivalents.

## Execution Preference Order

1. Existing project command (npm scripts, pnpm, yarn, documented README command)
2. Native PowerShell command
3. Cross-platform Python script
4. Cross-platform Node.js script
5. cmd.exe only when needed
6. Git Bash only if explicitly installed and user accepts
7. WSL only if explicitly allowed by user

## Common Replacements

| Bash | PowerShell |
|---|---|
| `grep -R "foo" .` | `Select-String -Path .\* -Pattern "foo" -Recurse` |
| `rm -rf dist` | `Remove-Item -Recurse -Force .\dist` |
| `export NODE_ENV=production` | `$env:NODE_ENV = "production"` |
| `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| `cat file.txt` | `Get-Content .\file.txt` |
| `touch file.txt` | `New-Item -ItemType File -Path .\file.txt -Force` |
| `/tmp/foo` | `$env:TEMP\foo` |
| `command > /dev/null` | `command *> $null` |
| `mkdir -p dir` | `New-Item -ItemType Directory -Path .\dir -Force` |
| `cp -r a b` | `Copy-Item -Recurse .\a .\b` |

Full mapping: see `references/command-map.md`.

## Path Rules

- Prefer relative paths like `.\src\main.ts`.
- In code, use `pathlib` (Python) or `path.join` / `path.resolve` (Node.js).
- Do not hardcode `/home`, `/tmp`, `/var`, `/dev/null`.
- Quote paths that may contain spaces.
- Do not assume path case sensitivity.
- Use `Join-Path` for constructed paths in PowerShell.

## Environment Variables

PowerShell syntax:

```powershell
$env:NODE_ENV = "production"
npm run build
```

Do NOT use:

```bash
NODE_ENV=production npm run build
export NODE_ENV=production
```

For npm scripts, prefer `cross-env`:

```json
{
  "scripts": {
    "build": "cross-env NODE_ENV=production vite build"
  }
}
```

## Python Virtual Environment

Prefer direct interpreter path:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
```

If activation is needed:

```powershell
.\.venv\Scripts\Activate.ps1
```

If execution policy blocks activation, prefer direct interpreter invocation over changing global policy.

## Failure Recovery

When a command fails:

1. Read the error message.
2. Determine if caused by: bash syntax in PowerShell, missing command, path separator issue, env var syntax, execution policy, missing dependency, or native compilation issue.
3. If shell compatibility issue: convert using `references/command-map.md`, explain briefly, retry once.
4. If dependency issue: check package manager files, use documented package manager.
5. If truly Linux-only: state clearly, suggest Docker/remote Linux/CI as fallback.

See `references/failure-recovery.md` for detailed diagnosis.

## Project Inspection

Before running setup/build/test in an unknown repo, check for:

- `package.json`, lockfiles (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`)
- `pyproject.toml`, `requirements.txt`
- `Makefile`, `.github/workflows`
- Existing `.ps1` scripts
- `README.md` for documented commands

See `references/project-patterns.md` for per-ecosystem guidance.

## Do NOT

- Blindly run bash snippets from README
- Use `chmod +x`, `sudo`, `apt`, `yum`, `brew`
- Assume `make` exists
- Create `.sh` scripts as primary solution
- Recommend WSL unless user explicitly allows it or project is Linux-only
