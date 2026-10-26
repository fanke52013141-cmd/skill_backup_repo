# 技能库

个人 AI 技能的统一存放与版本管理仓库。

**仓库是唯一真相源，`~/.workbuddy/skills` 只是部署产物。** 不要在本地安装目录里做长期修改——要改就改完再 `publish` 回写，否则下次更新会被拦下或覆盖。

按用途查找：[分类索引](分类索引.md)。多版本对照与恢复：[版本管理与工作树](版本管理与工作树.md)。

## 技能清单

| 技能 | 版本 | 用途 | 来源 |
|---|---|---|---|
| 项目结构可视化 | 1.0.0 | 把 GitHub 仓库或本地项目转成面向产品经理的本地可点击可视化导航报告 | 自建 |
| PRD工程师 | 1.0.0 | 把原型和交互说明转成前端可直接编码的 PRD，消灭一切模糊性 | 自建 |
| 公选王PRD撰写专家 | 3.0 draft | 逐项覆盖原型、字段、状态、弹窗与角色差异，写重点明确的开发 PRD | 自建 |
| grill-with-docs | 1.0.0 draft | 用追问澄清设计，并同步维护项目术语表与 ADR；依赖 grilling、domain-modeling | mattpocock/skills（MIT） |
| handoff | 1.0.0 draft | 把当前对话压缩成交接文档，供下一个 Agent 继续 | mattpocock/skills（MIT） |
| Vibe Coding教练 | 1.0.0 | 把模糊产品想法结构化为可实现系统，含需求梳理、状态设计与 MVP 任务拆解 | 自建 |
| 需求文档审查 | 1.0.0 | 对 PRD 做完整性、一致性、体验、可行性四轮审查，输出问题清单或评审报告 | 自建 |
| 公考遴选需求探索 | 1.0.0 | 把公考/遴选考试教育产品的初步想法转化为结构化需求洞察 | 自建 |
| 提示词工程师 | 1.0.0 | 诊断、优化或从零构建提示词，输出可直接复制使用的版本 | 自建 |
| 广告创意总监 | 1.0.0 draft | 诊断广告目标与创意机制，路由并编排专家，交付文案、脚本或 campaign 方案 | 自建 |
| 报告可视化 | 1.0.0 | 生成左侧菜单 + 米白纸张 + 深海军蓝的编辑型研究报告页面 | 改造自 paper-navy-visual-report |
| 视频视觉开发总监 | 1.0.0 draft | 故事到视觉方向、风格比较、色彩灯光与美术边界 | 用户提示词＋公开专家研究 |
| 视频镜头提示词 | 1.0.0 draft | 文字、图片、音频到中文视频镜头执行指令 | 用户提示词＋公开专家研究 |
| 场景视觉设计 | 1.0.0 draft | 同一地点的主视图与四宫格提示词 | 用户提示词＋公开专家研究 |
| 角色视觉设计 | 1.0.0 draft | 同一角色的转面与全身立绘提示词 | 用户提示词＋公开专家研究 |
| 分镜板提示词 | 1.0.0 draft | 已有镜头组到每板最多四格的静态分镜板提示词 | 用户提示词＋公开专家研究 |

## 常用命令

```bash
python tools/skillctl.py list                    # 看仓库里有什么、什么版本
python tools/skillctl.py status                  # 本地装了哪些、哪些该更新
python tools/skillctl.py install 报告可视化       # 安装单个技能
python tools/skillctl.py update --all            # 全部更新
python tools/skillctl.py diff 报告可视化         # 升级前先看改了什么
python tools/skillctl.py verify                  # 校验仓库结构是否一致
```

五个视频技能另有内容包校验，开发环境需 `PyYAML`、`jsonschema`：

```bash
python tools/validate_video_skills.py
python tools/skillctl.py --target ~/.codex/skills install 角色视觉设计
```

运行时不依赖上述校验库，也不自动调用图片或视频模型。每包按完整 Markdown 知识包约1万至1.5万字设计，详细来源和案例按需读取。原始提示词在 `资料/原始提示词/`，访问范围与验证记录在 `资料/研究记录/`。draft 表示独立前向测试及实际生成效果仍待验证；结构校验与作者桌面演练已记录，不冒充端到端测试。

改完技能要回写：

```bash
python tools/skillctl.py publish 报告可视化 --note "新增表格密度规则及对应示例"
```

每次发布按整数递增，必须填写非空 `--note`。旧 `--bump patch/minor/major` 仅为命令兼容别名，全部执行相同的整数递增。

## 版本规则

版本唯一真源是 `skills/<技能名>/skill.json`，manifest 是工具生成的机器索引，README 是展示副本；修改后保持一致。`SKILL.md` 不写版本号。

**自 2026-10-26 起，统一采用整数版本：`1.0 → 2.0 → 3.0 → 4.0 → 5.0 → 6.0`。**

- 新增 Skill 从 `1.0` 开始；每次正式更新，不论修改大小，整数部分加一，小数部分固定为 `0`。
- 不再按 patch / minor / major 分级，不生成 `2.1`、`2.0.1` 等版本。
- 历史三段版本与历史变更记录原样保留，等下次更新时迁移，例如 `2.0.0 → 3.0`；不为统一格式批量改号。
- 每次更新同步单技能元数据、manifest 与 README 展示版本，并在 CHANGELOG 顶部备注日期、旧版 → 新版、修改内容、原因与验证范围。未执行的验证明确写待执行。
- 规则同时写在 [AGENTS.md](AGENTS.md)，供后续 Agent 执行；版本工具已按此规则生成新版本。

验证版本工具：`python -m unittest discover -s tools -p test_skillctl.py`。

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
python tools/skillctl.py publish 新技能名 --note "新增技能：说明用途、内容与验证范围"
```

会自动收录进仓库、写入 manifest、提交一次 commit。

## 注意

- 技能名统一用中文，`slug` 字段保留英文原名便于追溯。
- 技能里不要放 API Key、Token、内网地址、个人信息。仓库为私有，但仍按最小暴露原则处理。
- 安装或更新后，Agent 通常需要**新开一个会话**才能识别到新技能。
