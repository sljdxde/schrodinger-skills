# Codex + Ob 个人知识库

这是给 **Codex + Obsidian + 本地 `ob` CLI** 设计的个人知识库组合包。

它的核心不是让 Agent 另建一个云端笔记系统，而是让 Codex 把 Obsidian vault 当作一个可检索、可维护、可持续积累的本地知识库：

- **Codex** 负责理解意图、规划检索范围、提炼结论、维护索引和记录变更。
- **`ob`** 负责访问当前 Obsidian vault，约束所有读写都发生在 vault 内。
- **Obsidian** 负责人工浏览、链接导航、编辑和最终确认。

## 这套能力能做什么

- **查知识**：按关键词、个人/工作范围、目录和标签检索，先定位再只读取必要笔记。
- **存知识**：把对话结论、文章、资料或研究结果写入 `raw/`、`concepts/`、`entities/`、`comparisons/`、`queries/` 等结构化目录。
- **整理知识**：补齐标签、wikilink、索引和变更日志，修复已有笔记的结构漂移。
- **审计知识库**：检查缺失目录、断链、孤立笔记、schema/index/log 漂移，以及标签冲突。
- **归档对话**：把值得长期复用的结论沉淀为查询页或概念页，而不是把整段聊天原样堆进去。
- **切换 vault**：使用当前配置的 vault；存在多个候选时先确认，不猜错库。
- **保护敏感内容**：读写遵循最小范围原则，回答只返回完成任务所需的字段或片段。

## 组合内容

这个目录需要整体安装，包含两个互相配合的 skill：

| Skill | 作用 |
|---|---|
| `ob-llm-wiki` | 个人知识库的主流程：启动、检索、摄取、整理、审计、归档和输出规则 |
| `ob` | 本地 vault 的底层操作：检查、定位、列目录、读写、搜索、移动和删除 |

`ob-llm-wiki` 依赖 `ob` 执行实际 vault 操作。只安装其中一个，能力会不完整。

## 安装方式

直接把下面这句话交给 Codex 或其他支持 Agent Skills 的 Agent：

```text
请把这个目录作为一个组合包安装：
https://github.com/sljdxde/schrodinger-skills/tree/main/personal-knowledge-base

需要同时安装其中的 ob-llm-wiki 和 ob 两个 skill，不要只安装 README 或其中一个目录。
安装后确认两个 skill 都能被发现；使用个人知识库时优先调用 ob-llm-wiki，并让它通过 ob 操作 vault。
```

也可以直接说：

```text
安装 schrodinger-skills 的 personal-knowledge-base 整套能力，包含 ob-llm-wiki 和 ob。
```

安装后，先让 Agent 执行：

```text
请检查 ob 是否可用，并告诉我当前 Obsidian vault 路径；不要修改任何笔记。
```

## 使用示例

```text
查我的个人知识库里关于家庭现金流的已有结论，只引用 #个人 笔记。
```

```text
把刚才关于这本书的三个长期结论归档到个人知识库，补充索引、标签和日志。
```

```text
审计我的知识库：检查断链、缺目录、缺少 #个人/#工作 标签和索引漂移，先只报告问题。
```

## 能力边界

- 这是本地 Markdown 知识库工作流，不提供云同步、账号系统或跨设备进度。
- `ob` 只负责本地 vault 的文件操作；网页检索、PDF/DOCX 转换、学习卡片等能力应由对应 skill 组合完成。
- 涉及删除、批量迁移或覆盖时，Agent 应先报告影响范围；默认优先采用可恢复的新增或更新路径。
- 标签用于分类和检索，不是权限控制；敏感内容仍需最小读取和最小输出。

## 目录结构

```text
personal-knowledge-base/
├── README.md
├── bundle.yaml
├── ob-llm-wiki/
│   ├── SKILL.md
│   └── agents/openai.yaml
├── ob/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   └── scripts/ob.py
└── scripts/install_bundle.py
```

Agent 也可以在下载后执行下面的安装命令，把两个组件分别放入 Codex 的 skill 目录：

```bash
python3 personal-knowledge-base/scripts/install_bundle.py --agent codex
```

如果目标目录已经有同名 skill，安装器默认停止；确认要替换时使用 `--replace`，它会先把旧目录移入临时备份目录。
