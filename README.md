# 范刻的 Skill 仓库

个人 Skill 的集中存放、安装、更新与版本追溯仓库。支持中文和英文名称及正文；自建 Skill 通常使用中文，第三方 Skill 保留上游名称、来源和许可。

**默认安装远端最新已发布版本；指定版本时安装该历史版本并锁定。每个 Skill 独立按整数 `1 → 2 → 3` 迭代。**

本仓库目前为公开仓库。Skill 的定义与配套资料可以入库，任务输入、私有素材、凭据和生成产物应放在 Skill 包外。

查找用途：[分类索引](分类索引.md)。当前机器索引：[manifest.json](manifest.json)。历史发布：[releases/](releases/)。更新摘要：[CHANGELOG.md](CHANGELOG.md)。版本与恢复：[版本管理与工作树](版本管理与工作树.md)。

## 直接对 Agent 说

> 读取这个仓库的 README，列出全部 Skill、当前版本、更新时间、状态、来源与依赖。
>
> 按这个仓库的统一安装器，把「角色视觉设计」最新版安装到当前产品的技能目录。
>
> 安装「公选王PRD撰写专家」第 1 版，保持版本锁定。
>
> 修改我已安装的「角色视觉设计」，补充服装一致性检查；验证后按已启用的回传配置发布，备注本次修改。

Agent 应先确定当前宿主实际识别的安装目录，用 `--target` 指定；不要把某产品的默认目录套用到其他产品。安装或更新后按宿主规则重新发现 Skill，必要时重启宿主。

## 快速开始

需要 Python 3.10+、Git；管理工具只用 Python 标准库。GitHub 上传使用本机已配置的 Git 认证，不把 Token 写入 Skill。

```bash
git clone https://github.com/fanke52013141-cmd/skill_backup_repo.git
cd skill_backup_repo
python tools/skillctl.py list
python tools/skillctl.py history --all
python tools/skillctl.py verify
```

`list`、`history`、`status`、`install`、`update`、`diff` 默认先 fetch 远端 main 和标签。网络失败返回错误，不用旧缓存冒充最新。显式增加 `--offline` 才使用本地 HEAD，并在输出中标明来源。

所有命令输出 JSON，便于 Agent 读取，也接受 `--json`。`list` 包含用途、来源、状态、依赖等完整元数据。没有状态字段时表示未记录，不能推断为稳定或已测试。最新版可能仍为 draft，安装不会把它改成稳定版。

## 安装、历史版本与更新

默认目标保留原工具的 `~/.workbuddy/skills`，也可以设置 `SKILLCTL_TARGET`。跨产品使用时必须明确 `--target`；下面的“实际技能目录”需替换成真实路径。

```bash
python tools/skillctl.py --target "实际技能目录" install "角色视觉设计"
python tools/skillctl.py --target "实际技能目录" install "公选王PRD撰写专家" --version 1
python tools/skillctl.py --target "实际技能目录" status
python tools/skillctl.py --target "实际技能目录" diff "角色视觉设计"
python tools/skillctl.py --target "实际技能目录" update --all
python tools/skillctl.py --target "实际技能目录" update "公选王PRD撰写专家" --unpin
```

- 不指定版本：安装当前远端索引中的最新版本。指定 `--version`：安装该版并锁定，即使指定的恰好是最新版。
- 批量更新跳过未安装和已锁定 Skill。`--unpin` 明确解除锁定并更新。
- 本地有修改或旧安装记录没有可用基线时停止覆盖。需先发布或备份；明确使用 `--force` 时会在安装目录的同级 `.skillctl_backup/` 保留旧目录。
- `diff` 比较整个业务包，包括引用、脚本、模板和文件删除，不只比较 SKILL.md。
- 离线副本旧于安装版时不会隐式降级；需要旧版时明确使用 `install --version`。
- 既有外部安装不会自动被接管；重新安装并显式允许覆盖时会备份原内容。

历史清单可以按中文名、英文名、id 或现有 slug 查询：

```bash
python tools/skillctl.py history "公选王PRD撰写专家" --revisions
python tools/skillctl.py history --all --json
```

`--revisions` 额外列出原始 Git 修订。原有未独立编号的修订仍保留在 Git 历史中。

## 安装时自动加入维护规则

统一安装器会复制完整业务包，在 `SKILL.md` 末尾加入一份受管维护段，并生成 `.skillctl/installation.json` 和 `.skillctl/maintenance.md`。无需作者逐个粘贴；重复安装不会重复叠加。

维护段要求 Agent 在实际修改 Skill 并验证后调用统一发布工具。规则模板在 [policy/managed-skill.md](policy/managed-skill.md)，不把长维护协议混进业务正文。

