# Sidebar Navigation Specification

## 1. 目标

将参考页面的“固定顶部导航 + 平滑锚点”语义，重构为更适合长报告的“固定左侧导航 + 主内容滚动”。

导航负责结构，不承担视觉展示任务。

## 2. 桌面骨架

```text
┌─────────────────────────────────────────────────────────────┐
│ Sidebar 264px │ Main content                              │
│               │                                           │
│ Brand         │ Hero / Summary                            │
│ ───────────   │                                           │
│ ● 一级菜单 A  │ Section A                                 │
│   ├ 二级 A1   │                                           │
│   └ 二级 A2   │                                           │
│ ○ 一级菜单 B  │ Section B                                 │
│ ○ 一级菜单 C  │ ...                                       │
│               │                                           │
│ Footer/meta   │                                           │
└─────────────────────────────────────────────────────────────┘
```

推荐 CSS：

```css
.app-shell {
  min-height: 100vh;
  background: var(--paper);
}

.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 264px;
  background: rgba(250, 248, 243, 0.94);
  backdrop-filter: blur(18px);
  border-right: 1px solid var(--border);
  z-index: 50;
  display: flex;
  flex-direction: column;
}

.main {
  margin-left: 264px;
  min-width: 0;
}

.content {
  /* 填满 .main，max-width 仅作阅读宽度的上限；不要写成 min(1200px, 100% - 64px)，
     否则宽屏会出现大段左右留白，.alt 章节的 paper-dark 背景会被截断露出边缘 */
  width: 100%;
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 8px;
  box-sizing: border-box;
}

/* 当 content 因 max-width 不再填满 .main 时（≈ W ≥ 1704px），
   用下面的公式把 .alt 章节的背景向左/右延展到 .main 边缘 */
@media (min-width: 1704px) {
  .section.alt::before {
    left: calc((1704px - 100vw) / 2);
    right: calc((1704px - 100vw) / 2);
  }
}
```

## 3. Sidebar 分区

### 3.1 Brand 区

- 高度约 64–72px。
- 左右 20–24px padding。
- 小圆点 8–10px，可用 navy→amber 渐变。
- 页面名 14–15px / 700 / navy。
- 副标题（文档类型 / 版本号）是**可选**的。对于内容已经很长的报告页，建议只保留主标题一行，避免侧栏顶部过重；副标题里的版本信息可放进 Hero 区的 eyebrow。

### 3.2 Menu 区

- `overflow-y: auto; min-height: 0;`（菜单 11+ 一级、33+ 二级时常超出 1080p 视口，保留滚动能力）。
- **滚动条必须自定义为细窄样式**。Windows Chrome 默认对 `overflow:auto` 的 flex 子项会保留占位式滚动条槽位（即使不溢出也显示一条灰色长条），看起来像 UI bug。规范写法：
  ```css
  .menu{
    overflow-y:auto;
    scrollbar-width:thin;                         /* Firefox */
    scrollbar-color:var(--border) transparent;
  }
  .menu::-webkit-scrollbar{width:6px}
  .menu::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
  .menu::-webkit-scrollbar-thumb:hover{background:var(--ink-light)}
  .menu::-webkit-scrollbar-track{background:transparent}
  ```
  不要直接写 `overflow-y:auto` 不带自定义滚动条样式——会触发 Windows 上的"灰条"问题。
- 上下 padding 12–20px。
- 一级菜单每项最小高度 40px（但 L1>10 个、L2>30 个的报告页可压到 34–36px，让默认折叠状态不溢出）。
- 菜单项横向 padding 12–14px；侧栏整体左右 12px 空隙。

### 3.3 Footer 区

可放"更新时间 / 数据来源 / 版本 / 导出按钮"等弱信息，使用 11–12px `ink-light`。

不要放强 CTA。

**报告型长页面建议不写 Footer。** 来源 / 版本已经在 Hero 区 eyebrow 和正文里反复出现，侧栏底部再贴一段来源说明会分散注意力。如果一定要保留，至少 16px 顶部分隔线与菜单区隔开，并且不要超过两行 11px 字。

## 4. 一级菜单

默认：

