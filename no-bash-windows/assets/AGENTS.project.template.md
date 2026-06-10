# Project Agent Instructions for Windows

## Environment

This project runs on native Windows with PowerShell.

Do not use bash-only commands. Do not assume WSL is available.

## Build & Test

<!-- Update these commands to match your project -->

```powershell
npm run build
npm run test
npm run lint
```

## Package Manager

<!-- Uncomment and update the one your project uses -->

<!-- pnpm -->
<!-- yarn -->
<!-- npm -->

## Shell Rules

- Use PowerShell syntax for all shell commands.
- Use `cross-env` for cross-platform env vars in npm scripts.
- Use `pathlib` / `path.join` for path construction in code.
- Prefer direct interpreter invocation over `.ps1` activation when execution policy is restrictive.

## Path Rules

- Use relative paths.
- Quote paths with spaces.
- Use `.\` prefix for local paths in PowerShell.
- Use `Join-Path` for dynamic path construction.
