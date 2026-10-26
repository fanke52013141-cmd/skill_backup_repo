# 仓库协作规则

## Skill 版本与备注

- 新发布版本统一使用 `N.0`，按 `1.0 → 2.0 → 3.0 → 4.0 → 5.0 → 6.0` 整数递增。
- 每次正式更新均将整数部分加一；不区分 patch、minor、major，不生成 `2.1`、`2.0.1` 等版本。
- 历史三段版本和旧变更记录原样保留，不批量改号。旧版下一次发布取第一段整数加一，如 `2.0.0 → 3.0`；新增 Skill 从 `1.0` 开始。
- 单技能版本唯一真源是 `skills/<名称>/skill.json`。更新版本、日期、验证备注后，使用 `tools/skillctl.py` 的索引函数同步 `manifest.json`；README 中展示的版本同步更新。SKILL.md 不重复记录版本号。
- 每次升版在 CHANGELOG.md 最上方记录日期、技能名、旧版 → 新版、修改内容、原因和验证限制。保留历史记录；版本备注不能只写“优化”。
- 发布命令必须带非空 `--note`；旧 `--bump patch/minor/major` 仅保留命令兼容性，行为全部为整数递增。

## 验证与修改边界

- 仓库是技能源文件；未要求安装时，不覆盖用户安装目录。
- 改动 Skill 时同步其模板、示例和相关回归项，避免示例引导与规则相反。
- 运行 `python tools/skillctl.py verify`。修改版本工具时运行 `python -m unittest discover -s tools -p test_skillctl.py`。
- 区分结构检查、作者桌面演练、独立生成和真实材料端到端验证；未执行的验证写明待执行。
- 不重写历史版本、不强制推送、不把其他 Skill 的内容顺带修改。

## 分类维护

- 一级分类统一为：提示词与 Skill 构建、视频创作、产品经理、开发相关、其他。按主要工作用途归类，交叉用途使用 tags，不移动或复制现有技能目录。
- 分类字段唯一真源是各技能 skill.json：category、subcategory、content_type、tags；通过 skillctl 的 save_manifest 索引函数生成 manifest，并同步 README 与分类索引。
- 新内容优先归现有分类；暂不能归类时放其他，后续有实际需求再扩展。原始提示词保持来源存档身份，并链接对应 Skill。
