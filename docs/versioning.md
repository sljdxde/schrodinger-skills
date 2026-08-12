# Skill 版本号与自更新规则

本仓库所有 skill 采用**语义化版本（semver）**驱动自更新。更新脚本优先比对远端版本号，版本一致就不下载任何内容；只有远端版本更新时才拉取并替换。

## 1. 版本存放在哪

| 类型 | 位置 | 示例 |
|---|---|---|
| 普通 skill | `SKILL.md` frontmatter 的 `version:` 字段 | `version: 1.0.0` |
| 组合包（bundle） | 包根目录的 `VERSION` 文件 | `personal-knowledge-base/VERSION` |

frontmatter 里的 `version` 必须是 `X.Y.Z` 形式；正文里出现的 "version" 字样不会被识别（解析只认 frontmatter 区间）。

## 2. 版本号怎么涨

| 段位 | 什么时候用 |
|---|---|
| **patch**（1.0.0→1.0.1） | 修 typo、文档措辞、不改变行为的优化 |
| **minor**（1.0.0→1.1.0） | 新增/调整能力、references 内容变化、workflow 修改 |
| **major**（1.0.0→2.0.0） | 触发条件、输入/输出契约、边界发生不兼容变化 |

## 3. 铁律：改 skill 必 bump

**任何对某个 skill 目录内容的修改，提交前必须 bump 它的版本号**——否则已安装的用户永远收不到这次更新（版本没变，更新脚本会认为已是最新）。

```bash
# 修改了 house-buying 的某个 reference → patch 或 minor
python tools/bump_version.py house-buying --part minor

# 一次改了多个 skill
python tools/bump_version.py --all --part patch

# 直接设定（仅限单个 skill）
python tools/bump_version.py skill-architect --set 1.2.0

# 提交前 lint：任何 skill 缺版本号会报错退出（exit 1）
python tools/bump_version.py --check
```

建议把 `--check` 挂到 pre-commit 或 CI，防止漏 bump。

## 4. 更新脚本的判定逻辑

`scripts/update_self.py`（每个 skill 一份 boilerplate）按以下顺序工作：

1. **版本优先（version）**：本地读 SKILL.md frontmatter / VERSION 文件；远端通过 raw.githubusercontent.com 只拉取对应文件（几十 KB 以内，不下载整包）。
   - 远端版本 > 本地版本 → `update_available: true`，`--apply` 时下载整包、备份后替换。
   - 远端版本 = 本地版本 → 已是最新，结束。
   - 远端版本 < 本地版本 → `local_ahead`（本地超前），不更新、不降级。
2. **清单回退（manifest）**：任一侧读不到版本号（老版本 skill、未升级的老远端、网络异常）时，自动回退到历史行为——下载仓库 zip、逐文件比对 sha256。结果里 `method` 字段会标明本次走了哪条路（`version` / `manifest`）。

## 5. 兼容性承诺

- **旧 updater + 新仓库**：旧脚本的 manifest 全量对比照常工作，不受影响。
- **新 updater + 无版本的老 skill / 老远端**：自动回退 manifest 路径，行为与旧版一致。
- **CLI 与 JSON 输出向后兼容**：`--check` / `--apply` / `--allow-repo-working-copy` / `--self-test` 不变，仅新增 `--version`；输出只增字段（`method` / `local_version` / `remote_version` / `relation`），不删不改既有字段。
- **skills-doctor 的 npm 检查**已并入统一 boilerplate，由 `NPM_PACKAGE` / `NPM_COMMAND` 常量开启，行为与历史一致。
- git 工作区内的 skill 默认拒绝被替换（防误覆盖开发中的副本），显式加 `--allow-repo-working-copy` 才会更新——此保护不变。

## 6. 新 skill 的初始版本

用 skill-architect 编译出的新 skill 默认带 `version: 0.1.0`；可在 `blueprint.json` 里用 `version` 字段覆盖。后续每次修改按第 2、3 节 bump。
