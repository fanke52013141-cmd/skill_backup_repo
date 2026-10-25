# 仓库维护约定

- 先读 README.md。仓库支持中文和英文名称，保持现有目录、业务内容、来源、许可证和验证成熟度。
- 默认联网解析 origin/main 的最新发布；离线必须明确说明副本来源。用户指定历史版本时使用 install --version，不能用当前目录冒充旧版。
- 修改已安装 Skill 时读取其管理段和安装记录；本机 sync 已启用时，在验证后调用 publish 并填写实际摘要，不重复索要已授予的回传授权。
- 只修改此 Skill 的维护文件。任务输入、素材和生成产物保存在包外，不随包上传。
- Skill 版本为独立正整数。无变化不加版本；旧记录、旧标签和 Git 历史不能覆盖。恢复旧内容也要产生新版本。
- 发布业务包使用 tools/skillctl.py；不要用 git add -A 夹带其他任务的改动。工具代码与文档升级使用普通 Git 提交，不为所有业务 Skill 加版本。
- 若直接修改仓库中的业务包，需同步生成合法新发布记录并校验；更推荐将变更应用到受管安装，再通过 publish 发布。
- 完整检查：python tools/skillctl.py verify；python -m unittest discover -s tools -p test_skillctl.py -v。修改视频包还需 tools/validate_video_skills.py。
- publish 通过独立工作目录推送 origin/main，不移动当前分支；普通 Git 工作继续前先 fetch，并在干净工作区快进同步。
- 同步失败保留 pending；同一发布重试不增加版本；有并发冲突先保护本地修改并合并，禁止强推。
- Skill 文字不是后台监听。不要宣称手工保存文件就会自动上传，也不要因维护规则而上传业务产物。
