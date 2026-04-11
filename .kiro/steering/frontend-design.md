---
inclusion: fileMatch
fileMatchPattern: "frontend/**"
---

# 前端设计规范

## 设计风格

商家后台 + HITL 工作台，浅色米粉色调。主色调为极浅粉背景 + 粉色强调色（#FF6B8A）。界面柔和、配色温暖，适合长时间操作，营造轻松专业的视觉体验。

## 技术栈

- Next.js App Router（SSR + React Server Components 优先）
- Tailwind CSS（通过 `globals.css` 的 `@theme inline` 定义 token）
- TypeScript strict 模式，禁止 `any`
- 路径别名：`@/` 映射到 `frontend/`

## 颜色 Token（唯一来源：`frontend/app/globals.css`）

禁止硬编码 hex 颜色，始终使用下方 Tailwind token class。

| Token Class           | 色值                        | 用途                         |
|-----------------------|-----------------------------|------------------------------|
| `bg-bg-primary`       | `#FFF5F5`（极浅粉）         | 页面背景、应用外壳            |
| `bg-bg-surface`       | `#FFFFFF`（白色）            | 卡片、下拉框、侧边栏背景      |
| `bg-bg-surface-dim`   | `#FFF0F0`（浅粉）           | 嵌套面板、内凹区域            |
| `bg-bg-surface-hover` | `#FFE8E8`（hover 粉）       | 表面元素 hover 状态           |
| `text-accent`         | `#FF6B8A`（粉色）           | 主强调色 — 激活导航、高亮     |
| `bg-accent`           | `#FF6B8A`（粉色）           | 主按钮、激活标签、开关激活态   |
| `text-accent-secondary` | `#FF8FA3`（次粉色）       | 渐变终点、次强调              |
| `text-text-primary`   | `#1A1A2E`（深色）           | 主文本                        |
| `text-text-secondary` | `#6B7280`（灰色）           | 次要文本、标签                |
| `text-text-muted`     | `rgba(26, 26, 46, 0.4)`    | 占位符、弱提示文本            |
| `border-border`       | `#F0E0E0`（浅粉灰）        | 所有边框                      |
| `text-accent-green`   | `#22C55E`（绿色）           | 成功状态、正向数值            |

规则：
- 禁止使用 Tailwind 默认色板（`gray-900`、`green-400` 等）
- 错误状态使用 `text-red-400`（暂未 token 化）

## 排版

- 字体：Inter（通过 `next/font/google` 加载）+ 系统默认中文字体
- 正文：`text-[14px]` 或 `text-[16px]`
- 标签/次要：`text-[12px]` 或 `text-[13px]`
- 标题：`text-[20px] font-semibold` 或 `text-[24px] font-semibold`
- 字重：400 / 500 / 600 / 700

## 间距与布局

| 元素           | 值                                          |
|----------------|---------------------------------------------|
| 侧边栏宽度     | `w-[240px]`（固定左侧，`lg` 以下隐藏）      |
| 顶部导航高度   | `h-[64px]`                                  |
| 主内容区       | `lg:ml-[240px] mt-[64px]`                   |
| 页面内边距     | `px-6`（24px）标准                          |
| 组件间距       | `gap-4`（16px）标准                         |
| 卡片内边距     | `p-5` 或 `p-6`                              |

## 组件规范

### 按钮

| 变体       | Classes                                                                                      |
|------------|----------------------------------------------------------------------------------------------|
| 主要操作   | `bg-accent text-white font-semibold text-[14px] px-5 h-[40px] rounded-lg hover:brightness-110 transition` |
| 次要操作   | `bg-bg-surface text-text-primary font-medium text-[14px] px-5 h-[40px] rounded-lg hover:bg-bg-surface-hover transition-colors border border-border` |
| 危险操作   | `bg-red-500/10 text-red-400 font-medium text-[14px] px-5 h-[40px] rounded-lg hover:bg-red-500/20 transition-colors` |

- 标准高度：`h-[40px]`
- 圆角：`rounded-lg`（8px）
- 主按钮粉色背景（`bg-accent`），hover 时亮度微增，文字白色

### 卡片与面板

- 标准卡片：`bg-bg-surface border border-border rounded-xl p-5`
- 大圆角卡片：`bg-bg-surface rounded-2xl shadow-lg p-6`（登录卡片等独立场景）
- 嵌套面板：`bg-bg-surface-dim rounded-lg p-4`
- 数据表格容器：`bg-bg-surface border border-border rounded-xl overflow-hidden`
- 卡片使用白色背景、大圆角（12-16px）、轻微阴影，营造柔和层次感

### 输入框

- 容器：`bg-bg-surface-dim border border-border rounded-lg h-[40px] flex items-center px-3`
- 占位符：`text-text-muted`
- 聚焦：`focus:border-accent focus:outline-none`（聚焦时边框变为粉色）

### 开关组件

- 激活态使用粉色（`bg-accent`）
- 未激活态使用浅灰色

### 表格

- 表头：`text-text-secondary text-[12px] font-medium uppercase tracking-wide`
- 行分隔：`border-b border-border`
- 行 hover：`hover:bg-bg-surface-hover`

### 状态标签（Badge）

- 成功：`bg-green-500/10 text-accent-green text-[12px] px-2 py-0.5 rounded-full`
- 警告：`bg-yellow-500/10 text-yellow-400 text-[12px] px-2 py-0.5 rounded-full`
- 错误：`bg-red-500/10 text-red-400 text-[12px] px-2 py-0.5 rounded-full`
- 默认：`bg-bg-surface-dim text-text-secondary text-[12px] px-2 py-0.5 rounded-full`

### 侧边栏

- 背景：白色（`bg-bg-surface`），右侧边框（`border-r border-border`）
- 导航项激活态：左侧 3px 粉色指示条 + 粉色文字（`text-accent`）+ 浅粉背景（`bg-accent/10`）
- 导航项默认态：灰色文字（`text-text-secondary`），hover 时浅粉背景

## 文件组织

| 类型         | 位置                        |
|--------------|-----------------------------|
| 页面         | `frontend/app/`             |
| 共享组件     | `frontend/components/`      |
| 工具函数     | `frontend/lib/`             |
| 全局样式     | `frontend/app/globals.css`  |
| 静态资源     | `frontend/public/`          |

- 组件文件：PascalCase（`AccountCard.tsx`、`HitlQueue.tsx`）
- 工具文件：kebab-case（`api-client.ts`、`format-utils.ts`）

## 响应式设计

- 主断点：`lg`（1024px）
- 桌面（`lg+`）：侧边栏可见，主内容区左偏移
- 移动（`< lg`）：侧边栏隐藏，顶部导航全宽，包含横向滚动导航

## 规则

1. 优先使用 React Server Components，仅在需要交互（hooks、事件）时加 `"use client"`
2. 禁止使用 CSS Modules、styled-components、Emotion
3. 图标使用内联 SVG，禁止安装图标库（lucide、heroicons 等）
4. API 请求统一通过 `@/lib/api-client.ts` 封装，禁止在组件中直接 fetch
5. 禁止在组件中硬编码 API 路径字符串
6. 禁止硬编码 hex 颜色值，始终使用 token class（如 `bg-accent`、`text-text-primary`）
