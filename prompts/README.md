# Prompt 管理规范

当前不恢复任何已删除的 Prompt 内容；本目录只提供统一的 Prompt 管理体系。

## 包结构

```text
prompts/
└── <稳定ID>-<N.0>/
    ├── PROMPT.md
    └── prompt.json
```

- `id`：稳定逻辑标识，升版时不变。
- `name`、仓库目录和本地安装目录：统一为 `<id>-<N.0>`。
- `version`：从 `1.0` 开始，每次发布整数加一。
- `repository`：记录 GitHub `url`、`branch` 和当前包 `path`。

`prompt.json` 示例：

```json
{
  "id": "示例提示词",
  "name": "示例提示词-1.0",
  "version": "1.0",
  "entry": "PROMPT.md",
  "summary": "用途说明",
  "repository": {
    "url": "https://github.com/fanke52013141-cmd/skill_backup_repo.git",
    "branch": "main",
    "path": "prompts/示例提示词-1.0"
  }
}
```

## 常用命令

```bash
python tools/promptctl.py list
python tools/promptctl.py install 示例提示词
python tools/promptctl.py status
python tools/promptctl.py diff 示例提示词
python tools/promptctl.py publish 示例提示词 --note "说明变更内容与原因"
python tools/promptctl.py verify
```

`publish` 默认同步本地版本、本地 Git 仓库并推送 GitHub；仅在明确不需要线上发布时使用 `--no-push`。
