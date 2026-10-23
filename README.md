# 技能库

个人 AI 技能的统一存放与版本管理仓库。

**仓库是唯一真相源，`~/.workbuddy/skills` 只是部署产物。** 不要在本地安装目录里做长期修改——要改就改完再 `publish` 回写，否则下次更新会被拦下或覆盖。

## 技能清单

| 技能 | 版本 | 用途 | 来源 |
|---|---|---|---|
| 项目结构可视化 | 1.0.0 | 把 GitHub 仓库或本地项目转成面向产品经理的本地可点击可视化导航报告 | 自建 |
| PRD工程师 | 1.0.0 | 把原型和交互说明转成前端可直接编码的 PRD，消灭一切模糊性 | 自建 |
| Vibe Coding教练 | 1.0.0 | 把模糊产品想法结构化为可实现系统，含需求梳理、状态设计与 MVP 任务拆解 | 自建 |
| 需求文档审查 | 1.0.0 | 对 PRD 做完整性、一致性、体验、可行性四轮审查，输出问题清单或评审报告 | 自建 |
| 公考遴选需求探索 | 1.0.0 | 把公考/遴选考试教育产品的初步想法转化为结构化需求洞察 | 自建 |
| 提示词工程师 | 1.0.0 | 诊断、优化或从零构建提示词，输出可直接复制使用的版本 | 自建 |
| 报告可视化 | 1.0.0 | 生成左侧菜单 + 米白纸张 + 深海军蓝的编辑型研究报告页面 | 改造自 paper-navy-visual-report |

## 常用命令

```bash
python tools/skillctl.py list                    # 看仓库里有什么、什么版本
python tools/skillctl.py status                  # 本地装了哪些、哪些该更新
python tools/skillctl.py install 报告可视化       # 安装单个技能
python tools/skillctl.py update --all            # 全部更新
python tools/skillctl.py diff 报告可视化         # 升级前先看改了什么
python tools/skillctl.py verify                  # 校验仓库结构是否一致
```

改完技能要回写：

```bash
python tools/skillctl.py publish 报告可视化 --bump minor --note "新增表格密度规则"
```

`--bump` 三档：`patch` 措辞修订、`minor` 加内容、`major` 流程或输出格式变了。

## 版本规则

版本号只写在一处：`skills/<技能名>/skill.json`。`SKILL.md` 的 frontmatter 只负责触发（`name` + `description`），不写版本，避免两份值打架。

| 改了什么 | 升哪一位 | 例子 |
|---|---|---|
| 措辞、错别字、description 微调 | patch | 1.0.0 → 1.0.1 |
| 新增步骤 / 示例 / 脚本，老用法不变 | minor | 1.0.1 → 1.1.0 |
| 流程重构、输出格式变更、改名 | major | 1.1.0 → 2.0.0 |

技能没有 API，所以「破坏性」的判定标准是：**原来的说法不再触发，或者产出的东西结构变了**。

## 安装器行为

- **只搬不改**：所有格式规范化在入库时一次做完，安装就是原样复制，保证仓库与本地 hash 可比。
- **防覆盖**：`~/.workbuddy/skills/.skillctl.json` 记录每个技能的安装版本和文件 hash。本地被手改过时 `update` 会停下来，不会静默覆盖；加 `--force` 才覆盖，且覆盖前自动备份到 `.skillctl_backup/`。
- **离线可用**：从本地 clone 的副本安装，`git pull` 只在主动同步时发生。
- **重复检测**：安装后如果发现本地还有正文相同的旧目录（多为改名遗留），会提示出来。

## 目录结构

```
skill_backup_repo/
├── manifest.json          # 机器索引，由 skillctl 生成，不要手改
├── CHANGELOG.md           # 变更记录，publish 时自动追加
├── skills/
│   └── <技能名>/
│       ├── SKILL.md       # 触发与执行正文
│       ├── skill.json     # 版本唯一真源
│       ├── references/    # 长背景、映射表（按需）
│       ├── scripts/       # 复杂逻辑（按需）
│       └── evaluation/    # 评估用例（按需）
└── tools/
    └── skillctl.py
```

## 新增技能

在 `~/.workbuddy/skills/` 下建好技能目录（含 `SKILL.md` 和 `skill.json`），然后：

```bash
python tools/skillctl.py publish 新技能名
```

会自动收录进仓库、写入 manifest、提交一次 commit。

## 注意

- 技能名统一用中文，`slug` 字段保留英文原名便于追溯。
- 技能里不要放 API Key、Token、内网地址、个人信息。仓库为私有，但仍按最小暴露原则处理。
- 安装或更新后，Agent 通常需要**新开一个会话**才能识别到新技能。
