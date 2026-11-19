# 仓库维护规则

## 收录边界

- 只保留 Skill、Prompt 包、运行所需资源、管理工具、测试、索引和版本记录。
- 不保留原始提示词散文件、研究过程记录、临时验证报告、废弃操作文档、重复旧目录或测试缓存。
- 当前不恢复已删除的 Prompt 内容；新增 Prompt 必须使用完整包结构，不得重新存成无版本 TXT。

## 统一身份与命名

- 每个 Skill/Prompt 使用稳定 `id` 作为命令参数和资产身份，升版时不变。
- `name`、仓库目录、Agent 本地安装目录、SKILL.md frontmatter 和 UI 显示名统一为 `<id>-<N.0>`。
- 版本只允许 `1.0 → 2.0 → 3.0 → 4.0` 整数递增；新资产从 `1.0` 开始。
- `skill.json` / `prompt.json` 是单资产版本与来源真源；`manifest.json` 是机器索引。
- 每个资产必须记录 `repository.url`、`repository.branch`、`repository.path`，升版时同步更新 path。
- 不在工作区堆叠多个历史版本；历史通过 Git 提交追溯。

## 安装与更新

- 使用 `tools/skillctl.py` 管理 Skill，使用 `tools/promptctl.py` 管理 Prompt。
- 安装和更新后的本地目录必须带版本号，安装状态记录版本、目录、GitHub 来源和哈希。
- 正常更新移除旧版本目录；本地有修改时不得静默覆盖，`--force` 覆盖前必须备份。
- 未明确要求安装时，不修改用户实际 Agent 安装目录。

## 发布与 GitHub 同步

- 发布命令：`python tools/<skillctl|promptctl>.py publish <稳定ID> --note "<变更内容与原因>"`。
- 备注必须具体说明变更内容与原因，不得只写“优化”。
- 发布默认推送 GitHub；`--no-push` 仅用于明确的本地发布，不得宣称线上已同步。
- 发布前检查本地与仓库版本一致、暂存区无既有修改、线上无本地尚未包含的新提交。
- 升版时同步资产元数据、frontmatter、UI、manifest、README、分类索引与 CHANGELOG。
- Git 提交只包含本次相关路径，不使用无范围的 `git add -A`。
- 推送成功后才切换 Agent 本地安装版本；推送失败时明确报告仓库与本地状态，不伪造同步成功。
- 不强推、不重写 Git 历史、不覆盖线上较新版本。

## 验证

- Skill 结构或元数据变更后运行 `python tools/skillctl.py verify`。
- Prompt 结构或元数据变更后运行 `python tools/promptctl.py verify`。
- 修改安装、版本或发布逻辑后运行 `python -m unittest discover -s tools -p test_skillctl.py`。
- 修改五个视频 Skill 后运行 `python tools/validate_video_skills.py`。
- 区分结构检查、模拟发布、真实 GitHub 推送和实际生成效果；未执行的验证不得写成已通过。
