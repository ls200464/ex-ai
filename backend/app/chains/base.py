"""LLM factory with multi-model switching and shared chain utilities.

All LangChain imports are lazy — the module works without LangChain installed
when the lightweight llm_client is used instead.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.config import settings


class LLMProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


def create_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
):
    """Factory to create the appropriate LangChain LLM instance based on config.

    Requires: langchain-core + langchain-openai (for OpenAI/DeepSeek)
              or langchain-anthropic (for Claude)
    """
    provider = provider or settings.LLM_PROVIDER
    model = model or settings.LLM_MODEL
    temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE

    if provider == "claude":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def create_embeddings(provider: str | None = None, model: str | None = None):
    """Factory for embedding models. Requires langchain-openai or langchain-voyageai."""
    provider = provider or settings.EMBEDDING_PROVIDER
    model = model or settings.EMBEDDING_MODEL

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=model, api_key=settings.OPENAI_API_KEY)
    elif provider == "deepseek":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model="text-embedding-3-small", api_key=settings.OPENAI_API_KEY or settings.DEEPSEEK_API_KEY)
    elif provider == "voyage":
        from langchain_voyageai import VoyageAIEmbeddings

        return VoyageAIEmbeddings(model=model, voyage_api_key=settings.VOYAGE_API_KEY)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")


def build_extraction_chain(
    system_prompt: str,
    output_schema: type[BaseModel],
    llm=None,
) -> Any:
    """Build a standard extraction chain: prompt → llm → json_parser.

    Requires langchain-core. Returns a LangChain Runnable that takes a dict
    with the prompt variables and returns a validated Pydantic model instance.
    """
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    if llm is None:
        llm = create_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    parser = JsonOutputParser(pydantic_object=output_schema)

    return prompt | llm | parser
