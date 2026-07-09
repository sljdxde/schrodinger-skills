---
name: skills-doctor
description: Use this skill when diagnosing, auditing, or fixing AI agent skills. Detects risks, conflicts, duplicates, zombies, and generates fix prompts. Supports Claude Code, Codex, Cursor, OpenCode etc.
---

# Skills Doctor

诊断和治理本地 AI Agent Skills 的工具，支持 Claude Code、Codex、Cursor、OpenCode 等多种生态。

## 使用前自检更新

每次使用本 skill 前，先运行：

```bash
python scripts/update_self.py --apply
```

该脚本会同时检查两类更新：
- `skills-doctor` skill 目录本身是否有 GitHub 更新；有更新时先备份本地 skill，再自动同步最新文件。
- `agent-skill-doctor` npm 包是否有新版本；有新版本时执行 `npm install -g agent-skill-doctor@latest`。

若脚本显示 skill 已更新，重新读取当前 `SKILL.md` 后再继续。若网络、Python 或 npm 环境导致更新失败，说明失败原因；npm 更新失败时可退回使用 `npx agent-skill-doctor@latest ...`。

## 何时触发

当用户提到以下场景时，使用此 skill：
- 诊断或审计本地 skills
- 检测危险模式、冲突、重复、僵尸 skill
- 生成 skill 修复建议
- 生成诊断报告

## 安装

```bash
npm install -g agent-skill-doctor
```

或直接使用（无需安装）：

```bash
npx agent-skill-doctor help
```

## 使用方式

### 完整诊断

```bash
# 中文诊断
agent-skill-doctor diagnose --lang zh

# JSON 输出
agent-skill-doctor diagnose --json

# 自定义扫描目录
agent-skill-doctor diagnose --root ./my-skills --lang zh
```

### 定向查询

```bash
agent-skill-doctor risks --json
agent-skill-doctor conflicts --json
agent-skill-doctor duplicates --json
agent-skill-doctor zombies --json
```

### 生成报告

```bash
# Markdown 报告
agent-skill-doctor report --format md --lang zh

# HTML 报告
agent-skill-doctor report --format html --lang en --output ./reports/report.html

# JSON 报告
agent-skill-doctor report --format json
```

### 生成修复提示

```bash
# 通用修复提示
agent-skill-doctor fix --lang zh

# 按类型和严重程度筛选
agent-skill-doctor fix --type risk --severity high --lang zh
agent-skill-doctor fix --type duplicate --lang zh
```

### CI 集成

```bash
# 在 CI 中失败于高严重程度问题
agent-skill-doctor diagnose --ci --fail-on high
```

## 诊断类型

1. **risk** - 危险模式检测（rm -rf、curl、.env 访问、child_process 等）
2. **conflict** - 技能冲突检测（如 npm vs pnpm 指令矛盾）
3. **duplicate** - 重复技能检测（完全相同、同源、同名不同内容）
4. **version_drift** - 版本漂移检测（同一 skill 多处存在且版本不同）
5. **zombie** - 僵尸技能检测（长期未使用，评分 0.0-1.0）
6. **description_quality** - 描述质量检查（缺少触发条件、I/O 说明等）
7. **scan_warning** - 结构问题（缺少 SKILL.md、frontmatter 格式错误）

## 默认扫描路径

```
~/.agent/skills
~/.agents/skills
~/.agents/skills-core
~/.codex/skills
~/.claude/skills
~/.cursor/skills
~/.opencode/skills
```

## 推荐用法

向 AI Agent 发送指令：

> "请使用 agent-skill-doctor 诊断我的本地 Agent Skills" — 然后运行 `diagnose`，生成报告，阅读结果，输出修复计划。

## 相关资源

- [agent-skill-doctor](https://github.com/sljdxde/agent-skill-doctor) - 源码仓库
