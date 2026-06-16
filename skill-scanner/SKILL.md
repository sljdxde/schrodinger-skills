---
name: Skill Scanner
description: Use this skill when scanning, discovering, or diagnosing AI agent skills across multiple agent ecosystems (Claude Code, Codex, Cursor, OpenCode, etc.). Provides automatic recursive discovery of skills in plugins/cache, plugins/marketplaces, and other nested directories.
source: https://github.com/sljdxde/agent-skill-doctor.git
ref: v0.2.0
---

# Skill Scanner

自动发现和扫描 AI Agent 技能的通用模块，支持 Claude Code、Codex、Cursor、OpenCode 等多种 Agent 生态。

## 核心能力

- **自动发现**：递归扫描 Agent 目录下的 `skills/`、`skills-core/`、`plugins/` 子目录
- **多 Agent 支持**：内置 12 种 Agent 根目录配置
- **智能过滤**：自动跳过 `sessions`、`backups`、`node_modules` 等无关目录
- **元数据解析**：解析 SKILL.md 的 YAML frontmatter，提取 name、description、source 等字段

## 何时触发

当用户提到以下场景时，使用此 skill：
- 扫描或发现本地安装的 skills
- 诊断 skill 问题（重复、冲突、僵尸 skill）
- 列出某个 Agent 的所有 skills
- 检查 plugins/cache 目录下的 skills

## 使用方式

### 作为 CLI 工具

```bash
# 安装
npm install -g agent-skill-doctor

# 扫描所有 skills
agent-skill-doctor scan

# 完整诊断
agent-skill-doctor diagnose

# 生成 HTML 报告
agent-skill-doctor report --format html
```

### 作为 Library API

```javascript
const { scanRoots, discoverSkillDirs, findSkillCandidates } = require('agent-skill-doctor');

// 自动发现所有 skill 目录
const dirs = discoverSkillDirs();
console.log('Found directories:', dirs);

// 扫描指定目录
const skills = scanRoots(dirs, { maxDepth: 6 });
console.log('Found skills:', skills.length);

// 自定义根目录扫描
const customSkills = scanRoots(['~/.claude/plugins', '~/.codex/plugins']);
```

## 支持的 Agent 目录

| Agent | 全局目录 | 项目目录 |
|-------|---------|---------|
| Claude Code | `~/.claude/` | `.claude/` |
| Codex | `~/.codex/` | `.codex/` |
| Cursor | `~/.cursor/` | `.cursor/` |
| OpenCode | `~/.opencode/` | `.opencode/` |
| Windsurf | `~/.windsurf/` | `.windsurf/` |
| Agents | `~/.agents/` | `.agents/` |

每个 Agent 目录下会自动扫描：
- `skills/` - 主技能目录
- `skills-core/` - 核心技能目录
- `plugins/` - 插件目录（含 cache、marketplace）

## SKILL.md 格式

```markdown
---
name: My Skill
description: Use this skill when you need to... (触发条件 + 功能描述)
source: https://github.com/user/repo.git
ref: v1.0.0
tags: utility, automation
---

# My Skill

技能的详细说明和使用指令...
```

### Frontmatter 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | 技能显示名称 |
| `description` | ✅ | 描述（含触发条件和功能） |
| `source` | ❌ | Git 仓库地址 |
| `ref` | ❌ | Git tag/branch |
| `tags` | ❌ | 标签（逗号分隔） |
| `pinned` | ❌ | 是否固定（防止被标记为僵尸） |

## 诊断类型

扫描完成后可进行 7 种诊断：

1. **risk** - 危险模式检测（rm -rf、curl、.env 访问等）
2. **conflict** - 技能冲突检测（如 npm vs pnpm）
3. **duplicate** - 重复技能检测
4. **version_drift** - 版本漂移检测
5. **zombie** - 僵尸技能检测（长期未使用）
6. **description_quality** - 描述质量检查
7. **scan_warning** - 结构问题（缺少 SKILL.md 等）

## 相关资源

- [Agent Skills 标准](https://agentskills.io)
- [agent-skill-doctor](https://github.com/sljdxde/agent-skill-doctor) - 诊断工具源码
- [API 参考](./references/api.md) - 完整 API 文档
