# Implementation Plan: 前端框架与扫码登录

## Overview

按组件粒度逐步搭建前端：先替换色彩体系，再逐个实现独立组件，最后组装到页面和 layout 中。每个 task 产出一个可独立验证的组件或模块。

## Tasks

- [x] 1. 替换全局色彩体系为米粉色调
  - [x] 1.1 更新 `frontend/app/globals.css` 中的 `@theme inline` token
    - 替换所有颜色变量为米粉色调（见 design.md 色彩 Token 表）
    - `--color-bg-primary`: `#FFF5F5`（极浅粉背景）
    - `--color-bg-surface`: `#FFFFFF`（白色卡片）
    - `--color-bg-surface-dim`: `#FFF0F0`（嵌套面板）
    - `--color-bg-surface-hover`: `#FFE8E8`（hover 态）
    - `--color-accent`: `#FF6B8A`（粉色强调）
    - `--color-accent-secondary`: `#FF8FA3`（次强调）
    - `--color-text-primary`: `#1A1A2E`（深色主文本）
    - `--color-text-secondary`: `#6B7280`（次要文本）
    - `--color-text-muted`: `rgba(26, 26, 46, 0.4)`（占位符）
    - `--color-border`: `#F0E0E0`（浅粉灰边框）
    - `--color-accent-green`: `#22C55E`（成功状态）
    - 更新 `body` 背景色和文字色
    - 更新滚动条样式适配浅色主题
    - _Requirements: F3.1_

- [x] 2. 实现认证状态管理模块
  - [x] 2.1 创建 `frontend/lib/auth-context.ts` — AuthContext 定义
    - 定义 `AuthState` 类型：`{ token: string | null; user: UserInfo | null; isLoading: boolean }`
    - 定义 `AuthContextValue` 类型：`AuthState` + `login(token: string, user: UserInfo): void` + `logout(): void`
    - 导出 `AuthContext` 和 `useAuth` hook
    - `UserInfo` 类型：`{ nickname: string; avatar: string | null; xhs_user_id: string }`
    - _Requirements: F4.1, F4.2_
  - [x] 2.2 创建 `frontend/components/AuthProvider.tsx` — 认证状态 Provider
    - `"use client"` 组件
    - 初始化时从 `localStorage` 读取 JWT，解析 payload 获取用户信息
    - 提供 `login()` 方法：存储 JWT 到 localStorage，更新 context state
    - 提供 `logout()` 方法：清除 localStorage JWT，重定向到 `/login`
    - 检查 JWT 过期时间（`exp` 字段），过期时自动调用 `logout()`
    - 渲染 `AuthContext.Provider` 包裹 `children`
    - _Requirements: F4.1, F4.2, F4.3_
  - [x] 2.3 更新 `frontend/lib/api-client.ts` — 注入认证头 + 401 拦截
    - 在 `request()` 函数中从 `localStorage` 读取 JWT，自动添加 `Authorization: Bearer <token>` 头
    - 当响应状态码为 401 时，清除 localStorage JWT 并 `window.location.href = "/login"`
    - 保持现有的 `apiClient.get/post/put/delete` 接口不变
    - _Requirements: F4.3, F4.4_

- [x] 3. 实现扫码登录页组件
  - [x] 3.1 创建 `frontend/components/QrLoginCard.tsx` — 扫码登录卡片
    - `"use client"` 组件
    - Props：无（内部管理所有状态）
    - 内部状态：`qrImage: string | null`、`sessionId: string | null`、`status: "loading" | "waiting" | "success" | "expired" | "error"`
    - 组件挂载时调用 `apiClient.post("/api/v1/accounts/qr-login/start")` 获取二维码
    - 获取成功后设置 `qrImage`（base64）和 `sessionId`，状态变为 `waiting`
    - 启动 3 秒间隔的轮询 `apiClient.get("/api/v1/accounts/qr-login/status?session_id=xxx")`
    - 轮询结果处理：
      - `waiting` → 继续轮询
      - `success` → 调用 `useAuth().login(token, user)`，然后 `router.push("/dashboard")`
      - `expired` → 停止轮询，状态变为 `expired`，展示"刷新二维码"按钮
    - 组件卸载时清除轮询 interval
    - UI 结构：
      - 品牌 Logo（粉色心形 SVG + "RedFlow" 文字）
      - "扫码登录" 标题（`text-[24px] font-semibold`）
      - 二维码图片区域（200x200，`rounded-xl`）
        - loading 态：灰色骨架屏 + spinner
        - waiting 态：`<img src="data:image/png;base64,{qrImage}" />`
        - expired 态：二维码上覆盖半透明遮罩 + "已过期" 文字 + 刷新按钮
        - error 态：错误提示 + 重试按钮
      - 底部提示文字："请使用小红书 App 扫码"（`text-text-secondary text-[14px]`）
    - 卡片样式：`bg-white rounded-2xl shadow-lg p-8 w-[400px]`
    - _Requirements: F1.1, F1.2, F1.3, F1.4, F1.5, F1.6_

