---
inclusion: fileMatch
fileMatchPattern: "frontend/**"
---

# 前端设计规范

## 设计风格

商家后台 + HITL 工作台，深色专业风格。主色调为深灰背景 + 品牌绿色强调色。界面清晰、数据密度适中，适合长时间操作。

## 技术栈

- Next.js App Router（SSR + React Server Components 优先）
- Tailwind CSS（通过 `globals.css` 的 `@theme inline` 定义 token）
- TypeScript strict 模式，禁止 `any`
- 路径别名：`@/` 映射到 `frontend/src/`

## 颜色 Token（唯一来源：`frontend/src/app/globals.css`）

禁止硬编码 hex 颜色，始终使用下方 Tailwind token class。

| Token Class           | 用途                         |
|-----------------------|------------------------------|
| `bg-bg-primary`       | 页面背景、应用外壳            |
| `bg-bg-surface`       | 卡片、下拉框、输入框背景      |
| `bg-bg-surface-dim`   | 嵌套面板、内凹区域            |
| `bg-bg-surface-hover` | 表面元素 hover 状态           |
| `text-accent`         | 主强调色 — 激活导航、高亮     |
| `bg-accent`           | 主按钮、激活标签              |
| `text-text-primary`   | 主文本                        |
| `text-text-secondary` | 次要文本、标签                |
| `text-text-muted`     | 占位符、弱提示文本            |
| `border-border`       | 所有边框                      |
| `text-accent-green`   | 成功状态、正向数值            |

规则：
- 禁止使用 Tailwind 默认色板（`gray-900`、`green-400` 等）
- 错误状态使用 `text-red-400`（暂未 token 化）

## 排版

- 字体：Inter（通过 `next/font/google` 加载）
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

### 卡片与面板

- 标准卡片：`bg-bg-surface border border-border rounded-xl p-5`
- 嵌套面板：`bg-bg-surface-dim rounded-lg p-4`
- 数据表格容器：`bg-bg-surface border border-border rounded-xl overflow-hidden`

### 输入框

- 容器：`bg-bg-surface border border-border rounded-lg h-[40px] flex items-center px-3`
- 占位符：`text-text-muted`
- 聚焦：`focus:border-accent focus:outline-none`

### 表格

- 表头：`text-text-secondary text-[12px] font-medium uppercase tracking-wide`
- 行分隔：`border-b border-border`
- 行 hover：`hover:bg-bg-surface-hover`

### 状态标签（Badge）

- 成功：`bg-green-500/10 text-accent-green text-[12px] px-2 py-0.5 rounded-full`
- 警告：`bg-yellow-500/10 text-yellow-400 text-[12px] px-2 py-0.5 rounded-full`
- 错误：`bg-red-500/10 text-red-400 text-[12px] px-2 py-0.5 rounded-full`
- 默认：`bg-bg-surface-dim text-text-secondary text-[12px] px-2 py-0.5 rounded-full`

## 文件组织

| 类型         | 位置                           |
|--------------|--------------------------------|
| 页面         | `frontend/src/app/`            |
| 共享组件     | `frontend/src/components/`     |
| 工具函数     | `frontend/src/lib/`            |
| 全局样式     | `frontend/src/app/globals.css` |
| 静态资源     | `frontend/public/`             |

- 组件文件：PascalCase（`AccountCard.tsx`、`HitlQueue.tsx`）
- 工具文件：kebab-case（`api-client.ts`、`format-utils.ts`）

## 响应式设计

- 主断点：`lg`（1024px）
- 桌面（`lg+`）：侧边栏可见，主内容区左偏移
- 移动（`< lg`）：侧边栏隐藏，顶部导航全宽

## 规则

1. 优先使用 React Server Components，仅在需要交互（hooks、事件）时加 `"use client"`
2. 禁止使用 CSS Modules、styled-components、Emotion
3. 图标使用内联 SVG，禁止安装图标库（lucide、heroicons 等）
4. API 请求统一通过 `@/lib/api-client.ts` 封装，禁止在组件中直接 fetch
5. 禁止在组件中硬编码 API 路径字符串
