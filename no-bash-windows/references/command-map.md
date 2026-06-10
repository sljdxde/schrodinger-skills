# Bash to PowerShell / Cross-platform Command Map

## File Operations

| Bash | PowerShell |
|---|---|
| `ls -la` | `Get-ChildItem -Force` |
| `pwd` | `Get-Location` |
| `cat file` | `Get-Content .\file` |
| `head -n 20 file` | `Get-Content .\file -TotalCount 20` |
| `tail -n 20 file` | `Get-Content .\file -Tail 20` |
| `touch file` | `New-Item -ItemType File -Path .\file -Force` |
| `mkdir -p dir` | `New-Item -ItemType Directory -Path .\dir -Force` |
| `rm file` | `Remove-Item .\file` |
| `rm -rf dir` | `Remove-Item -Recurse -Force .\dir` |
| `cp a b` | `Copy-Item .\a .\b` |
| `cp -r a b` | `Copy-Item -Recurse .\a .\b` |
| `mv a b` | `Move-Item .\a .\b` |
| `ln -s target link` | `New-Item -ItemType SymbolicLink -Path .\link -Target .\target` |

## Search

| Bash | PowerShell |
|---|---|
| `grep "foo" file` | `Select-String -Path .\file -Pattern "foo"` |
| `grep -R "foo" .` | `Select-String -Path .\* -Pattern "foo" -Recurse` |
| `grep -r "foo" src/` | `Select-String -Path .\src\* -Pattern "foo" -Recurse` |
| `grep -i "foo" file` | `Select-String -Path .\file -Pattern "foo" -CaseSensitive:$false` |
| `grep -l "foo" *` | `Select-String -Path .\* -Pattern "foo" -List \| Select-Object -ExpandProperty Path` |
| `find . -name "*.ts"` | `Get-ChildItem -Recurse -Filter *.ts` |
| `find . -type f` | `Get-ChildItem -Recurse -File` |
| `find . -type d` | `Get-ChildItem -Recurse -Directory` |
| `find . -name "*.ts" -exec grep "foo" {} \;` | `Get-ChildItem -Recurse -Filter *.ts \| Select-String -Pattern "foo"` |

## Text Processing

| Bash | PowerShell |
|---|---|
| `sed 's/foo/bar/g' file` | `(Get-Content .\file) -replace 'foo', 'bar' \| Set-Content .\file` |
| `sed -i 's/foo/bar/g' file` | `(Get-Content .\file) -replace 'foo', 'bar' \| Set-Content .\file` |
| `awk '{print $1}' file` | `Get-Content .\file \| ForEach-Object { $_.Split()[0] }` |
| `sort file` | `Get-Content .\file \| Sort-Object` |
| `uniq file` | `Get-Content .\file \| Select-Object -Unique` |
| `wc -l file` | `(Get-Content .\file).Count` |
| `tr '[:upper:]' '[:lower:]'` | `$str.ToLower()` |

## Environment Variables

| Bash | PowerShell |
|---|---|
| `export A=B` | `$env:A = "B"` |
| `unset A` | `Remove-Item Env:A` |
| `A=B npm test` | `$env:A = "B"; npm test` |
| `echo $A` | `$env:A` |
| `printenv` | `Get-ChildItem Env:` |

## Redirection

| Bash | PowerShell |
|---|---|
| `command > /dev/null` | `command *> $null` |
| `command 2>/dev/null` | `command 2>$null` |
| `command &> file` | `command *> .\file` |
| `command && next` | `command; if ($LASTEXITCODE -eq 0) { next }` |
| `command \|\| fallback` | `command; if ($LASTEXITCODE -ne 0) { fallback }` |

## Python venv

| Bash | PowerShell |
|---|---|
| `python3 -m venv .venv` | `python -m venv .venv` |
| `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| `source .venv/bin/activate.fish` | `.\.venv\Scripts\Activate.ps1` |
| `venv/bin/python script.py` | `.\.venv\Scripts\python.exe script.py` |
| `venv/bin/pip install req` | `.\.venv\Scripts\python.exe -m pip install req` |
| `deactivate` | `deactivate` |

## System

| Bash | PowerShell |
|---|---|
| `which node` | `Get-Command node` |
| `uname -a` | `[System.Environment]::OSVersion.VersionString` |
| `env` | `Get-ChildItem Env:` |
| `chmod +x file` | (not needed on Windows) |
| `ps aux` | `Get-Process` |
| `kill -9 PID` | `Stop-Process -Id PID -Force` |
| `df -h` | `Get-PSDrive -PSProvider FileSystem` |
| `du -sh dir` | `Get-ChildItem .\dir -Recurse \| Measure-Object -Property Length -Sum` |

## Prefer Cross-platform Scripts for Complex Cases

Avoid translating long pipelines directly. Instead of:

```bash
find src -name "*.ts" | xargs sed -i 's/foo/bar/g'
```

Write a Python or Node.js script using `pathlib` or `fs`.
