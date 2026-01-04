from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..parameters import MidiParameters, AudioRenderParameters
import json
import os

from .client import simple_chat, ChatError, list_providers, list_models
from ..debug_store import DEBUG_STORE

router = APIRouter(prefix="/chat-smoke", tags=["ai-param-test:chat-smoke"])


class ChatIn(BaseModel):
    prompt: str
    provider: str | None = None
    model: str | None = None
    structured: bool | None = None


class ChatOut(BaseModel):
    reply: str
    provider: str
    model: str
    run_id: str | None = None


@router.get("/providers")
async def providers():
    return {"providers": list_providers()}


@router.get("/models/{provider}")
async def models(provider: str):
    items = list_models(provider)
    return {"provider": provider, "models": items}


def _paramify_core(prompt: str, provider: str, model: str | None, run=None):
    """Core logic for JSON param generation and normalization."""
    # Build a strict system instruction
    system = (
        "You are a music param planner. Respond ONLY with valid minified JSON in the exact schema:"
        " {\"midi\":{\"style\":string,\"mood\":string,\"tempo\":number,\"key\":string,\"scale\":string,\"meter\":string,\"bars\":number,\"length_seconds\":number,\"form\":[string],\"dynamic_profile\":string,\"arrangement_density\":string,\"harmonic_color\":string,\"instruments\":[string],\"instrument_configs\":[{\"name\":string,\"register\":string,\"role\":string,\"volume\":number,\"pan\":number,\"articulation\":string,\"dynamic_range\":string,\"effects\":[string]}],\"seed\":number|null},\"audio\":{\"sample_rate\":number,\"seconds\":number,\"master_gain_db\":number}}."
        " No markdown, no commentary. Use reasonable defaults when unspecified."
    )
    from .client import get_openai_client, get_anthropic_client, get_gemini_client
    raw: str
    if run:
        try:
            run.log("paramify", "start", {"provider": provider, "model": model, "prompt": prompt})
        except Exception:
            pass
    if provider == "openai":
        client = get_openai_client()
        use_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if run:
            try:
                run.log("provider_call", "openai.request", {"model": use_model})
            except Exception:
                pass
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        raw = (resp.choices[0].message.content or "").strip()
    elif provider == "anthropic":
        client = get_anthropic_client()
        use_model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        if run:
            try:
                run.log("provider_call", "anthropic.request", {"model": use_model})
            except Exception:
                pass
        resp = client.messages.create(
            model=use_model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.0,
        )
        blocks = getattr(resp, "content", []) or []
        out = []
        for b in blocks:
            t = getattr(b, "text", None)
            if t:
                out.append(t)
        raw = "\n".join(out).strip()
    elif provider == "gemini":
        g = get_gemini_client()
        use_model = model or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
        if run:
            try:
                run.log("provider_call", "gemini.request", {"model": use_model})
            except Exception:
                pass
        m = g.GenerativeModel(use_model, system_instruction=system)
        r = m.generate_content(prompt)
        raw = (getattr(r, "text", None) or str(r) or "").strip()
    else:
        raise ChatError(f"Unknown provider: {provider}")

    if run:
        try:
            run.log("provider_call", "raw_received", {"chars": len(raw)})
        except Exception:
            pass

    parsed = None
    parsed_dict: dict[str, object] | None = None
    errors: list[str] = []
    try:
        candidate = json.loads(raw)
        parsed = candidate
        if isinstance(candidate, dict):
            parsed_dict = candidate
        else:
            errors.append("parse: top-level JSON must be an object")
            if run:
                try:
                    run.log("parse", "json_error", {"error": "top_level_not_object"})
                except Exception:
                    pass
    except Exception as e:
        parsed = None
        parsed_dict = None
        errors.append(f"parse: {e}")
        if run:
            try:
                run.log("parse", "json_error", {"error": str(e)})
            except Exception:
                pass
    midi_out = None
    audio_out = None
    if parsed_dict is not None:
        try:
            midi_in = parsed_dict.get("midi") or {}
            audio_in = parsed_dict.get("audio") or {}
            midi = MidiParameters.from_dict(midi_in)
            audio = AudioRenderParameters.from_dict(audio_in)
            midi_out = midi.to_dict()
            audio_out = audio.to_dict()
        except Exception as e:
            errors.append(f"normalize: {e}")
            if run:
                try:
                    run.log("normalize", "error", {"error": str(e)})
                except Exception:
                    pass
    else:
        if run:
            try:
                run.log("normalize", "skipped", {"reason": "parse_failed"})
            except Exception:
                pass
    if run and parsed_dict is not None:
        try:
            run.log("normalize", "done", {"ok": bool(midi_out) and bool(audio_out)})
        except Exception:
            pass
    return {"raw": raw, "parsed": parsed, "normalized": {"midi": midi_out, "audio": audio_out}, "errors": errors or None}


@router.post("/send", response_model=ChatOut)
async def chat_send(body: ChatIn) -> ChatOut:
    try:
        provider = (body.provider or "gemini").lower()
        if body.structured:
            run = DEBUG_STORE.start()
            result = _paramify_core(body.prompt, provider, body.model, run=run)
            # Prefer normalized JSON; fall back to parsed/raw
            payload = result.get("normalized") or result.get("parsed") or result.get("raw") or {}
            try:
                reply = json.dumps(payload, separators=(",", ":")) if not isinstance(payload, str) else payload
            except Exception:
                reply = str(payload)
            return ChatOut(reply=reply, provider=provider, model=body.model or "", run_id=run.run_id)
        # Plain chat mode
        run = DEBUG_STORE.start()
        try:
            run.log("chat", "start", {"provider": provider, "model": body.model, "prompt": body.prompt})
        except Exception:
            pass
        reply = simple_chat(body.prompt, provider=provider, model=body.model)
        if run:
            try:
                run.log("chat", "reply", {"chars": len(reply)})
            except Exception:
                pass
        return ChatOut(reply=reply, provider=provider, model=body.model or "", run_id=run.run_id)
    except ChatError as e:
        raise HTTPException(status_code=400, detail={"error": "chat_error", "message": str(e)})


class ParamifyIn(BaseModel):
    prompt: str
    provider: str | None = None
    model: str | None = None


@router.post("/paramify")
async def paramify(body: ParamifyIn):
    """Ask the model to return JSON in our expected schema and then normalize it.

    Returns: { raw: string, parsed?: object, normalized: { midi, audio }, errors?: string[] }
    """
    provider = (body.provider or "gemini").lower()
    model = body.model
    run = DEBUG_STORE.start()
    result = _paramify_core(body.prompt, provider, model, run=run)
    return {"provider": provider, "model": model or "", **result, "errors": result.get("errors") or None, "run_id": run.run_id}


@router.get("/debug/{run_id}")
async def get_debug_run(run_id: str):
    data = DEBUG_STORE.get(run_id)
    if not data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "run not found"})
    return data
