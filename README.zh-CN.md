# 💔 ex-skill — 把前任蒸馏成 AI

导入微信/QQ 聊天记录，用 AI 提取一个人的人格画像，然后跟"ta"聊天。

## 项目简介

ex-skill 是一个全栈 AI 应用，核心流程分三步：

1. **上传聊天记录** — 导入你和某个人的微信/QQ 聊天导出文件（.txt）
2. **AI 提取人格** — LLM 分析聊天内容，提取 5 层人格画像 + 共同回忆
3. **对话** — 用这个 AI 人格跟你聊天，语气、情感、说话方式都像 ta

## 技术架构

```
ex-skill-fullstack/
├── backend/          FastAPI + SQLAlchemy + SQLite
└── frontend/         Next.js 16 (Turbopack) + shadcn/ui + Tailwind CSS
```

```
┌─────────────┐     SSE Streaming     ┌────────────────┐
│   Next.js   │ ◄───────────────────► │    FastAPI     │
│  前端 :3000  │     REST API          │   后端 :8000    │
└─────────────┘                       └───────┬────────┘
                                              │
                                    ┌─────────┴────────┐
                                    │  LLM Provider    │
                                    │  DeepSeek/Claude │
                                    │  /OpenAI         │
                                    └──────────────────┘
```

### 后端技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI (异步) |
| ORM | SQLAlchemy 2.0 async |
| 数据库 | SQLite (开发) / PostgreSQL + pgvector (生产) |
| LLM | DeepSeek / Claude / OpenAI，支持切换 |
| Embedding | OpenAI text-embedding-3-small / Voyage AI |
| 流式响应 | SSE (Server-Sent Events) |
| 聊天解析 | 微信 .txt / QQ .txt 格式 |

### 前端技术栈

| 组件 | 技术 |
|------|------|
| 框架 | Next.js 16 (App Router, Turbopack) |
| UI 库 | shadcn/ui |
| 样式 | Tailwind CSS 4 |
| 状态管理 | React useState / useCallback |
| 流式接收 | Fetch API + ReadableStream (SSE) |

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- LLM API Key（DeepSeek 推荐，便宜好用）

### 1. 配置环境变量

```bash
cd backend
```

创建 `backend/.env`：

```env
# 必填：LLM API Key（至少配一个）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

# 可选：Embedding API（不配也能用，会用关键词匹配降级）
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

后端运行在 `http://localhost:8000`，交互式 API 文档在 `http://localhost:8000/docs`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://localhost:3000`。

> **代理配置**：前端 `next.config.ts` 需配置 rewrites 将 `/api/*` 代理到后端：
> ```ts
> async rewrites() {
>   return [{ source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' }]
> }
> ```

---

## 项目结构

### 后端

```
backend/
├── app/
│   ├── main.py                # FastAPI 应用入口
│   ├── config.py              # 环境变量配置 (pydantic-settings)
│   ├── database.py            # 数据库引擎 & session 工厂
│   ├── models/
│   │   └── __init__.py        # SQLAlchemy 数据模型
│   ├── schemas/
│   │   └── __init__.py        # Pydantic 请求/响应模型
│   ├── routers/
│   │   ├── health.py          # GET  /api/health
│   │   ├── persona.py         # CRUD /api/personas
│   │   ├── upload.py          # POST /api/personas/{id}/upload
│   │   ├── extraction.py      # POST /api/personas/{id}/extract/all
│   │   ├── memory.py          # CRUD /api/personas/{id}/memories
│   │   └── chat.py            # POST /api/personas/{id}/chat (SSE)
│   ├── services/
│   │   ├── chat_service.py    # 对话服务 (RAG + 系统提示词构建)
│   │   ├── extraction.py      # 人格 & 记忆提取编排
│   │   ├── embedding_service.py # 向量嵌入 & 相似度搜索
│   │   ├── llm_client.py      # LLM API 客户端 (httpx)
│   │   ├── persona_service.py # 人格 CRUD 业务逻辑
│   │   └── parser/
│   │       ├── base.py        # 解析器基类
│   │       ├── wechat.py      # 微信 .txt 解析
│   │       └── qq.py          # QQ .txt 解析
│   ├── chains/
│   │   ├── base.py            # LLM & Embedding 工厂函数
│   │   ├── persona_chain.py   # 人格提取链 (5层模型)
│   │   ├── memory_chain.py    # 记忆提取链 (6类记忆)
│   │   └── correction_chain.py # 用户纠正链
│   └── utils/
│       ├── chunking.py        # 聊天记录分块策略
│       └── normalization.py   # 消息格式统一化
├── data/uploads/              # 上传文件存储
├── requirements.txt
└── pyproject.toml
```

