"""Lightweight LLM client — calls DeepSeek/OpenAI API directly without LangChain.

Falls back to LangChain if it's installed, but works standalone with httpx.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


def _get_client_config() -> dict[str, str]:
    """Resolve API key, base URL, and model from settings."""
    provider = settings.LLM_PROVIDER

    if provider == "deepseek":
        return {
            "api_key": settings.DEEPSEEK_API_KEY,
            "base_url": settings.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions",
            "model": settings.LLM_MODEL,
        }
    elif provider == "openai":
        return {
            "api_key": settings.OPENAI_API_KEY,
            "base_url": "https://api.openai.com/v1/chat/completions",
            "model": settings.LLM_MODEL,
        }
    elif provider == "claude":
        return {
            "api_key": settings.ANTHROPIC_API_KEY,
            "base_url": "https://api.anthropic.com/v1/messages",
            "model": settings.LLM_MODEL,
        }
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def chat_completion(
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
) -> dict:
    """Send a chat completion request and return the response dict.

    Args:
        messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
        temperature: LLM temperature (default from settings)
        max_tokens: Max tokens (default from settings)
        response_format: Optional OpenAI-style response_format, e.g.
            {"type": "json_object"}

    Returns:
        Dict with keys: content (str), model (str), usage (dict), raw (dict)
    """
    config = _get_client_config()
    temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
    max_tokens = max_tokens or settings.LLM_MAX_TOKENS

    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Only add response_format for OpenAI-compatible providers that support it
    # DeepSeek supports json_object mode
    if response_format:
        payload["response_format"] = response_format

    # DeepSeek/OpenAI API
    if config["base_url"].endswith("/chat/completions"):
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json; charset=utf-8",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(config["base_url"], json=payload, headers=headers)
            resp.raise_for_status()
            # Use resp.text and manual JSON parsing for better encoding control
            text = resp.text
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # Try reading as bytes and decoding
                data = json.loads(resp.content.decode('utf-8'))

        choice = data["choices"][0]
        return {
            "content": choice["message"]["content"],
            "model": data.get("model", config["model"]),
            "usage": data.get("usage", {}),
            "raw": data,
        }

    # Anthropic Messages API
    else:
        headers = {
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json; charset=utf-8",
        }

        system_messages = [m["content"] for m in messages if m["role"] == "system"]
        chat_messages = [m for m in messages if m["role"] != "system"]

        payload = {
            "model": config["model"],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(config["base_url"], json=payload, headers=headers)
            resp.raise_for_status()
            text = resp.text
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = json.loads(resp.content.decode('utf-8'))

        return {
            "content": data["content"][0]["text"],
            "model": data.get("model", config["model"]),
            "usage": data.get("usage", {}),
            "raw": data,
        }


async def extract_json(
    system_prompt: str,
    user_input: str,
    temperature: float | None = None,
) -> dict:
    """Send a prompt and get structured JSON back.

    Uses OpenAI's JSON mode for reliable structured output.
    Adds format instructions to the system prompt.
    """
    # Append JSON format requirement
    full_system = system_prompt + """

## Output Format
You MUST respond with ONLY a valid JSON object. No markdown, no code fences, no extra text.
The JSON object must use double quotes for all keys and string values.
Ensure all strings are properly escaped."""
    full_system = full_system.replace("{format_instructions}", "")

    messages = [
        {"role": "system", "content": full_system},
        {"role": "user", "content": user_input},
    ]

    result = await chat_completion(
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    content = result["content"].strip()
    # Try to extract JSON from the response
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Some models wrap JSON in markdown code blocks
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            return json.loads(content[start:end].strip())
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            return json.loads(content[start:end].strip())
        # Try to fix common JSON issues
        try:
            # Sometimes trailing commas or other issues
            import re
            fixed = re.sub(r',\s*}', '}', content)
            fixed = re.sub(r',\s*]', ']', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            raise ValueError(
                f"Could not parse JSON from response (length={len(content)}): "
                f"{content[:300]}..."
            )


async def chat_stream(
    messages: list[dict[str, str]],
    temperature: float | None = None,
):
    """Stream chat completion tokens via async generator.

    Yields token strings one at a time, like LangChain's .astream().
    """
    config = _get_client_config()
    temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE

    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": settings.LLM_MAX_TOKENS,
        "stream": True,
    }

    # DeepSeek/OpenAI streaming
    if config["base_url"].endswith("/chat/completions"):
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", config["base_url"], json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
    else:
        # Anthropic streaming — fall back to non-streaming
        result = await chat_completion(messages, temperature)
        yield result["content"]
