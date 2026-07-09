# Skill Scanner API Reference

## 安装

```bash
npm install agent-skill-doctor
```

## 更新

本仓库中的 `skills-doctor` skill 使用前应先运行：

```bash
python scripts/update_self.py --apply
```

该命令会检查 skill 本身是否有 GitHub 更新，并检查 `agent-skill-doctor` npm 包是否有新版本。若只想手动更新 npm 包，可运行：

```bash
npm install -g agent-skill-doctor@latest
```

## 导入

```javascript
// CommonJS
const { scanRoots, discoverSkillDirs } = require('agent-skill-doctor');

// ES Module (需要 package.json 中 type: module)
import { scanRoots, discoverSkillDirs } from 'agent-skill-doctor';
```

## 核心 API

### `discoverSkillDirs(options?)`

自动发现所有 Agent 的 skill 目录。

**参数：**
- `options.cwd` (string, 可选) - 项目目录，默认 `process.cwd()`
- `options.extraRoots` (string[], 可选) - 额外的扫描根目录

**返回值：** `string[]` - 存在的目录路径列表

```javascript
const dirs = discoverSkillDirs();
// => ['C:/Users/me/.claude/skills', 'C:/Users/.claude/plugins', ...]

// 添加自定义目录
const dirs = discoverSkillDirs({
  extraRoots: ['~/my-skills', './local-skills']
});
```

### `scanRoots(roots, options?)`

扫描指定根目录，返回解析后的 skill 列表。

**参数：**
- `roots` (string[]) - 根目录路径列表
- `options.maxDepth` (number, 可选) - 最大递归深度，默认 6

**返回值：** `Skill[]` - skill 对象数组

```javascript
const skills = scanRoots(['~/.claude/plugins', '~/.codex/plugins']);
console.log(`Found ${skills.length} skills`);

skills.forEach(s => {
  console.log(`${s.name} (${s.agent}) - ${s.description}`);
});
```

### `findSkillCandidates(dir, root, depth, maxDepth)`

递归查找目录中的 skill 候选。

**参数：**
- `dir` (string) - 当前扫描目录
- `root` (string) - 根目录
- `depth` (number) - 当前深度
- `maxDepth` (number) - 最大深度

**返回值：** `Candidate[]` - 候选列表

```javascript
const candidates = findSkillCandidates('~/.claude', '~/.claude', 0, 6);
candidates.forEach(c => {
  console.log(c.path, c.hasSkillMd ? '✓ SKILL.md' : '⚠ README.md');
});
```

### `parseSkillCandidate(candidate)`

解析单个 skill 候选，提取元数据。

**参数：**
- `candidate` (Candidate) - 候选对象

**返回值：** `Skill` - 完整的 skill 对象

```javascript
const { path, root, hasSkillMd } = candidates[0];
const skill = parseSkillCandidate({ path, root, hasSkillMd, hasReadme: true });
console.log(skill.name, skill.description, skill.source);
```

## 数据结构

### Skill 对象

```typescript
interface Skill {
  id: string;                    // SHA256 哈希 ID
  name: string;                  // 显示名称
  slug: string;                  // URL-safe 标识符
  description: string;           // 描述
  source: {
    type: 'git' | 'plugin' | 'builtin' | 'unknown';
    url: string | null;
    subdir: string | null;
    ref: string | null;
    commit: string | null;
  };
  location: {
    path: string;                // 绝对路径
    root: string;                // 根目录
    rootType: 'central_library' | 'agent_global' | 'project_local' | 'unknown';
    agent: string | null;        // Agent 类型
  };
  tags: string[];
  hashes: {
    contentSha256: string;
    normalizedTextSha256: string;
  };
  usage: {
    installedInAgents: string[];
    installedInProjects: string[];
    presetCount: number;
    hasRecentModification: boolean;
    manuallyPinned: boolean;
  };
  frontmatter: Record<string, string>;
  createdAt: string | null;
  modifiedAt: string | null;
  lastSeenAt: string;
}
```

### Candidate 对象

```typescript
interface Candidate {
  path: string;        // 目录绝对路径
  root: string;        // 根目录
  hasSkillMd: boolean; // 是否有 SKILL.md
  hasReadme: boolean;  // 是否有 README.md
}
```

## 工具函数

### `normalizePath(path)`

规范化路径（展开 `~`，统一斜杠）。

### `expandHome(path)`

展开 `~` 为用户主目录。

### `isDir(path)`

检查路径是否为存在的目录。

### `parseFrontmatter(text)`

解析 YAML frontmatter。

```javascript
const { data, body, error } = parseFrontmatter(text);
// data: { name: '...', description: '...' }
// body: markdown 内容
// error: null | 'frontmatter_missing_closing_delimiter'
```

## 常量

### `SKIP_DIRS`

跳过的目录名集合（Set）。

```javascript
console.log(SKIP_DIRS.has('node_modules')); // true
console.log(SKIP_DIRS.has('sessions'));     // true
```

包含：`.git`, `node_modules`, `target`, `dist`, `build`, `.tmp`, `.DS_Store`, `sessions`, `backups`, `shell-snapshots`, `session-env`, `debug`, `file-history`, `paste-cache`, `plans`, `daemon`, `ide`, `hooks`, `logs`, `log`, `errors`, `archived_sessions`, `worktrees`, `sqlite`, `accounts`, `memories`, `rules`, `docs`, `vendor_imports`, `process_manager`, `node_repl`, `ambient-suggestions`, `automations`, `codexmate`, `computer-use`, `computer-use-turn-ended`, `browser`, `pets`

### `DEFAULT_AGENT_ROOTS`

默认的 Agent 根目录列表。

```javascript
// => ['~/.skills-manager', '~/.agent', '~/.agents', '~/.codex', '~/.claude', ...]
```

## CLI 命令

```bash
# 扫描
agent-skill-doctor scan [--root <path>]

# 诊断
agent-skill-doctor diagnose [--format text|json]

# 报告
agent-skill-doctor report [--format md|json|html] [--output <path>]

# 重复检测
agent-skill-doctor duplicates

# 风险扫描
agent-skill-doctor risks [--severity high|critical]

# 冲突检测
agent-skill-doctor conflicts

# 僵尸检测
agent-skill-doctor zombies

# 生成优化计划
agent-skill-doctor plan [--mode safe|normal|aggressive]

# 应用计划（dry-run）
agent-skill-doctor apply --plan <plan.json>
```
