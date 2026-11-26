# Skill & Prompt 资产库

统一管理 Skill 和 Prompt 的命名、版本、安装、备注及 GitHub 同步。线上仓库是唯一内容真相源，Agent 本地目录是带来源信息的可更新安装副本。

## 统一命名规则

每个资产同时具有稳定 `id` 和版本化 `name`：

| 字段 | 规则 | 示例 |
|---|---|---|
| `id` | 永久稳定，升版不变 | `报告可视化` |
| `name` | 必须为 `id-N.0` | `报告可视化-2.0` |
| `version` | 从 `1.0` 开始，每次发布整数加一 | `1.0 → 2.0 → 3.0` |
| `repository` | 记录 GitHub 地址、分支和包路径 | `url + branch + path` |

以下位置必须保持同一个版本化 `name`：

- 仓库目录：`skills/报告可视化-2.0` 或 `prompts/示例提示-1.0`
- Agent 本地安装目录：`报告可视化-2.0`
- `skill.json` / `prompt.json` 的 `name`
- `SKILL.md` frontmatter 的 `name`
- Skill UI 的 `display_name` 和默认调用名称

`id` 用于安装、更新和发布，因此命令始终使用不带版本号的稳定 ID。版本只允许 `1.0 → 2.0 → 3.0 → 4.0`，不使用 `v1.0`、`1.0.0`、`2.1` 或 `2.0.1`。

## GitHub 来源记录

每个 `skill.json` 和 `prompt.json` 都包含：

```json
{
  "id": "报告可视化",
  "name": "报告可视化-2.0",
  "version": "2.0",
  "repository": {
    "url": "https://github.com/fanke52013141-cmd/skill_backup_repo.git",
    "branch": "main",
    "path": "skills/报告可视化-2.0"
  }
}
```

安装状态同时记录该来源、版本化目录、版本和文件哈希。发布时直接读取资产中的 `repository.url` 和 `branch`，不依赖手写线上地址。

## 目录结构

```text
skill_backup_repo/
├── skills/
│   └── <Skill-ID>-<N.0>/
│       ├── SKILL.md
│       ├── skill.json
│       ├── references/       # 按需：规范与引用
│       ├── assets/           # 按需：模板与素材
│       ├── scripts/          # 按需：运行脚本
│       └── evaluation/       # 按需：评估用例
├── prompts/
│   ├── README.md             # Prompt 包规范；当前不恢复旧 Prompt
│   └── <Prompt-ID>-<N.0>/    # 以后新增时采用
│       ├── PROMPT.md
│       └── prompt.json
├── tools/
│   ├── skillctl.py           # Skill 与 Prompt 共用核心同步逻辑
│   ├── promptctl.py          # Prompt 命令入口
│   ├── test_skillctl.py      # 安装、升版、同步与失败保护回归
│   └── validate_video_skills.py
├── manifest.json             # Skill/Prompt 机器索引与默认仓库
├── 分类索引.md               # Skill 人工导航
├── CHANGELOG.md              # 每次发布的备注与版本记录
└── AGENTS.md                 # 仓库维护约束
```

## Skill 使用流程

### 1. 安装到 Agent 本地

```bash
python tools/skillctl.py install 报告可视化
```

安装结果为版本化目录：

```text
~/.workbuddy/skills/报告可视化-2.0/
```

自定义安装根目录：

```bash
python tools/skillctl.py --target "D:\my-agent\skills" install 报告可视化
```

### 2. 查看状态与差异

```bash
python tools/skillctl.py list
python tools/skillctl.py status
python tools/skillctl.py diff 报告可视化
```

先从 GitHub 获取其他电脑发布的最新内容，再更新本地安装：

```bash
git pull --ff-only
python tools/skillctl.py update 报告可视化
# 或更新全部已安装 Skill
python tools/skillctl.py update --all
```

正常更新会移除旧版本目录；本地被手动修改时会停止，`--force` 才会先备份再覆盖。

### 3. 修改本地 Skill 并发布

直接修改已安装的 `报告可视化-2.0`，然后执行：

```bash
python tools/skillctl.py publish 报告可视化 --note "补充表格密度规则与两个验收示例"
```

发布会自动完成：

