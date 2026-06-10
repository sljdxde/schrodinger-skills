# Global Agent Instructions for Windows

## Environment

I am working on native Windows, usually in PowerShell.

Do not assume WSL, Linux, macOS, or bash.

## Shell Rules

- Prefer PowerShell-compatible commands.
- Avoid bash-only commands.
- Do not use `rm -rf`, `grep`, `sed`, `awk`, `xargs`, `export`, `source`, `chmod`, `sudo`, `/tmp`, `/dev/null`.
- Use Windows-compatible path handling.
- Prefer Python/Node scripts for complex file operations.
- Prefer existing project scripts over ad-hoc shell commands.
- If a command fails, check for shell compatibility before retrying.

## Path Rules

- Use relative paths where practical.
- Quote paths with spaces.
- Use `.\` for local paths in PowerShell.
- In generated code, use cross-platform path APIs (`pathlib`, `path.join`).

## Project Rules

- Before running setup/build/test, inspect project files.
- Use lockfile to infer package manager.
- Do not globally install dependencies unless explicitly requested.
- Do not recommend WSL unless Windows-native execution is impractical.
