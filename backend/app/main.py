from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import auth, chat, extraction, health, memory, persona, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create pgvector extension on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="ex-skill API",
    description="Distill an ex-partner into an AI persona",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(persona.router, prefix="/api", tags=["personas"])
app.include_router(upload.router, prefix="/api", tags=["uploads"])
app.include_router(extraction.router, prefix="/api", tags=["extraction"])
app.include_router(memory.router, prefix="/api", tags=["memories"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
