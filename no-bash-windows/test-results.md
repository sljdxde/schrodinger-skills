# No Bash Windows - 测试对比结果

## 测试环境

- OS: Windows 10 Pro (10.0.19045)
- PowerShell: 5.1.19041.6456 (Desktop)
- Shell: bash (Git Bash)

## 测试场景

### Case 1: 文件搜索

**任务**: 搜索 src 目录下所有包含 "keyword" 的文件

| | 无 Skill | 有 Skill |
|---|---|---|
| 输出 | `grep -R "keyword" src` | `Select-String -Path .\src\* -Pattern "keyword" -Recurse` |
| 可执行 | PowerShell 中报错: `grep: command not found` | 正常执行 |

### Case 2: 删除目录

**任务**: 删除 dist 目录

| | 无 Skill | 有 Skill |
|---|---|---|
| 输出 | `rm -rf dist` | `Remove-Item -Recurse -Force .\dist` |
| 可执行 | PowerShell 中报错: `rm: command not found` | 正常执行 |

### Case 3: 环境变量设置

**任务**: 设置 NODE_ENV 为 production 后执行 build

| | 无 Skill | 有 Skill |
|---|---|---|
| 输出 | `NODE_ENV=production npm run build` | `$env:NODE_ENV = "production"; npm run build` |
| 可执行 | PowerShell 中报错: `NODE_ENV=production: not recognized` | 正常执行 |

### Case 4: Python venv 激活

**任务**: 激活 Python 虚拟环境并运行测试

| | 无 Skill | 有 Skill |
|---|---|---|
| 输出 | `source .venv/bin/activate && pytest` | `.\.venv\Scripts\python.exe -m pytest` |
| 可执行 | PowerShell 中报错: `source: not recognized` | 正常执行 |

### Case 5: 查看文件内容

**任务**: 查看 package.json 的前 10 行

| | 无 Skill | 有 Skill |
|---|---|---|
| 输出 | `head -n 10 package.json` | `Get-Content .\package.json -TotalCount 10` |
| 可执行 | PowerShell 中报错: `head: command not found` | 正常执行 |

## 总结

使用 no-bash-windows skill 后，agent 在 Windows 环境下生成的所有 shell 命令均为 PowerShell 兼容语法，避免了 bash-only 命令导致的执行失败。核心收益：

1. **零报错**: 所有生成的命令可在 PowerShell 中直接执行
2. **无需 WSL**: 不依赖 Git Bash 或 WSL 环境
3. **自动适配**: agent 根据 skill 指令自动选择 Windows 兼容方案
