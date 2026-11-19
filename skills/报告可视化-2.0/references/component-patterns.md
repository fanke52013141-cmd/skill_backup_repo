# Component Patterns

本文件定义“什么信息用什么形式呈现”。不要把所有内容都做成同一种卡片。

## 1. Hero / Summary

适合：页面总标题、核心结论、研究范围、4 个以内核心指标。

结构：

```text
Eyebrow
大标题（Serif / Navy）
1–3 行摘要
[可选] 2–4 个指标块
```

指标块之间用 1px border 形成整体，而不是 4 张悬浮卡。

## 2. Section Header

推荐：

```text
[小号英文/分类标签]                     [1–3 行说明]
中文章节标题
```

宽屏可左右对齐；窄屏垂直堆叠。

**禁止硬限制右侧描述的 `max-width`**（如 `max-width:340px`）。当描述文本超过 340px 时会被强行折成多排，视觉上"明明一行能展示却被强行换行"。规范写法：
```css
.sec-head{display:flex;justify-content:space-between;align-items:flex-end;gap:40px;margin-bottom:44px}
.sec-desc{max-width:42%;text-align:right;font-size:13px;color:var(--ink-soft);line-height:1.7;flex:none}
```
`max-width` 用百分比（不超过 50%）让 flex 容器自适应分配；标题区始终一行展示，描述按文字自然伸展。

## 3. Dual Comparison Card

适合：两种角色、两套方案、Before/After、A/B 路径。

- 外容器 20px radius + `shadow-card`。
- 中间用 1px divider；可在中心放 48px 圆形连接符。
- 左侧使用 navy soft 渐变；右侧使用 amber soft 渐变。
- 两侧标签分别使用各自主色 weak background。

避免：两侧都使用高饱和实色背景。

## 4. Principle / Insight Grid

适合：3–6 个原则、洞察、能力、关键发现。

- 桌面 3 列，gap 20px；移动 1 列。
- 普通卡 14px radius，padding 28px。
- 44px 图标块，10px radius，使用 navy-soft。
- hover 上移 2px + `shadow-hover`。

## 5. Feature Cards

适合：模块能力、产品功能、方案组成。

- 桌面 2 列，gap 24px。
- 顶部 3px semantic accent line。
- Header：40px icon + title + pill。
- Detail：低饱和内嵌块 + 左侧 2px accent。

## 6. Table

适合：边界、责任、风险、规则矩阵、参数对比。

### 强表头版本

- 表头 navy + white text。
- 内容 paper。
- row hover：极弱 navy 透明背景。

### 弱表头版本

- 表头 paper-dark + navy text。
- 适用于风险/说明类表格，避免过于“数据库后台”。

### Badge

- navy-soft / navy：主角色、确认、常规状态。
- amber-soft / amber-deep：第二角色、提示、中等风险。
- `#e6f2ec` / success：高置信/已完成。

移动端（`max-width:899px` 媒体查询内）：表格外层 `overflow-x:auto`，并给 `table` 加 `min-width:560px` 触发横向滚动；**桌面端默认不允许 `overflow-x:auto`**，否则表格列少时会无意义地出现一条空滚动条。

## 7. Tabs

适合：同一层级下 2–6 个互斥视图。

- inactive：paper + border + ink-soft。
- active：navy + white；第二语义可 amber-deep + white。
- radius 8–10px。
- 不使用下划线式 Material Tabs，除非用户已有设计系统要求。

## 8. Journey / Stage Detail

适合：用户旅程、流程阶段、生命周期。

推荐组合：

```text
[阶段 Tab / Chips]
┌───────────────────────────────┐
│ 左侧动作/角色 A │ 右侧动作/角色 B │
│                                 │
│ 用户感知 / 结论 / 注意事项       │
└───────────────────────────────┘
```

两列动作分别使用 navy-soft 与 amber-soft。

## 9. Scenario Flow

适合：协同流程、闭环、操作步骤。

- 纵向步骤更适合长文本。
- 每步使用 32–36px 圆形角色标识。
- 步骤之间用 1px 竖线连接。
- 角色色保持一致；用户/系统可用 paper-dark/ink-soft。

## 10. Architecture Layers

适合：系统架构、能力层、数据流的“概念架构”。

