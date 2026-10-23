# Design System — Paper / Navy / Amber

本文件保存视觉层细节。`SKILL.md` 只负责流程；生成页面时按需读取本文件。

## 1. 视觉定位

关键词：**编辑型报告、温暖纸张、专业、克制、研究感、轻学术、低噪声、清晰层级**。

避免：企业后台蓝、科技霓虹、过度玻璃拟态、大面积纯白、强边框、重阴影、满屏渐变。

## 2. 基础颜色 Token

以下数值来自参考页面的核心变量，可直接作为默认值：

```css
:root {
  --ink-navy: #1a2b49;
  --ink-navy-light: #2d4270;
  --ink-navy-soft: #e8edf5;

  --amber-deep: #c47a1f;
  --amber: #e89a3c;
  --amber-light: #f5c97a;
  --amber-soft: #fdf3e3;

  --paper: #faf8f3;
  --paper-dark: #f0ece2;

  --ink: #2a2a2a;
  --ink-soft: #5a5a5a;
  --ink-light: #8a8a8a;
  --border: #e0dbd0;

  --success: #3a7d5a;
  --warning: #c47a1f;

  --shadow-soft: 0 2px 20px rgba(26, 43, 73, 0.06);
  --shadow-card: 0 8px 32px rgba(26, 43, 73, 0.08);
  --shadow-hover: 0 12px 40px rgba(26, 43, 73, 0.12);
}
```

### 色彩职责

| Token | 角色 | 推荐用途 |
|---|---|---|
| `paper` | 主背景 | body、卡片、导航主体 |
| `paper-dark` | 次级背景 | 章节分隔、表格表头、内嵌信息块 |
| `ink-navy` | 结构主色 | 一级标题、active、表头、关键数字 |
| `ink-navy-soft` | 主色弱背景 | active menu、teacher/主角色标签、信息块 |
| `amber-deep` | 强调色 | Eyebrow、重点词、第二角色、风险标签 |
| `amber-soft` | 强调弱背景 | 标签、第二角色卡片、提示块 |
| `ink` | 正文 | 普通正文 |
| `ink-soft` | 次正文 | 描述、辅助信息 |
| `ink-light` | 辅助文字 | 来源、说明、次要 meta，不用于关键正文 |
| `border` | 结构线 | 卡片边界、分隔线、导航分隔 |

### 用色比例

- `paper/paper-dark`：约 65–75%
- `ink/ink-navy`：约 20–30%
- `amber`：约 5–10%

不要追求机械比例；原则是“琥珀负责点亮，不负责铺底”。

## 3. 字体系统

默认字体语义：

```css
body {
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.font-serif {
  font-family: "Noto Serif SC", "Songti SC", "STSong", serif;
}
.font-mono {
  font-family: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
}
```

### 层级

| 层级 | 建议尺寸 | 字重 | 字体 | 色彩 |
|---|---:|---:|---|---|
| Hero Title | `clamp(36px, 5vw, 64px)` | 700 | Serif | navy |
| Section Title | `clamp(28px, 3.5vw, 40px)` | 700 | Serif | navy |
| Card Title | 17–22px | 600–700 | Serif 优先 | navy |
| Body | 13–15px | 400 | Sans | ink / ink-soft |
| Eyebrow | 12–13px | 500 | Sans | amber-deep |
| Meta/Source | 11–12px | 400–500 | Sans/Mono | ink-light |
| Metric Number | 28–36px | 700 | Serif | navy/amber |

正文行高 1.7–1.8。标题行高 1.2–1.35。

## 4. 间距系统

采用 4px 基础网格，不需要把每个数值 Token 化。

推荐高频值：4 / 8 / 10 / 12 / 16 / 20 / 24 / 28 / 32 / 40 / 48 / 60 / 80 / 100。

- 主内容 section：桌面 80–100px 上下；移动端 52–64px。
- 卡片内边距：20 / 24 / 28 / 32px；签名大卡 40–48px。
- 网格 gap：16 / 20 / 24px。
- 标题与描述：12–20px。
- Section Header 与内容：40–60px。

## 5. 圆角

| 场景 | Radius |
|---|---:|
| 小标签/按钮 | 8–10px |
| 普通卡片/表格 | 12–14px |
| 大型签名卡 | 20px |
| Pill/Badge | 20px 或 999px |
| Avatar | 50% |

避免同一屏出现 6 种以上圆角。

## 6. 阴影

阴影必须偏 navy、低透明：

- 普通页面尽量无阴影或 `shadow-soft`。
- 重点容器用 `shadow-card`。
- hover 才升级到 `shadow-hover`。
- 不使用纯黑 20%+ 的重阴影。

## 7. 背景与渐变

允许：

```css
background: linear-gradient(180deg, #f5f7fb 0%, var(--paper) 100%);
background: linear-gradient(180deg, var(--amber-soft) 0%, var(--paper) 100%);
background: linear-gradient(135deg, var(--ink-navy-soft), var(--paper));
```

渐变只用于：角色对照、关键 Header、小面积品牌标记。不要用作整页大背景。

## 8. 边框与分隔线

- 卡片边框：`1px solid var(--border)`。
- 表格行分隔：1px border。
- 引用/结论块：左侧 2–3px navy 或 amber。
- Section 不要全部框起来；靠留白和背景层次划分。

## 9. 动效

```css
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

推荐：
- hover transition：0.2–0.3s。
- 卡片 hover：`translateY(-2px)` 或 `-3px`。
- 入场：0.5–0.6s；大面积 section 级别使用。
- menu chevron：旋转 90°，0.2s。

必须支持：

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

## 10. 内容宽度

- 参考视觉的主体最大宽度约 1200–1440px。
- 改为左侧栏后：主内容外层用 `width:100%; max-width:1440px; margin:0 auto; padding:0 8px; box-sizing:border-box`。**不要**写成 `min(1200px, calc(100% - 64px))`——后者会在宽屏留下大段左右空白，并让 `.alt` 章节的 `paper-dark` 背景被截断（详见 component-patterns §14"全宽背景"）。
- 长文本阅读列建议 640–760px（由卡片/正文容器自身约束，不要靠主容器缩小来实现）。
- 表格/网格可占满内容容器。

## 11. 可替换规则

当用户有品牌规范时：

1. 先替换 `ink-navy` 为品牌主色。
2. 生成 `main-light/main-soft` 两个低饱和衍生色。
3. 保留 `paper` 系背景，除非品牌要求纯白/深色。
4. 检查 active、表头、按钮的文字对比度。
5. amber 若与品牌冲突，可替换为品牌辅助色，但仍保持“小面积强调”职责。