发布时只去掉与安装记录完全匹配的管理段及管理文件。管理段被破坏会报错，不能猜测删除正文。版本比较依据业务内容 hash，管理注入本身不产生业务版本。

**普通 git clone 或直接下载不会执行安装器，也不会自动加入上述内容。** 需要受管安装时，使用本仓库的 `install` 命令。

## 修改后回传 GitHub

仓库所有者在每个可信本机 clone 启用一次；设置保存在被 Git 忽略的 `.skillctl-local/` 中，不随公共 Skill 分发。启用代表允许该管理器在实际修改与验证完成后回传；不授予普通下载者任何 GitHub 写权限。

```bash
python tools/skillctl.py sync --enable
python tools/skillctl.py --target "实际技能目录" publish "角色视觉设计" --note "补充服装一致性检查"
python tools/skillctl.py sync
python tools/skillctl.py sync --disable
```

发布会检查本地安装基线与远端最新版，用独立工作目录只提交对应包、发布记录、索引及变更摘要，并原子推送 main 和该版标签。远端确认后才报告“已上传”，再刷新安装记录。没有业务变化不增加版本。

当前分支及其暂存区不随发布移动，也不会夹带其他任务的文件。继续普通 Git 开发前，在干净工作区执行 `git pull --ff-only` 同步本地分支；不要通过强推让远端退回旧提交。

同步失败保留 `.skillctl-local/pending/` 与准备好的提交。使用同一条发布命令重试，不会重复增加版本；不同 Skill 的并发更新会基于新 main 重新组装。如果同一 Skill 已有并发版本，停止覆盖。需要重新合并时：

```bash
python tools/skillctl.py cancel-pending "角色视觉设计"
```

该命令只将待同步记录和提交归档，保留本地修改，不删除或覆盖远端版本。Agent 应先保存差异、安装最新版，再合并原修改后重新发布。不要直接删除 pending 文件假装同步成功。

换了 clone 的位置时，安装记录中的仓库路径可能失效。核对新旧 origin 相同后，使用 `publish ... --adopt` 接管；工具仍检查业务基线。

这里的自动同步由 Agent 完成修改后调用工具执行。**手工编辑文件而 Agent 未运行，不会自行上传。** 本仓库没有启动后台文件监听、定时任务或付费服务。

## 收录新 Skill

在目标技能目录准备完整业务包与 `skill.json`，至少包含 `summary`；第三方内容同时提供 `origin`、`source`、许可及上游 commit 等已有信息。

```bash
python tools/skillctl.py --target "实际技能目录" publish "我的新技能" --new --id my-new-skill --note "首次收录"
```

id 使用唯一、稳定的英文小写字母、数字和连字符；名称和正文可以中文或英文。首次发布为整数 1，发布成功后自动形成受管安装。

## 版本与历史保留

2026-10-26 从原语义版本迁移为整数版本，16 个 Skill 共建立 17 条发布记录。公选王PRD撰写专家的旧 `1.0.0 → 1`、`2.0.0 → 2`；其他当前版本均为 1。映射记录保留 legacy_version、原提交及原始更新时间，业务内容没有因迁移改写。

每版记录整数版本、带时区时间、更新摘要、内容 SHA-256、发布引用。标签格式为 `skill/<id>/v<整数>`；不使用全仓库唯一的“latest release”定位某个 Skill。

不得修改旧发布记录、覆盖旧标签或强推改写历史。恢复旧内容后重新发布会产生更大的新版本。工具和 CI 检查不是仓库管理员权限的替代：GitHub 侧可另配置标签与 main 保护，并保留独立镜像备份，不能把单一云仓库视为绝对不丢失保证。

## 目录与校验

```text
skills/<中文或英文名称>/        业务正文、引用、脚本、模板与当前 skill.json
releases/<id>/<整数>.json      每版追加记录，不可覆盖
manifest.json                 当前元数据汇总
CHANGELOG.md                  人可读更新摘要，旧记录保留
policy/managed-skill.md        安装时注入的维护模板
tools/skillctl.py              命令入口
tools/skillstore.py            快照、hash、安装和一致性检查
tools/skillpublish.py          发布、远端确认、待同步恢复
tools/skillmigrate.py          旧版本迁移
```

```bash
python tools/skillctl.py verify
python -m unittest discover -s tools -p test_skillctl.py -v
```

五个视频 Skill 的额外内容校验需要 `PyYAML`、`jsonschema`，运行 `python tools/validate_video_skills.py`。这些是开发校验依赖，安装和发布管理器不依赖它们。CI 在 Windows 和 Linux 上检查结构、历史记录与管理流程；业务生成效果仍以各 Skill 的原有验证状态为准。
