from __future__ import annotations

"""pomocnicze klienty do providerów ai używane przez `air/param_generation`.

założenia:
- moduł jest wydzielony z wcześniejszych, testowych klientów (z katalogów testów),
  żeby `param_generation` nie zależało od kodu testowego
- inicjalizacja jest "best-effort": import sdk może się nie udać (brak zależności),
  a brak klucza api ma zwrócić czytelny błąd w stylu `ChatError`
- konfiguracja opiera się o zmienne środowiskowe oraz opcjonalny plik `backend-fastapi/.env`
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv  # type: ignore

# ładujemy env jednorazowo przy starcie modułu.
# najpierw próbujemy jawnie `backend-fastapi/.env`, a jeśli nie istnieje, fallback do domyślnego `load_dotenv()`.
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
    # openai python sdk v1.x (nowy klient `OpenAI`)
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
    """wyjątek warstwy providerów (brak sdk, brak klucza api, itp.)."""

    pass


def get_openai_client() -> Any:
    """zwraca klienta openai skonfigurowanego na bazie env.

    wymagane zmienne:
    - `OPENAI_API_KEY`

    opcjonalnie:
    - `OPENAI_BASE_URL` (jeśli chcemy użyć proxy / self-hosted kompatybilnego api)
    """
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
    """zwraca klienta openrouter (api zgodne z openai).

    uwagi:
    - wykorzystujemy openai sdk, ale z innym `base_url`
    - wymagany jest `OPENROUTER_API_KEY` (opcjonalnie `OPENROUTER_BASE_URL`)
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
    """zwraca klienta anthropic skonfigurowanego na bazie env (`ANTHROPIC_API_KEY`)."""
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
    """zwraca klienta gemini (google generative ai) skonfigurowanego na bazie env (`GOOGLE_API_KEY`)."""
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
    """zwraca listę dostępnych providerów oraz ich domyślne modele.

    uwaga: wartości modeli pochodzą z env, żeby łatwo sterować domyślnym wyborem bez zmian w kodzie.
    """
    return [
        {"id": "openai", "name": "OpenAI", "default_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")},
        {"id": "anthropic", "name": "Anthropic Claude", "default_model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")},
        {"id": "gemini", "name": "Google Gemini", "default_model": os.getenv("GOOGLE_MODEL", "gemini-3-pro-preview")},
        {"id": "openrouter", "name": "OpenRouter (OpenAI-compatible)", "default_model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")},
    ]


def _looks_like_image_model(model_id: str) -> bool:
    mid = (model_id or "").lower()
    # konserwatywna heurystyka: filtrujemy modele wyraźnie do generowania obrazów.
    # celowo nie filtrujemy modeli "vision" (to nadal modele czatu / generacji tekstu).
    return ("imagen" in mid) or ("image" in mid)


def _env_list(var_name: str) -> list[str]:
    """parsuje zmienną env jako listę elementów rozdzielonych przecinkami."""
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def list_models(provider: str) -> list[str]:
    p = (provider or "").lower().strip()
    # allow overrides via env, np. OPENAI_MODELS, ANTHROPIC_MODELS, GOOGLE_MODELS
    if p == "openai":
        override = _env_list("OPENAI_MODELS")
        if override:
            return override
        # próbujemy dynamicznie odkryć modele przez sdk (jeśli dostępne)
        try:
            client = get_openai_client()
            found: list[str] = []
            for m in client.models.list():
                mid = getattr(m, "id", "") or ""
                # filtrujemy modele, które wyglądają na chat/llm (odrzucamy embedding/audio/tts/itp.)
                if any(prefix in mid for prefix in ("gpt-", "o3", "o4")) and not any(
                    skip in mid for skip in ("embedding", "audio", "tts", "whisper", "image")
                ):
                    found.append(mid)
            # ustawiamy domyślny model na początku listy
            defaults = [os.getenv("OPENAI_MODEL", "gpt-4o-mini")]
            uniq: list[str] = []
            for x in defaults + found:
                if x and x not in uniq:
                    uniq.append(x)
            return uniq[:50]
        except Exception:  # pragma: no cover - fallback
            # fallback: statyczna lista, gdy sdk/dostęp do endpointu nie działa
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
        # brak publicznego endpointu listującego; zwracamy zestaw "ręczny"
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
            return [m for m in override if m and not _looks_like_image_model(m)]
        try:
            g = get_gemini_client()
            found: list[str] = []
            for m in g.list_models():
                mid = getattr(m, "name", "") or getattr(m, "model", "") or ""
                if mid.startswith("models/"):
                    mid = mid.split("/", 1)[1]
                methods = set(getattr(m, "supported_generation_methods", []) or [])
                if "generateContent" in methods:
                    # nazwy modeli mogą zawierać wersje; wystawiamy "gołe" id
                    if mid and not _looks_like_image_model(mid):
                        found.append(mid)
            defaults = [os.getenv("GOOGLE_MODEL", "gemini-3-pro-preview")]
            uniq: list[str] = []
            for x in defaults + found:
                if x and x not in uniq:
                    uniq.append(x)
            return uniq[:50]
        except Exception:  # pragma: no cover - fallback
            return [
                os.getenv("GOOGLE_MODEL", "gemini-3-pro-preview"),
                "gemini-3-pro-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-2.0-flash",
            ]

    if p == "openrouter":
        # allow overrides via env: OPENROUTER_MODELS
        override = _env_list("OPENROUTER_MODELS")
        if override:
            return override
        # ręcznie dobrana lista modeli, które zwykle dobrze radzą sobie ze
        # strukturalnym json i są dostępne na openrouter.
        # tę listę można w całości nadpisać w `.env`.
        defaults = [
            # Default / primary model (configure in .env; pick a strong general-purpose model)
            os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"),
            # Strong general-purpose LLaMA
            "meta-llama/llama-3.3-70b-instruct",
            # Gemini via OpenRouter (fast, good for structured output)
            "google/gemini-2.0-flash-001",
            # Qwen family (good compromise quality/price)
            "qwen/qwen-2.5-7b-instruct",
            # Qwen reasoning-flavoured, larger model
            "qwen/qwen-2.5-72b-instruct",
            # DeepSeek reasoning model
            "deepseek/deepseek-r1:free",
            # Mistral family
            "mistralai/mistral-nemo",
        ]
        # deduplikacja z zachowaniem kolejności
        uniq: list[str] = []
        for m in defaults:
            if m and m not in uniq:
                uniq.append(m)
        return uniq

    # nieznany provider
    return []