### 前端

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # 根布局
│   │   ├── page.tsx                # 首页 (Persona 列表)
│   │   ├── globals.css
│   │   ├── upload/page.tsx         # 新建 Persona + 上传
│   │   └── personas/[id]/
│   │       ├── page.tsx            # Persona 详情 (5层画像 + 记忆)
│   │       └── chat/page.tsx       # 对话界面 (SSE 流式)
│   ├── components/ui/              # shadcn/ui 组件
│   └── lib/
│       ├── api.ts                  # API 客户端 + SSE streamChat
│       └── utils.ts                # cn() 工具函数
├── package.json
└── tsconfig.json
```

---

## 人格五层模型

AI 从聊天记录中提取 5 个层次的人格画像：

| 层级 | 字段 | 内容 |
|------|------|------|
| **硬规则** | `hard_rules` | 底线、不可触碰的原则、绝对不能说的话 |
| **身份特征** | `identity` | MBTI、星座、年龄、职业、自我描述 |
| **说话风格** | `speaking_style` | 语气、用词、句长、标点习惯、表情包使用 |
| **情感模式** | `emotional_patterns` | 依恋类型、爱的语言、冲突处理、情绪触发点 |
| **关系行为** | `relational_behavior` | 对你的昵称、对你的态度、典型开场白/告别语 |

---

## 记忆提取（6 类）

| 类别 | 说明 |
|------|------|
| `shared_experience` | 共同经历（旅行、活动） |
| `date` | 重要日期（纪念日、第一次约会） |
| `inside_joke` | 内部梗、只有你们懂的玩笑 |
| `argument` | 吵架、冲突及解决方式 |
| `sweet_moment` | 甜蜜时刻、浪漫互动 |
| `timeline_event` | 关系时间线关键节点 |

---

## 对话 RAG 流程

每次对话时，系统会：

1. **检索** — 用用户消息做相似度搜索，从 `memory_chunks` 中召回最相关的 top-12 条记忆
2. **构建提示词** — 将 5 层人格 + 检索到的记忆 + 反幻觉规则拼成系统提示词
3. **流式生成** — 调用 LLM 流式返回，前端实时渲染
4. **保存** — 用户消息和 AI 回复都存入数据库

### 反幻觉机制

- 系统提示词中明确区分"性格/情绪可以自由表达"和"事实信息只能从回忆获取"
- 温度降至 0.3 减少创造性编造
- 低质量检索结果（平均相似度 < 0.08）会触发警告："以上回忆与当前话题关联度较低，不要强行引用"

---

## 完整 API 接口

### 健康检查
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |

### Persona 管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/personas` | 列表（支持 `status`/`page`/`page_size` 参数） |
| POST | `/api/personas` | 创建（`name` + `display_name`） |
| GET | `/api/personas/{id}` | 详情（含 5 层画像数据） |
| PATCH | `/api/personas/{id}` | 更新画像层 |
| DELETE | `/api/personas/{id}` | 删除（级联删除记忆、对话等） |

### 上传 & 解析
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/personas/{id}/upload?file_type=wechat\|qq` | 上传聊天文件，后台解析 |
| GET | `/api/personas/{id}/uploads` | 上传文件列表 |
| GET | `/api/upload/{task_id}/status` | 解析进度查询 |

### AI 提取
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/personas/{id}/extract/persona` | 仅提取人格 |
| POST | `/api/personas/{id}/extract/memories` | 仅提取记忆 |
| POST | `/api/personas/{id}/extract/all` | 全量提取（人格 + 记忆） |
| GET | `/api/personas/{id}/extract/status` | 提取进度查询 |

### 记忆管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/personas/{id}/memories` | 记忆列表（支持分类筛选 + 分页） |
| GET | `/api/memories/{id}` | 单条记忆详情 |
| POST | `/api/personas/{id}/memories` | 手动创建记忆 |
| PATCH | `/api/memories/{id}` | 更新记忆 |
| DELETE | `/api/memories/{id}` | 删除单条记忆 |
| DELETE | `/api/personas/{id}/memories` | 删除全部记忆（重新提取前用） |
| POST | `/api/personas/{id}/memories/search` | 向量相似度搜索 |

