# Windows Shell Policy

## Default Shell

Assume PowerShell 7+ or Windows PowerShell unless explicitly told otherwise.

## Safe Command Style

Use `$ErrorActionPreference = "Stop"` for scripts.

Quote paths with spaces:

```powershell
Get-Content ".\path with spaces\file.txt"
```

Use explicit executables:

```powershell
python -m pytest
node .\scripts\build.js
npm run test
```

## Avoid Shell-specific Tricks

Do NOT use:

- Bash brace expansion (`{a,b,c}`)
- Process substitution (`<(command)`)
- Here-doc syntax (`<<EOF`)
- `$(...)` unless writing PowerShell-specific syntax
- Single-line env var assignment before command (`FOO=bar cmd`)
- Unix path assumptions (`/home`, `/tmp`, `/var`)

## Package Managers

Detect lockfile to choose package manager:

1. `pnpm-lock.yaml` -> use `pnpm`
2. `yarn.lock` -> use `yarn`
3. `package-lock.json` -> use `npm`
4. No lockfile -> inspect `README.md` / `package.json`

Do not switch package managers without reason.

## Makefile Handling

Do not assume `make` is installed on Windows.

If a project only documents `make test`, inspect the `Makefile` and translate the target into native commands where practical.

## Script Creation Policy

For helper scripts:

- `.ps1` for shell tasks
- `.js` / `.mjs` for Node projects
- `.py` for Python-heavy text/file operations
- Avoid `.sh` unless project already uses Git Bash and user accepts it

## Execution Policy

If script execution policy blocks `.ps1` scripts:

1. Prefer direct interpreter invocation as workaround
2. Only suggest `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` if user wants activation
3. Never change machine-wide policy automatically
