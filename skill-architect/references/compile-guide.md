# Compile Guide — compile_skill.py 用法

把访谈产出的 `blueprint.json` 编译成本仓库布局的 skill 包。

## 基本用法

```bash
# 编译到指定父目录（默认在当前目录下生成 <name>/）
python scripts/compile_skill.py --blueprint examples/sample-blueprint.json --out ./skills

# 覆盖已存在的同名目录
python scripts/compile_skill.py --blueprint bp.json --out ./skills --force
```

退出码：成功 `0`，失败 `1`（蓝图不合法 / 目标已存在且未加 `--force` / 找不到文件）。

## 生成包结构

```
<out>/<name>/
├── SKILL.md                  # frontmatter(name/description) + 中文正文
├── agents/openai.yaml        # interface 注册块（display_name / short_description / default_prompt）
├── scripts/update_self.py    # 从本 skill 复制，SKILL_NAME 已替换为 <name>
├── references/<title>.md     # 每个 blueprint.references 一项一个 stub
└── evaluations/self-eval.md  # evaluator 填写的评估占位
```

生成的包和 `house-buying` / `memory-forge` 同构：Agent（Claude Code / Codex / Cursor）直接说「安装这个目录」即可，`scripts/update_self.py --apply` 立即可用。

## 改名与发布

- 生成包的 `scripts/update_self.py` 默认指向本仓库（`sljdxde/schrodinger-skills`）。如果生成 skill 要发布到**别的 GitHub 仓库**，改文件顶部三个常量：
  ```python
  REPO_OWNER = "<你的用户名>"
  REPO_NAME = "<你的仓库名>"
  REPO_BRANCH = "main"
  ```
- 想改 skill 名：改 blueprint 的 `name` 后重跑（或先 `--force`），不要在生成目录里手工改名——`update_self.py` 里的 `SKILL_NAME` 必须与目录名一致，脚本已保证。

## 编译后的必要人工步骤

脚本产出的是**脚手架**，直接能用但内容偏薄。交付用户时明确列出以下待办：

1. 按 blueprint 填实每个 `references/*.md` stub（大纲 → 完整内容）。
2. 用 `evaluations/self-eval.md` 跑一遍评估（见 `evaluator.md`），并修正发现的问题。
3. 用 1–2 个真实场景实测，确认 `SKILL.md` 的「何时触发」描述准确。
4. 发布前在仓库根目录 README 的 skills 表里登记一行。

## 本 skill 自身

本目录（skill-architect）同样遵守仓库约定：

```bash
python scripts/update_self.py --check    # 检查 GitHub 更新
python scripts/update_self.py --self-test  # 自检脚本本身
```
