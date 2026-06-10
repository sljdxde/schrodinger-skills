# Project Patterns

## Node.js Project

Check for:

```powershell
Test-Path .\package.json
```

Prefer:

```powershell
npm run test
npm run build
npm run lint
```

If env vars are needed, use `cross-env` or PowerShell `$env:` syntax.

Avoid editing npm scripts into bash-only commands.

## Python Project

Check for:

```powershell
Test-Path .\pyproject.toml
Test-Path .\requirements.txt
Test-Path .\.venv
```

Prefer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
```

## Java / Maven / Gradle

Prefer Windows wrapper files:

```powershell
.\mvnw.cmd test
.\gradlew.bat test
```

If wrappers exist, use them instead of `mvn` or `gradle` directly.

## Go

```powershell
go test ./...
go run .
```

## Rust

```powershell
cargo test
cargo run
```

## Docker

Only use Docker if:

- Project already documents it
- Dependencies are Linux-only
- Windows-native execution is impractical

Do not suggest WSL first.

## Monorepo

Check root for workspace configuration:

```powershell
Test-Path .\pnpm-workspace.yaml
Test-Path .\lerna.json
Test-Path .\nx.json
```

Use the workspace tool's native commands:

```powershell
pnpm --filter <package> run test
npx nx run <project>:test
```

## Makefile Projects

Do not assume `make` exists. If Makefile is the only documented way:

1. Read the Makefile
2. Identify the target's actual commands
3. Run those commands directly in PowerShell

Example: if `make test` runs `pytest tests/`, use:

```powershell
python -m pytest tests/
```
