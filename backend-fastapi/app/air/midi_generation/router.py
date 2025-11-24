from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Any, Dict, Optional, List
import os

from .schemas import MidiGenerationIn, MidiGenerationOut, MidiArtifactPaths
from .engine import generate_midi_and_artifacts, _safe_parse_midi_json
from app.air.providers.client import (
    get_openai_client as _get_openai_client,
    get_anthropic_client as _get_anthropic_client,
    get_gemini_client as _get_gemini_client,
    get_openrouter_client as _get_openrouter_client,
)

router = APIRouter(prefix="/air/midi-generation", tags=["air:midi-generation"])


def _call_composer(provider: str, model: Optional[str], meta: Dict[str, Any]) -> tuple[str, str, str]:
    """Wywołuje model AI, który ma zwrócić JSON z pattern/layers/meta.

    Wejście do modelu opieramy na meta z param_generation.
    """

    provider = (provider or "gemini").lower()

    system = (
        "You are a precise MIDI pattern composer. "
        "Respond ONLY with valid minified JSON describing a drum-machine-like pattern. "
        "Schema: {\"pattern\":[{\"bar\":int,\"events\":[{\"step\":int,\"note\":int,\"vel\":int,\"len\":int}]}],"
        "\"layers\":{instrument:[{\"bar\":int,\"events\":[{\"step\":int,\"note\":int,\"vel\":int,\"len\":int}]}]},"
        "\"meta\":{...}}. "
        "Use exactly 8 steps per bar (0-7). Steps are 16th-note grid in 4/4. "
        "Use MIDI note numbers for notes (e.g. 36 for kick, 38 for snare, 42 for hihat, 60 for middle C). "
        "Do not include any explanations, comments or markdown, only JSON."
    )

    user_payload = {
        "task": "compose_midi_pattern",
        "meta": meta,
    }

    import json

    user = json.dumps(user_payload, separators=(",", ":"))

    # OpenAI
    if provider == "openai":
        client = _get_openai_client()
        use_model = model or os.getenv("OPENAI_MIDI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        resp = client.chat.completions.create(
            model=use_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        return system, user, content

    # Anthropic
    if provider == "anthropic":
        client = _get_anthropic_client()
        use_model = model or os.getenv("ANTHROPIC_MIDI_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"))
        resp = client.messages.create(
            model=use_model,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=4096,
            temperature=0.2,
        )
        blocks = getattr(resp, "content", []) or []
        out: List[str] = []
        for b in blocks:
            t = getattr(b, "text", None)
            if t:
                out.append(t)
        content = "\n".join(out).strip()
        return system, user, content

    # Gemini
    if provider == "gemini":
        g = _get_gemini_client()
        use_model = model or os.getenv("GOOGLE_MIDI_MODEL", os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"))
        try:
            m = g.GenerativeModel(use_model, system_instruction=system)
        except TypeError:
            m = g.GenerativeModel(use_model, system_instruction=[{"role": "system", "parts": [system]}])
        r = m.generate_content(user)
        try:
            text_parts: List[str] = []
            candidates = getattr(r, "candidates", None) or []
            for cand in candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None) or []
                for part in parts:
                    t = getattr(part, "text", None)
                    if t:
                        text_parts.append(t)
            if text_parts:
                content = "\n".join(text_parts).strip()
                return system, user, content
        except Exception:
            pass
        fallback = (getattr(r, "text", None) or str(r) or "").strip()
        return system, user, fallback

    # OpenRouter
    if provider == "openrouter":
        client = _get_openrouter_client()
        use_model = model or os.getenv("OPENROUTER_MIDI_MODEL", os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"))
        resp = client.chat.completions.create(
            model=use_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        return system, user, content

    raise HTTPException(status_code=400, detail={"error": "unknown_provider", "message": f"Unknown provider: {provider}"})


@router.post("/compose", response_model=MidiGenerationOut)
def compose(req: MidiGenerationIn) -> MidiGenerationOut:
    """Główny endpoint: przyjmuje meta z param_generation, generuje MIDI + SVG.

    Frontend scenariusz:
    1) /air/param-generation/plan -> parsed.meta
    2) /air/midi-generation/compose { meta: parsed.meta, provider?, model? }
    """

    meta = req.meta.dict()
    provider = (req.provider or "gemini").lower()
    model = req.model or None

    raw_midi_json: Dict[str, Any]
    raw_text: Optional[str] = None
    system: Optional[str] = None
    user: Optional[str] = None
    errors: List[str] = []

    if req.ai_midi is not None:
        # ręcznie wstrzyknięty JSON (debug / eksperymenty)
        raw_midi_json = req.ai_midi
    else:
        try:
            system, user, raw_text = _call_composer(provider, model, meta)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail={"error": "composer_error", "message": str(e)})
        parsed, parse_errors = _safe_parse_midi_json(raw_text)
        raw_midi_json = parsed
        errors.extend(parse_errors)

    from .engine import generate_midi_and_artifacts

    run_id, midi_data, artifacts = generate_midi_and_artifacts(meta, raw_midi_json)

    return MidiGenerationOut(
        run_id=run_id,
        midi=midi_data,
        artifacts=MidiArtifactPaths(**artifacts),
        provider=provider,
        model=model,
        errors=errors or None,
        system=system,
        user=user,
        raw=raw_text,
        parsed=raw_midi_json,
    )