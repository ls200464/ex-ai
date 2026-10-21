# ex-skill

[![Tests](https://github.com/ls200464/ex-ai/actions/workflows/tests.yml/badge.svg)](https://github.com/ls200464/ex-ai/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](backend/pyproject.toml)

[中文文档](README.zh-CN.md) · English

Turn exported chat history into a conversational persona.

ex-skill is a self-hosted full-stack application. You import a WeChat or QQ chat export
(`.txt`), an LLM extracts a structured personality profile and a set of shared memories
from it, and you can then talk to that persona through a streaming chat interface. The
persona is generated from the messages themselves, not written by hand.

```
Chat export (.txt)
        │
        ▼
   parse & normalize  ──►  messages
        │
        ▼
   LLM extraction  ──►  5-layer persona profile
        │               6 categories of memories
        ▼
   embed & store  ──►  vector index
        │
        ▼
   chat with RAG retrieval + SSE streaming
```

---

## Features

- **Chat import** — tolerant parsers for WeChat and QQ `.txt` exports, which differ across
  client versions and platforms.
- **Structured persona extraction** — a five-layer profile: hard rules, identity, speaking
  style, emotional patterns, and relational behavior.
- **Memory extraction** — six categories of shared memory (shared experiences, dates,
  inside jokes, arguments, sweet moments, timeline events).
- **Retrieval-augmented chat** — each turn retrieves the most relevant memories and injects
  them into the system prompt, so replies reference real shared history instead of inventing
  it.
- **Streaming responses** — token-by-token over SSE.
- **Provider-agnostic LLM layer** — DeepSeek, Anthropic, and OpenAI are all supported for
  chat, with OpenAI or Voyage for embeddings. Switched by configuration, no code changes.
- **Graceful embedding fallback** — runs without an embedding API by falling back to
  character-bigram pseudo-vectors and keyword similarity.
- **Correction loop** — when a reply is wrong, you can correct it and the persona layer is
  updated.

---

## Tech stack

**Backend**

| Component | Technology |
|---|---|
| Web framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Database | SQLite (development) / PostgreSQL + pgvector (production) |
| LLM | DeepSeek / Anthropic / OpenAI, configurable |
| Embeddings | OpenAI `text-embedding-3-small` / Voyage AI |
| Streaming | SSE via `sse-starlette` |

**Frontend**

| Component | Technology |
|---|---|
| Framework | Next.js 16 (App Router, Turbopack) |
| UI | shadcn/ui + Base UI |
| Styling | Tailwind CSS 4 |
| Streaming | Fetch API + `ReadableStream` (SSE) |

---

## Quick start

### Requirements

- Python 3.11+
- Node.js 20+
- An LLM API key (DeepSeek is the cheapest option)

### 1. Configure environment

```bash
cd backend
cp ../.env.example .env     # then edit .env
```

At minimum, set one LLM provider:

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
```

An embedding key is optional — without one the app degrades to keyword retrieval.

### 2. Start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API runs at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The UI runs at `http://localhost:3000`.

> **Proxy setup** — the frontend proxies `/api/*` to the backend through `next.config.ts`:
>
> ```ts
> async rewrites() {
>   return [{ source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' }]
> }
> ```

### 4. Use it

1. Open `http://localhost:3000` and create a persona (an ID plus a display name).
2. On the persona page, open the **source files** tab and upload an exported chat log,
   choosing WeChat or QQ as the source.
3. Wait for the pipeline to finish: parse → extract persona → extract memories → embed.
4. Open the chat view and start talking.

**Exporting chat history**

- **WeChat**: open the conversation → `...` (top right) → More → Export chat history →
  save as `.txt`
- **QQ**: open the conversation → `≡` (top right) → Export message history → choose `.txt`

---

## Configuration

`backend/.env`:

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./exskill.db

# LLM
LLM_PROVIDER=deepseek              # deepseek | openai | claude
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# Embeddings
EMBEDDING_PROVIDER=openai          # openai | voyage
EMBEDDING_MODEL=text-embedding-3-small
VOYAGE_API_KEY=

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
CORS_ORIGINS=http://localhost:3000
```

---

## How it works

### The five-layer persona model

| Layer | Field | What it captures |
|---|---|---|
| **Hard rules** | `hard_rules` | Bottom lines, non-negotiable principles, things this person would never say |
| **Identity** | `identity` | Self-description, age, occupation, personality typing |
| **Speaking style** | `speaking_style` | Tone, vocabulary, sentence length, punctuation habits, emoji use |
| **Emotional patterns** | `emotional_patterns` | Attachment style, conflict handling, emotional triggers |
| **Relational behavior** | `relational_behavior` | How they address you, their attitude toward you, typical openers and sign-offs |

### The six memory categories

| Category | Contents |
|---|---|
| `shared_experience` | Trips, activities, things you did together |
| `date` | Anniversaries, first dates, significant days |
| `inside_joke` | Jokes only the two of you understand |
| `argument` | Conflicts and how they were resolved |
| `sweet_moment` | Affectionate and romantic exchanges |
| `timeline_event` | Key points on the relationship timeline |

### The RAG chat flow

On every turn the system:

1. **Retrieves** — runs a similarity search over `memory_chunks` using the user message and
   takes the top 12 matches.
2. **Builds the prompt** — combines the five persona layers, the retrieved memories, and
   anti-hallucination rules into the system prompt.
3. **Generates** — streams the reply from the LLM.
4. **Persists** — stores both the user message and the reply.

### Anti-hallucination

Chatting as a specific person invites the model to invent memories, so three mechanisms
counter it:

- The system prompt separates *what may be expressed freely* (personality, mood) from
  *what may only come from retrieved memories* (factual claims about shared history).
- Temperature is lowered to 0.3.
- If retrieval quality is poor (average similarity below 0.08), the prompt instructs the
  model not to force a reference to those memories.

### Embedding fallback

Without an embedding API key the application still runs:

| Mode | Mechanism | Quality |
|---|---|---|
| Pseudo-vectors | Character bigrams + MD5-hashed tokens → 1536-dim sparse vectors | Basic retrieval |
| Keyword search | Jaccard similarity over bigrams and tokens | Works for exact matches, weak generalization |
| Low-quality warning | Prompt warns the model when mean similarity < 0.08 | Prevents forced references |

Keyword matching is noticeably weaker on natural conversational queries. Configuring
`OPENAI_API_KEY` gives materially better retrieval.

---

## API

Full interactive documentation is served at `/docs`. Summary:

| Group | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Personas | `GET/POST /api/personas`, `GET/PATCH/DELETE /api/personas/{id}` |
| Upload & parsing | `POST /api/personas/{id}/upload`, `GET /api/personas/{id}/uploads`, `GET /api/upload/{task_id}/status` |
| Extraction | `POST /api/personas/{id}/extract/{persona,memories,all}`, `GET /api/personas/{id}/extract/status` |
| Memories | `GET/POST /api/personas/{id}/memories`, `GET/PATCH/DELETE /api/memories/{id}`, `POST /api/personas/{id}/memories/search` |
| Conversations | `GET/POST /api/personas/{id}/conversations`, `GET /api/conversations/{id}/messages`, `DELETE /api/conversations/{id}` |
| Chat | `POST /api/personas/{id}/chat` (SSE), `POST /api/conversations/{id}/correct` |

### SSE event format

`POST /api/personas/{id}/chat` emits:

```json
{"type": "thinking", "stage": "generating"}
{"type": "token", "token": "好"}
{"type": "done", "full_text": "...", "message_id": "uuid", "retrieved_memories": []}
{"type": "error", "message": "reason"}
```

---

## Project structure

```
ex-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   ├── database.py             # Engine and session factory
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── routers/                # health, persona, upload, extraction, memory, chat
│   │   ├── services/               # chat, extraction, embedding, LLM client, persona
│   │   │   └── parser/             # base, wechat, qq
│   │   ├── chains/                 # persona, memory, correction + LLM factories
│   │   └── utils/                  # chunking, normalization
│   ├── tests/                      # parser tests
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── app/                    # App Router pages
│       ├── components/ui/          # shadcn/ui components
│       └── lib/                    # API client, SSE helpers
├── docker-compose.yml
├── .env.example
└── LICENSE
```

---

## Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Tests
cd backend
pytest tests/ -v

# Lint
cd backend && ruff check .
```

---

## Privacy

This application processes **private conversation logs** and produces a model of a real
person from them. Treat it accordingly:

- Run it locally. Do not expose it to the public internet without adding authentication.
- Conversation content is sent to whichever LLM provider you configure — that provider's
  data handling policy applies to it.
- Extracted personas and memories are stored in your local database
  (`backend/data/`, `*.db`), which is gitignored. Back it up or delete it deliberately.
- Do not publish personas generated from other people's messages without their consent.

---

## License

[MIT](LICENSE)