- 外层使用 paper-dark，14px radius，padding 32–40px。
- 每层是 paper 卡片，10px radius。
- 层标题用 amber-deep + Serif。
- 内部模块用小型 `arch-item` 标签，不画复杂线条时也能读懂层级。

若用户需要严格技术拓扑图，改用 SVG/Mermaid/Canvas，不强制本卡片结构。

## 11. Risk / Pitfall Cards

适合：问题 → 原因 → 解决方式。

- 2 列卡片（移动 1 列）。
- 左边 3px amber warning line。
- `solution` 使用 success 色。
- 不用红色大背景；除非是阻塞/故障级风险。

## 12. Prompt / Policy Detail

适合：规则、Prompt、制度、长配置说明。

- 顶部 Tabs 选版本。
- Header 可使用 navy-soft→paper / amber-soft→paper 渐变。
- Body 使用 2 列信息块；移动端 1 列。
- 代码参数/温度值等使用 Mono Badge。

不要一次性把 100+ 行 Prompt 全塞在一个黑色代码块里；优先摘要 + 可展开全文。

## 13. Quote / Callout

- paper 内嵌浅色背景。
- 左侧 2–3px navy/amber。
- 14px，line-height 1.8。
- 只放关键结论、定义、引用，不作为普通正文容器。

## 14. Section Background Rhythm

推荐节奏：

```text
paper       → 常规章节
paper       → 常规章节
paper-dark  → 边界/矩阵/重要分析带
paper       → 常规章节
paper       → 功能/方案
paper-dark  → 风险/交互范式带
paper       → 结论
```

不要每个 section 都换背景。

**全宽背景（重要，避免边缘露白）**

`.alt` 章节的 `paper-dark` 背景必须延伸到 `.main` 的左右边缘（即左侧栏右侧的全部可用区域），不能被 `.content` 的 `max-width` / 内边距截断，否则会出现"纸被切掉"的视觉效果。

实现方式（CSS 负 margin + 伪元素铺底）：

```css
/* 主内容填满 .main，max-width 仅作上限 */
.content { width:100%; max-width:1440px; margin:0 auto; padding:0 8px; box-sizing:border-box; }

/* .alt 章节：用负 margin 抵消 .content 的内边距，再用 ::before 铺底 */
.section.alt{
  background:transparent;
  position:relative;
  margin:0 -8px;          /* 抵消 .content 的 padding */
  padding:78px 8px;       /* 保留内部留白 */
}
.section.alt::before{
  content:"";
  position:absolute;
  z-index:-1;
  inset:0;
  left:0; right:0;
  background:var(--paper-dark);
}
/* 宽屏（content 因 max-width 不再填满 .main 时）继续向左/右铺底 */
@media (min-width:1704px){
  .section.alt::before{
    left:calc((1704px - 100vw) / 2);
    right:calc((1704px - 100vw) / 2);
  }
}
/* 移动端 .content padding 改为 16，.alt 的负 margin/内边距也要同步 */
@media (max-width:899px){
  .content{ padding:0 16px; }
  .section{ padding:52px 16px; }
  .section.alt{ margin:0 -16px; padding:52px 16px; }
}
```

移动端 `.alt` 章节的 `.section.alt` 还需要一个单独的移动端规则：把负 margin 和 padding 都从 8 改成 16，跟 `.content` 在移动端的 `padding:0 16px` 保持一致。`.section`（非 alt）也要给一个横向 padding，避免内容贴到屏幕边。

**其他常见坑**

- 网格卡片里的 flow/超 表格超过列宽：给 `.grid-2 > *,.grid-3 > *,.dual > *{min-width:0}`，让 grid 子项能缩到列宽以内，flex 内容自然换行。
- 全局防水平滚动：给 `html,body{overflow-x:hidden}`，避免任何子元素意外溢出导致整页出现横向滚动条。
- `border-top` 在 `.alt` 上因为负 margin 会自动延伸到 `.main` 边缘，可以当成章节分隔线使用，不必另外画。

## 15. 图表

若需要 ECharts/Chart.js：

- 图表背景透明。
- 主系列 navy，辅助系列 amber；次级系列用 soft/gray。
- 坐标轴与网格线使用 border/ink-light。
- 避免默认彩虹色 palette。
- 图表必须有标题、单位、时间范围、数据来源/口径（如果用户提供）。
- 不虚构数据。
