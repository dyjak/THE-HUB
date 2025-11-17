from __future__ import annotations

"""Production AI provider client helpers used by air/param_generation.

This module is extracted from the previous test-only clients in
app.tests.ai-render-test / app.tests.ai-param-test so that the
param_generation router no longer depends on test code.
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv  # type: ignore

# Load env once for local runs and server start, try explicit backend-fastapi/.env
try:
    here = Path(__file__).resolve()
    backend_root = here.parents[3]  # .../backend-fastapi
    env_file = backend_root / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        load_dotenv()
except Exception:
    load_dotenv()

try:
    # OpenAI python SDK v1.x (new client)
    from openai import OpenAI  # type: ignore
except Exception as e:  # pragma: no cover
    OpenAI = None  # type: ignore
    _OPENAI_IMPORT_ERROR = e

try:
    import anthropic  # type: ignore
except Exception as e:  # pragma: no cover
    anthropic = None  # type: ignore
    _ANTHROPIC_IMPORT_ERROR = e

try:
    import google.generativeai as genai  # type: ignore
except Exception as e:  # pragma: no cover
    genai = None  # type: ignore
    _GEMINI_IMPORT_ERROR = e


class ChatError(RuntimeError):
    pass


def get_openai_client() -> Any:
    global OpenAI, _OPENAI_IMPORT_ERROR
    if OpenAI is None:
        try:
            from openai import OpenAI as _NewOpenAI  # type: ignore
            OpenAI = _NewOpenAI  # type: ignore
        except Exception as e:  # pragma: no cover
            _OPENAI_IMPORT_ERROR = e
            raise ChatError(f"OpenAI SDK not available: {_OPENAI_IMPORT_ERROR}")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ChatError("OPENAI_API_KEY is not set. Create backend-fastapi/.env with your key.")
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def get_openrouter_client() -> Any:
    """Client for OpenRouter, which speaks the OpenAI-compatible API.

    We reuse the OpenAI SDK with a different base_url and API key.
    """
    global OpenAI, _OPENAI_IMPORT_ERROR
    if OpenAI is None:
        try:
            from openai import OpenAI as _NewOpenAI  # type: ignore
            OpenAI = _NewOpenAI  # type: ignore
        except Exception as e:  # pragma: no cover
            _OPENAI_IMPORT_ERROR = e
            raise ChatError(f"OpenAI SDK not available: {_OPENAI_IMPORT_ERROR}")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ChatError("OPENROUTER_API_KEY is not set in .env")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    return OpenAI(api_key=api_key, base_url=base_url)


def get_anthropic_client() -> Any:
    global anthropic, _ANTHROPIC_IMPORT_ERROR
    if anthropic is None:
        try:
            import anthropic as _anth  # type: ignore
            anthropic = _anth  # type: ignore
        except Exception as e:  # pragma: no cover
            _ANTHROPIC_IMPORT_ERROR = e
            raise ChatError(f"Anthropic SDK not available: {_ANTHROPIC_IMPORT_ERROR}")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ChatError("ANTHROPIC_API_KEY is not set in .env")
    return anthropic.Anthropic(api_key=api_key)


def get_gemini_client() -> Any:
    global genai, _GEMINI_IMPORT_ERROR
    if genai is None:
        try:
            import google.generativeai as _genai  # type: ignore
            genai = _genai  # type: ignore
        except Exception as e:  # pragma: no cover
            _GEMINI_IMPORT_ERROR = e
            raise ChatError(f"Gemini SDK not available: {_GEMINI_IMPORT_ERROR}")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ChatError("GOOGLE_API_KEY is not set in .env")
    genai.configure(api_key=api_key)
    return genai


def list_providers() -> list[dict[str, str]]:
    return [
        {"id": "openai", "name": "OpenAI", "default_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")},
        {"id": "anthropic", "name": "Anthropic Claude", "default_model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")},
        {"id": "gemini", "name": "Google Gemini", "default_model": os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")},
        {"id": "openrouter", "name": "OpenRouter (OpenAI-compatible)", "default_model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")},
    ]


def _env_list(var_name: str) -> list[str]:
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def list_models(provider: str) -> list[str]:
    p = (provider or "").lower().strip()
    # Allow overrides via env, e.g., OPENAI_MODELS, ANTHROPIC_MODELS, GOOGLE_MODELS
    if p == "openai":
        override = _env_list("OPENAI_MODELS")
        if override:
            return override
        # Try dynamic discovery
        try:
            client = get_openai_client()
            found: list[str] = []
            for m in client.models.list():
                mid = getattr(m, "id", "") or ""
                # filter likely chat models
                if any(prefix in mid for prefix in ("gpt-", "o3", "o4")) and not any(
                    skip in mid for skip in ("embedding", "audio", "tts", "whisper", "image")
                ):
                    found.append(mid)
            # put defaults first
            defaults = [os.getenv("OPENAI_MODEL", "gpt-4o-mini")]
            uniq: list[str] = []
            for x in defaults + found:
                if x and x not in uniq:
                    uniq.append(x)
            return uniq[:50]
        except Exception:  # pragma: no cover - fallback
            # Fallback static list
            return [
                os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "gpt-4o",
                "gpt-4o-mini",
                "o3-mini",
                "o4-mini",
            ]

    if p == "anthropic":
        override = _env_list("ANTHROPIC_MODELS")
        if override:
            return override
        # No public list endpoint; return curated set
        return [
            os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-haiku-20240307",
        ]

    if p == "gemini":
        override = _env_list("GOOGLE_MODELS")
        if override:
            return override
        try:
            g = get_gemini_client()
            found: list[str] = []
            for m in g.list_models():
                mid = getattr(m, "name", "") or getattr(m, "model", "") or ""
                if mid.startswith("models/"):
                    mid = mid.split("/", 1)[1]
                methods = set(getattr(m, "supported_generation_methods", []) or [])
                if "generateContent" in methods:
                    # model names can include versions; expose plain id
                    found.append(mid)
            defaults = [os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")]
            uniq: list[str] = []
            for x in defaults + found:
                if x and x not in uniq:
                    uniq.append(x)
            return uniq[:50]
        except Exception:  # pragma: no cover - fallback
            return [
                os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
                "gemini-2.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-2.0-flash",
            ]

    if p == "openrouter":
        # Allow overrides via env: OPENROUTER_MODELS
        override = _env_list("OPENROUTER_MODELS")
        if override:
            return override
        # Curated list of models that are generally good for structured JSON
        # and available on OpenRouter. You can tweak this in .env.
        defaults = [
            os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
            "meta-llama/llama-3.3-70b-instruct",
            "google/gemini-2.0-flash-001",
            "qwen/qwen-2.5-7b-instruct",
        ]
        # De-duplicate while preserving order
        uniq: list[str] = []
        for m in defaults:
            if m and m not in uniq:
                uniq.append(m)
        return uniq

    # Unknown provider
    return []