```css
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 8px 12px;
  border-radius: 9px;
  color: var(--ink-soft);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: background .2s ease, color .2s ease;
}

.menu-item:hover {
  color: var(--ink-navy);
  background: rgba(26, 43, 73, .035);
}

.menu-item.active {
  color: var(--ink-navy);
  background: var(--ink-navy-soft);
  font-weight: 600;
}
```

可选 active 方案二：背景不变，左侧增加 3px navy 指示线。不要同时使用重背景 + 粗指示线 + 阴影。

## 5. 二级菜单

只有一级项含稳定子章节时才出现。

```css
.submenu {
  margin: 2px 0 8px 20px;
  padding-left: 12px;
  border-left: 1px solid var(--border);
}

.submenu a {
  display: block;
  padding: 7px 10px;
  border-radius: 8px;
  color: var(--ink-light);
  font-size: 12px;
  line-height: 1.4;
}

.submenu a.active {
  color: var(--ink-navy);
  background: rgba(232, 237, 245, .65);
}
```

二级菜单不要使用独立图标，除非业务语义确实需要。

## 6. 展开/收起

- 只有包含二级菜单的一级项显示 chevron。
- 默认：当前章节展开；其他章节可收起。
- **报告型长页面（L1 ≥ 8、L2 ≥ 20）默认全部展开**。理由：(1) 用户的目的就是"快速定位章节"，折叠等于让菜单失去索引价值；(2) 全部展开约 1300px，1080p 视口下用自定义细滚动条即可承载（见 §3.2），不必依赖折叠来"压住高度"。初始化时遍历所有 group 加 `open` class，并把每个 chevron 旋转 90° 朝下。
- 用户手动展开后不要因为轻微滚动马上强制关闭。
- chevron 旋转 90° 即可。

## 7. Scroll Spy

推荐原则：

- section 进入视口上方 20–30% 区域时，切换 active。
- 点击菜单后先更新 active，再平滑滚动。
- 使用 `IntersectionObserver` 优先于高频 `scroll` 事件。
- section 应设置 `scroll-margin-top: 24px`；若移动端有顶部栏，设置为顶部栏高度 + 16px。

**禁止用 `element.offsetTop` 作为 spy 判定的纵坐标**。`offsetTop` 是相对于 `offsetParent`（最近的 `position:relative/absolute/fixed` 祖先），在嵌套容器 + positioned 祖先链下会累加偏移，导致"用户看到的是 A 章节，但侧栏高亮的是同一章节末尾的子项"——这是常见但隐蔽的 bug。
规范做法：每个 `scroll` 事件回调里用 `el.getBoundingClientRect().top`（视口坐标系原点），把"距视口顶部的距离"作为判定基准：

```js
var line = window.innerHeight * 0.3;          // 视口顶部 30% 处
document.querySelectorAll('.sub[id]').forEach(function(s){
  if(s.getBoundingClientRect().top <= line) currentSub = s;
});
```

配合 `requestAnimationFrame` 节流（避免每帧多次触发）和 `manualUntil` 时间锁（点击菜单后 700ms 内不抢答），体验稳定。

## 8. 移动端

≤ 900px：

```css
.sidebar { transform: translateX(-100%); }
.sidebar.open { transform: translateX(0); }
.main { margin-left: 0; }
.mobile-bar { display: flex; }
```

- mobile bar 高度约 56–64px。
- 抽屉宽 `min(84vw, 320px)`。
- 抽屉打开时显示低透明 navy 遮罩。
- ESC / 点击遮罩 / 点击菜单后关闭。
- 保持 body scroll lock，避免抽屉与正文双滚动。

## 9. 菜单命名

优先 2–8 个汉字，使用业务名词：

好：`核心结论`、`用户旅程`、`技术架构`、`风险与验证`

差：`这里很重要`、`更多内容`、`其他`、`Part 1`

二级菜单可更具体，但仍尽量不超过一行。

## 10. 验收

- 一级、二级视觉权重明显不同。
- 侧栏超过屏高时只滚动侧栏菜单，不让整个侧栏消失。
- 主内容有 `margin-left`/grid column 预留，不被遮挡。
- 360px 不保留桌面侧栏。
- active 状态至少通过颜色 + 背景/指示线两种视觉信号之一明确表达。
- 键盘 focus 可见。
