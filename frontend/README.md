# 💔 ex-skill Frontend

基于 Next.js 16 (Turbopack) 的前端应用。与 ex-skill 后端 API 配合使用。

## 技术栈

- **Next.js 16** (App Router, Turbopack)
- **React 19**
- **TypeScript 5**
- **Tailwind CSS 4**
- **shadcn/ui** — UI 组件库
- **lucide-react** — 图标

## 快速开始

```bash
npm install
npm run dev
```

访问 `http://localhost:3000`。

> 需要后端 API 在 `http://localhost:8000` 运行。前端通过 `next.config.ts` 中的 `rewrites` 将 `/api/*` 代理到后端。

## 项目结构

```
src/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # 根布局（Header + 全局导航）
│   ├── page.tsx                  # 首页：Persona 卡片列表
│   ├── globals.css               # 全局样式 + Tailwind
│   ├── upload/
│   │   └── page.tsx              # 新建 Persona 表单
│   └── personas/
│       └── [id]/
│           ├── page.tsx          # Persona 详情页
│           │                     #   - 5层人格画像 Tabs
│           │                     #   - 记忆列表（分页加载）
│           │                     #   - 源文件管理 + 上传
│           │                     #   - 提取进度展示
│           │                     #   - 触发提取 / 清除重提取
│           └── chat/
│               └── page.tsx      # 对话界面
│                                 #   - SSE 流式渲染
│                                 #   - 重新生成 / 删除消息
│                                 #   - 加载骨架屏
├── components/ui/                # shadcn/ui 组件
│   ├── button.tsx
│   ├── card.tsx
│   ├── input.tsx
│   ├── badge.tsx
│   ├── tabs.tsx
│   ├── progress.tsx
│   ├── skeleton.tsx
│   ├── separator.tsx
│   └── label.tsx
└── lib/
    ├── api.ts                    # API 客户端
    │                             #   - personaApi: Persona CRUD
    │                             #   - uploadApi: 文件上传 + 进度
    │                             #   - extractionApi: 触发提取 + 状态
    │                             #   - memoryApi: 记忆 CRUD
    │                             #   - chatApi: 会话 + 消息 + 删除
    │                             #   - streamChat(): SSE 流式接收
    └── utils.ts                  # cn() classname 合并
```

## 页面说明

### 首页 `/`

- 展示所有 Persona 的卡片网格
- 每个卡片：名称、状态标签、标签、操作按钮
- 空状态引导创建第一个 Persona
- 加载状态：骨架屏

### 新建 Persona `/upload`

- 表单：名称（英文 ID）+ 显示名称
- 创建成功后跳转到详情页

### Persona 详情 `/personas/[id]`

- 顶部：名称、状态 Badge、操作按钮组
- 5 个 Tabs：
  - **硬规则** — 底线和行为边界
  - **身份特征** — 自我描述、MBTI、星座等
  - **说话风格** — 语气、用词、表情包习惯
  - **情感模式** — 依恋类型、冲突处理方式
  - **关系行为** — 对你的昵称、态度、典型开场白
- **💾 记忆** Tab — 记忆列表，分类标签 + 重要性评分 + 分页
- **📁 源文件** Tab — 上传文件列表 + 上传新文件面板
- 提取进度条（进行中时显示）
- 操作：触发提取、清除并重新提取、删除 Persona、开始对话

### 对话 `/personas/[id]/chat`

- 顶部 Header：返回按钮 + Persona 名称 + 状态
- 消息列表：用户消息（右对齐，蓝色气泡）、AI 消息（左对齐，灰色气泡）
- 流式输出：逐 token 渲染 + 闪烁光标
- 加载状态：三个跳动圆点
- 消息操作（悬停显示）：
  - AI 消息左侧：🔄 重新生成 / ✕ 删除
  - 用户消息右侧：✕ 删除
  - 重新生成仅在最后一条 AI 消息上显示
- 底部输入框：Enter 发送、Shift+Enter 换行
- 错误处理：错误横幅 + 关闭按钮
- 空状态引导

## API 客户端 (`lib/api.ts`)

```typescript
// Persona
personaApi.list(status?, page, pageSize)
personaApi.get(id)
personaApi.create(name, displayName?)
personaApi.update(id, data)
personaApi.delete(id)

// Upload
uploadApi.upload(personaId, file, fileType)
uploadApi.status(taskId)
uploadApi.list(personaId)

// Extraction
extractionApi.extractAll(personaId)
extractionApi.status(personaId)

// Memory
memoryApi.list(personaId, category?, page, pageSize)
memoryApi.create(personaId, data)
memoryApi.delete(memoryId)
memoryApi.deleteAll(personaId)

// Chat
chatApi.sessions(personaId)
chatApi.createSession(personaId, title?)
chatApi.messages(conversationId)
chatApi.deleteSession(conversationId)
chatApi.deleteMessage(messageId)

// Streaming
streamChat(personaId, content, onToken, onDone, onError)
// 返回 AbortController，用于取消请求
```

## 开发

```bash
npm run dev     # 开发服务器 (Turbopack)
npm run build   # 生产构建
npm run start   # 生产运行
npm run lint    # ESLint
```