1. 检查本地与仓库是否同为 `2.0`，避免基于旧副本覆盖新版本。
2. 检查 Git 暂存区，避免混入其他暂存修改。
3. 从资产记录的 GitHub 地址 fetch，线上存在本地未包含的新提交时停止。
4. 将版本升级为 `3.0`，同步修改版本化名称、frontmatter、UI 和 repository.path。
5. 更新线上仓库工作副本、`manifest.json`、README、分类索引和 CHANGELOG。
6. 只暂存本次相关路径，以备注创建 Git commit，并 push 到对应 GitHub 分支。
7. **推送成功后**，将 Agent 本地安装切换为 `报告可视化-3.0` 并更新安装状态。

如果推送失败，本地 Agent 继续保持 `2.0`，不会显示为已同步；工具会明确提示仓库提交和推送状态。

仅想在本地生成新版本时，必须显式使用：

```bash
python tools/skillctl.py publish 报告可视化 --note "本地试验，暂不发布" --no-push
```

`--no-push` 不代表 GitHub 已更新。

## Prompt 使用流程

当前没有恢复此前删除的 Prompt 内容，但管理体系已经可用。Prompt 包由 `PROMPT.md + prompt.json` 组成，命名、版本和同步规则与 Skill 完全一致。

```bash
python tools/promptctl.py list
python tools/promptctl.py install 示例提示词
python tools/promptctl.py status
python tools/promptctl.py diff 示例提示词
python tools/promptctl.py publish 示例提示词 --note "优化输出约束与示例"
python tools/promptctl.py verify
```

详细格式见 [Prompt 管理规范](prompts/README.md)。

## 当前 Skill

| Skill ID | 版本 | 用途 |
|---|---|---|
| 项目结构可视化 | 2.0 | 把 GitHub 仓库或本地项目转成可点击的可视化导航报告 |
| PRD工程师 | 2.0 | 把原型和交互说明转成前端可直接编码的 PRD |
| 公选王PRD撰写专家 | 5.0 | 先审原型对齐方案、再按固定骨架出稿，撰写人机共读的高信噪比 PRD |
| grill-with-docs | 2.0 | 追问澄清设计，并维护项目术语表与 ADR |
| handoff | 2.0 | 把当前对话压缩成交接文档 |
| Vibe Coding教练 | 2.0 | 需求梳理、状态设计与 MVP 任务拆解 |
| 需求文档审查 | 2.0 | 对 PRD 做完整性、一致性、体验与可行性审查 |
| 公考遴选需求探索 | 2.0 | 把教育产品想法转化为结构化需求洞察 |
| 技能构建专家 | 3.0 | 创建、重构、评估可稳定触发和验证的 Skill |
| 蒸馏万物skill | 1.0 | 把书、长视频、播客、课程或访谈蒸馏成 Agent Skill |
| 提示词工程师 | 2.0 | 诊断、优化或从零构建提示词 |
| 广告创意总监 | 2.0 | 广告目标诊断、专家路由与创意方案 |
| 报告可视化 | 2.0 | 生成编辑型研究报告页面 |
| 视频视觉开发总监 | 2.0 | 故事到视觉方向、色彩灯光与美术边界 |
| 视频镜头提示词 | 2.0 | 文字、图片、音频到中文视频镜头执行指令 |
| 场景视觉设计 | 2.0 | 同一地点的主视图与四宫格提示词 |
| 角色视觉设计 | 2.0 | 同一角色的转面与全身立绘提示词 |
| 分镜板提示词 | 2.0 | 已有镜头组到静态分镜板提示词 |

按用途查找：[分类索引](分类索引.md)。

## 校验

```bash
python tools/skillctl.py verify
python tools/promptctl.py verify
python -m unittest discover -s tools -p test_skillctl.py
python tools/validate_video_skills.py
```

视频 Skill 专项校验需要 `PyYAML`、`jsonschema`；核心安装和发布功能只使用 Python 标准库与 Git。

## 注意事项

- 不存放 API Key、Token、内网地址或个人信息。
- 发布需要当前机器具备对应 GitHub 仓库的推送权限。
- 不自动强推、不覆盖线上较新的提交、不把其他暂存修改混入发布。
- 安装或升级后，宿主通常需要新开会话才能识别新的版本化 Skill 名称。
