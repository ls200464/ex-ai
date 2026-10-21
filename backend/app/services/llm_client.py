"""Lightweight LLM client — calls DeepSeek/OpenAI API directly without LangChain.

Falls back to LangChain if it's installed, but works standalone with httpx.
"""

from __future__ import annotations

import json
import re
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


def _strip_code_fence(content: str) -> str:
    """Return the body of a markdown code fence, or the text unchanged.

    Models often wrap JSON in ```json ... ```. A response truncated by the token
    limit can omit the closing fence; looking the closing marker up with
    ``str.index`` then raised ``ValueError: substring not found`` and hid the
    real parse failure. Ending at the string end instead lets a complete JSON
    body still parse.
    """
    fence = "```"
    start = content.find(fence)
    if start == -1:
        return content

    body_start = start + len(fence)
    # Drop an optional language tag sitting on the opening fence's line.
    newline = content.find("\n", body_start)
    if newline != -1 and content[body_start:newline].strip().lower() in ("", "json"):
        body_start = newline + 1

    body_end = content.find(fence, body_start)
    if body_end == -1:
        body_end = len(content)
    return content[body_start:body_end].strip()


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

    candidates = [content]
    fenced = _strip_code_fence(content)
    if fenced != content:
        candidates.append(fenced)

    # Previously an unparseable fenced block raised the raw JSONDecodeError out
    # of the except handler, and an unclosed fence raised "substring not found",
    # so callers could not tell a malformed model response from a bug upstream.
    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as error:
            last_error = error

        # Repair the most common model mistake: trailing commas.
        repaired = re.sub(r",\s*}", "}", candidate)
        repaired = re.sub(r",\s*]", "]", repaired)
        if repaired != candidate:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError as error:
                last_error = error

    raise ValueError(
        f"Could not parse JSON from response (length={len(content)}): "
        f"{content[:300]}..."
    ) from last_error


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
