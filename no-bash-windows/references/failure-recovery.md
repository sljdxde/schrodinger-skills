# Failure Recovery Guide

## Error: Command Not Found

Examples:

```
grep: The term 'grep' is not recognized
sed: The term 'sed' is not recognized
rm: cannot find...
source: The term 'source' is not recognized
```

Action:

1. Identify the bash-only command.
2. Convert using `command-map.md`.
3. Retry with PowerShell-compatible command.

## Error: Environment Variable Syntax

Example:

```
NODE_ENV=production : The term 'NODE_ENV=production' is not recognized
```

Action:

```powershell
$env:NODE_ENV = "production"
npm run build
```

Or use `cross-env` inside npm scripts.

## Error: Script Execution Policy

Example:

```
running scripts is disabled on this system
```

Action:

Prefer direct interpreter execution:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Only suggest this if user wants activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Do not change machine-wide policy automatically.

## Error: Path Not Found

Action:

1. Check current directory with `Get-Location`.
2. List files with `Get-ChildItem`.
3. Use quoted relative paths.
4. Avoid Linux paths (`/home`, `/tmp`).

## Error: Native Dependency Compilation

Action:

1. Identify the package.
2. Check if prebuilt binary exists.
3. Use documented Windows install steps.
4. Do not assume Linux package managers.
5. If Windows unsupported, state that clearly.

## Error: Permission Denied

Action:

1. Check if file is read-only: `(Get-Item .\file).IsReadOnly`
2. Remove read-only flag: `Set-ItemProperty .\file -Name IsReadOnly -Value $false`
3. For locked files, check if another process holds it.
4. Do NOT suggest `sudo` or `chmod`.

## Error: Path Separator Issues

Example: Code using `/` in paths fails on Windows.

Action:

1. In generated code, use `path.join` (Node.js) or `pathlib` (Python).
2. In PowerShell, use `Join-Path` or backslash `\`.
3. For mixed environments, normalize with `[IO.Path]::Combine()`.