### 对话
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/personas/{id}/conversations` | 对话会话列表 |
| POST | `/api/personas/{id}/conversations` | 创建新会话 |
| GET | `/api/conversations/{id}/messages` | 消息历史 |
| POST | `/api/personas/{id}/chat` | **发送消息 (SSE 流式响应)** |
| DELETE | `/api/conversations/{id}` | 删除整个会话 |
| DELETE | `/api/messages/{id}` | 删除单条消息 |
| POST | `/api/conversations/{id}/correct` | 纠正 AI 回复（更新人格层） |

### SSE 事件格式

`POST /api/personas/{id}/chat` 返回的流式事件：

```json
// 思考阶段
{"type": "thinking", "stage": "generating"}

// 逐 token 输出
{"type": "token", "token": "好"}

// 完成
{"type": "done", "full_text": "好啊，最近在干嘛？", "message_id": "uuid", "retrieved_memories": [...]}

// 错误
{"type": "error", "message": "错误原因"}
```

---

## 使用指南

### 第一步：创建 Persona

1. 打开 `http://localhost:3000`
2. 点击右上角 **"+ 新建 Persona"**
3. 填写：
   - **名称**（英文 ID，如 `yun-meng-ze`）
   - **显示名称**（中文昵称，如 `云梦泽`）
4. 点击创建

### 第二步：上传聊天记录

1. 进入 Persona 详情页
2. 切换到 **"📁 源文件"** 标签
3. 点击 **"📁 上传更多记录"**
4. 选择来源类型（微信 / QQ）
5. 选择导出的 `.txt` 文件
6. 点击 **"开始上传并提取"**

#### 如何导出聊天记录？

**微信**：聊天窗口 → 右上角 `...` → 更多 → 导出聊天记录 → 保存为 `.txt`

**QQ**：聊天窗口 → 右上角 `≡` → 导出消息记录 → 选择 `.txt` 格式

### 第三步：等待 AI 提取

上传后系统自动执行，进度条会展示各阶段：

1. **解析** → 识别每条消息的发送者、内容、时间戳
2. **提取人格** → LLM 分析 5 层画像
3. **提取记忆** → LLM 识别 6 类共同回忆
4. **向量化** → 生成 embedding 用于 RAG 检索

进度条走完、状态变为 **"就绪"** 后即可对话。

### 第四步：开始对话

1. 点击 **"💬 开始对话"**
2. 像正常聊天一样发消息，Enter 发送
3. AI 会用 ta 的语气回复，自然地提到共同回忆

### 对话功能

| 操作 | 方式 |
|------|------|
| 发送消息 | 输入框 + Enter（Shift+Enter 换行） |
| 重新生成 | 鼠标悬停最后一条 AI 回复 → 点击 🔄 |
| 删除消息 | 鼠标悬停任意消息 → 点击 ✕ |
| 返回 | 点击左上角 ← 返回 |

> **重新生成**只在最后一条 AI 消息上显示，避免破坏对话上下文。删除消息会同步删除后端数据。

---

## Embedding 降级策略

当没有配置 Embedding API 时，系统自动降级：

| 模式 | 机制 | 效果 |
|------|------|------|
| 伪向量 | 字符 bigram + 单词 MD5 哈希 → 1536 维稀疏向量 | 有基础检索能力 |
| 关键词搜索 | Jaccard 相似度（bigram + 词语重叠） | 精确匹配可以，泛化弱 |
| 低质量告警 | 平均相似度 < 0.08 时提示词警告 AI | 防止强行引用无关回忆 |

> ⚠️ 关键词匹配对自然对话查询效果有限。推荐配置 `OPENAI_API_KEY` 以获得最佳 RAG 体验。

---

## 配置参考

`backend/.env` 完整配置项：

```env
# ── 数据库 ──
DATABASE_URL=sqlite+aiosqlite:///./exskill.db

# ── LLM ──
LLM_PROVIDER=deepseek              # deepseek | openai | claude
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# ── Embedding ──
EMBEDDING_PROVIDER=openai          # openai | voyage
EMBEDDING_MODEL=text-embedding-3-small
VOYAGE_API_KEY=

# ── 应用 ──
APP_HOST=0.0.0.0
APP_PORT=8000
CORS_ORIGINS=http://localhost:3000
```

---

## 开发

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev

# 运行测试
cd backend
pytest tests/ -v
```

---

## License

MIT — 仅供个人学习和情感疗愈使用。