- [x] 4. 实现主布局组件
  - [x] 4.1 创建 `frontend/components/AuthGuard.tsx` — 认证守卫
    - `"use client"` 组件
    - Props：`{ children: React.ReactNode }`
    - 使用 `useAuth()` 获取认证状态
    - `isLoading` 为 true 时渲染全屏 loading（居中 spinner + 米粉背景）
    - `token` 为 null 时调用 `router.push("/login")` 并返回 null
    - `token` 有效时渲染 `children`
    - _Requirements: F1.1, F2.7_
  - [x] 4.2 重写 `frontend/components/Sidebar.tsx` — 米粉色调侧边栏
    - `"use client"` 组件
    - 顶部：品牌 Logo 区域（粉色心形 SVG + "RedFlow" 文字，`h-[64px]`）
    - 导航项列表：数据看板、账号管理、内容管理、实时会话、HITL 审核、告警中心
    - 每个导航项包含：图标（内联 SVG）+ 文字标签
    - 激活态样式：左侧 3px 粉色指示条 + 粉色文字 + 浅粉背景（`bg-accent/10 text-accent`）
    - 默认态样式：灰色文字（`text-text-secondary`），hover 时浅粉背景
    - 侧边栏背景：白色（`bg-bg-surface`），右侧边框（`border-r border-border`）
    - 固定定位：`fixed left-0 top-0 h-full w-[240px]`
    - 移动端隐藏：`hidden lg:flex`
    - 每个导航项配一个简单的内联 SVG 图标（首页、用户、文件、消息、审核、铃铛）
    - _Requirements: F2.1, F2.2, F2.3, F2.8_
  - [x] 4.3 创建 `frontend/components/UserMenu.tsx` — 用户菜单
    - `"use client"` 组件
    - 使用 `useAuth()` 获取用户信息
    - 展示用户头像（32x32 圆形，无头像时显示昵称首字 + 粉色背景）+ 昵称
    - 点击展开下拉菜单（绝对定位，白色卡片 + 阴影）
    - 菜单项："退出登录"（点击调用 `useAuth().logout()`）
    - 点击外部区域关闭菜单
    - _Requirements: F2.4, F2.5, F2.6_
  - [x] 4.4 重写 `frontend/components/TopNav.tsx` — 米粉色调顶部导航
    - `"use client"` 组件
    - 左侧：移动端 Logo（`lg:hidden`）
    - 中间：移动端横向滚动导航（`lg:hidden`，复用 Sidebar 的导航项数据）
    - 右侧：`<UserMenu />` 组件
    - 背景：白色（`bg-bg-surface`），底部边框（`border-b border-border`）
    - 固定定位：`fixed top-0 left-0 lg:left-[240px] right-0 h-[64px]`
    - _Requirements: F2.1, F2.4, F2.8_

- [x] 5. 组装页面与 Layout
  - [x] 5.1 重写 `frontend/app/layout.tsx` — 根 Layout（纯净壳）
    - 只包含 `<html>`、`<body>`、Inter 字体加载、`globals.css` 引入
    - 用 `<AuthProvider>` 包裹 `{children}`
    - 不包含 Sidebar、TopNav 或任何业务 UI
    - _Requirements: F2.7_
  - [x] 5.2 创建 `frontend/app/login/page.tsx` — 扫码登录页面
    - 全屏米粉渐变背景：`min-h-screen bg-gradient-to-br from-[#FFE0E6] via-[#FFF5F5] to-white`
    - 居中布局：`flex items-center justify-center`
    - 渲染 `<QrLoginCard />`
    - 如果用户已登录（`useAuth().token` 存在），直接 `router.push("/dashboard")`
    - _Requirements: F1.1, F1.7_
  - [x] 5.3 创建 `frontend/app/(dashboard)/layout.tsx` — 主应用 Layout
    - 用 `<AuthGuard>` 包裹整个 layout
    - 渲染 `<Sidebar />` + `<TopNav />` + `<main>` 内容区
    - `<main>` 样式：`lg:ml-[240px] mt-[64px] min-h-screen bg-bg-primary`
    - _Requirements: F2.1, F2.7_
  - [x] 5.4 迁移现有页面到 `(dashboard)` Route Group
    - 将 `frontend/app/dashboard/page.tsx` 移动到 `frontend/app/(dashboard)/dashboard/page.tsx`
    - 将 `frontend/app/accounts/page.tsx` 移动到 `frontend/app/(dashboard)/accounts/page.tsx`
    - 将 `frontend/app/content/page.tsx` 移动到 `frontend/app/(dashboard)/content/page.tsx`
    - 将 `frontend/app/conversations/page.tsx` 移动到 `frontend/app/(dashboard)/conversations/page.tsx`
    - 将 `frontend/app/hitl/page.tsx` 移动到 `frontend/app/(dashboard)/hitl/page.tsx`
    - 将 `frontend/app/alerts/page.tsx` 移动到 `frontend/app/(dashboard)/alerts/page.tsx`
    - 更新 `frontend/app/page.tsx` 保持重定向到 `/dashboard`
    - _Requirements: F2.1_

- [ ] 6. 更新前端设计规范 Steering 文件
  - [ ] 6.1 更新 `.kiro/steering/frontend-design.md`
    - 将设计风格从"深色专业风格"改为"浅色米粉色调"
    - 更新所有颜色 Token 表为新的米粉色值
    - 更新按钮、卡片、输入框等组件规范的配色描述
    - _Requirements: F3.1, F3.2, F3.3, F3.4, F3.5, F3.6_

- [ ] 7. Checkpoint — 验证端到端流程
  - 启动前端 dev server，验证：
    - 访问 `/` 重定向到 `/dashboard`，未登录时跳转到 `/login`
    - `/login` 页面展示米粉渐变背景 + 白色扫码卡片
    - 二维码加载、展示、过期刷新功能正常
    - 登录成功后跳转到 `/dashboard`，Sidebar 和 TopNav 正常渲染
    - 用户头像和昵称展示正确，退出登录功能正常
    - 移动端 Sidebar 隐藏，TopNav 全宽
  - Ensure all flows work, ask the user if questions arise.

## Notes

- 后端需要新增无需认证的扫码登录 API（当前 qr-login 接口需要 JWT），这是一个后端改动点，不在本 spec 范围内，需要单独处理
- 所有组件使用 Tailwind CSS class，禁止硬编码 hex 颜色
- 图标使用内联 SVG，不安装图标库
- API 请求统一通过 `lib/api-client.ts`
