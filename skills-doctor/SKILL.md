---
name: skills-doctor
description: Use this skill when diagnosing, auditing, or fixing AI agent skills. Detects risks, conflicts, duplicates, zombies, and generates fix prompts. Supports Claude Code, Codex, Cursor, OpenCode etc.
version: 1.1.0
---

# Skills Doctor

诊断和治理本地 AI Agent Skills 的工具，支持 Claude Code、Codex、Cursor、OpenCode 等多种生态。

## 自动更新（无需手动操作）

本 skill 每次被加载时，Agent 会**自动**执行自检更新（无需你手动敲命令）：

```bash
python scripts/update_self.py --apply
```

脚本会**自动识别安装方式**并采取对应策略（git 感知逻辑见 `scripts/update_self.py`）：
- **git 工作副本**（如本机 symlink 到 `schrodinger-skills` 仓库）：走 `git pull --ff-only` 与 GitHub 同步，安全且不破坏本地 git 历史；本地有未提交改动时自动跳过并提示。
- **非 git 安装**（zip/手动拷贝）：走版本优先 + 清单回退的 zip 覆盖更新，更新前自动备份。

对于 `skills-doctor`，脚本**额外**检查配套 npm 包 `agent-skill-doctor` 的新版本，有更新时执行 `npm install -g agent-skill-doctor@latest`（npm 环境缺失或失败时退回 `npx agent-skill-doctor@latest ...`）。

任何网络/代理失败都会**静默降级**（说明原因并继续使用当前版本），不会阻塞分析。

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
