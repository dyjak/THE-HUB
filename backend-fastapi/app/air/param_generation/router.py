from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import json
import os

from .schemas import MidiPlanIn, MidiPlanResult
from urllib.parse import quote
try:
    from app.air.inventory.access import get_inventory_cached as _inv_get_cached
    from app.air.inventory.access import list_instruments as _inv_list
except Exception:  # pragma: no cover
    _inv_get_cached = None  # type: ignore
    _inv_list = None  # type: ignore
try:  # optional inventory usage for hints
    from app.air.inventory.access import list_instruments as _inventory_instruments
except Exception:
    _inventory_instruments = None  # type: ignore
from .debug_store import DEBUG_STORE
from app.air.providers.client import (
    get_openai_client as _get_openai_client,
    get_anthropic_client as _get_anthropic_client,
    get_gemini_client as _get_gemini_client,
    get_openrouter_client as _get_openrouter_client,
    list_providers as _providers_list,
    list_models as _models_list,
)


router = APIRouter(prefix="/air/param-generation", tags=["air:param-generation"])

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ProvidersOut(BaseModel):
    providers: list[dict]


@router.get("/providers", response_model=ProvidersOut)
def providers() -> ProvidersOut:
    items = _providers_list()
    return ProvidersOut(providers=items)


@router.get("/models/{provider}")
def models(provider: str):
    return {"provider": provider, "models": _models_list(provider)}


def _allowed_instruments_hint() -> str:
    # Prefer inventory (canonical list, may include future instruments)
    try:
        if callable(_inventory_instruments):  # type: ignore
            inv_list = _inventory_instruments() or []
            if inv_list:
                return ", ".join(inv_list)
    except Exception:
        pass
    # Final static fallback (no ai-render-test dependency)
    return "piano, pad, strings, lead, bass, drumkit, kick, snare, hihat, fx"


def _midi_plan_system(midi: MidiPlanIn) -> tuple[str, str]:
    """Build system and user prompts for the *parameter planner*.

    This agent is responsible ONLY for high-level musical parameters, not
    for concrete MIDI note sequences. It should return a JSON object with
    a single key `meta` that mirrors MidiPlanIn/MidiParameters-like fields.
    """
    allowed = _allowed_instruments_hint()
    system = (
        "You are a precise music parameter planner, NOT a MIDI composer. "
        "Respond ONLY with valid minified JSON in the exact schema:"
    " {\"meta\":{"
    "\"style\":string,\"mood\":string,\"tempo\":number,\"key\":string,\"scale\":string,"
    "\"meter\":string,\"bars\":number,\"length_seconds\":number,"
    "\"dynamic_profile\":string,\"arrangement_density\":string,\"harmonic_color\":string,"
    "\"instruments\":[string]}}."
        " Choose all values based on the natural-language description from the user."
        " You are free to change tempo, bar count, form and instrument choices to best match the request."
        " This module plans parameters only. Do NOT output any MIDI notes,"
        " patterns, bars with steps, or note/velocity/length grids."
        " No markdown, no comments."
        " IMPORTANT: Allowed instrument names are strictly: [" + allowed + "]."
        " Always use only these names in meta.instruments (case preserved as listed)."
    )
    # For generative behavior we only send the high-level natural language
    # description from the user. All concrete parameter values are chosen by
    # the model within the schema constraints described in the system prompt.
    user = json.dumps({
        "task": "plan_midi_parameters",
        "user_prompt": getattr(midi, "prompt", None),
    }, separators=(",", ":"))
    return system, user


def _call_model(provider: str, model: Optional[str], system: str, user: str) -> str:
    """Call underlying LLM provider and return raw text response.

    This wrapper tries to be defensive about provider SDK response shapes,
    especially for Gemini where `.text` may not be populated.
    """
    provider = (provider or "gemini").lower()

    # OpenAI
    if provider == "openai":
        client = _get_openai_client()
        use_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        return (resp.choices[0].message.content or "").strip()

    # Anthropic
    if provider == "anthropic":
        client = _get_anthropic_client()
        use_model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        resp = client.messages.create(
            model=use_model,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=2048,
            temperature=0.0,
        )
        blocks = getattr(resp, "content", []) or []
        out = []
        for b in blocks:
            t = getattr(b, "text", None)
            if t:
                out.append(t)
        return "\n".join(out).strip()

    # Gemini / Google Generative AI
    if provider == "gemini":
        g = _get_gemini_client()
        use_model = model or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")

        # Newer SDKs expect system instruction as list of parts; fall back to old style.
        try:
            m = g.GenerativeModel(use_model, system_instruction=system)
        except TypeError:
            # In some SDK versions `system_instruction` expects list[dict]
            m = g.GenerativeModel(
                use_model,
                system_instruction=[{"role": "system", "parts": [system]}],
            )

        r = m.generate_content(user)

        # Preferred path: candidates -> content.parts[].text
        try:
            text_parts = []
            candidates = getattr(r, "candidates", None) or []
            for cand in candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None) or []
                for part in parts:
                    t = getattr(part, "text", None)
                    if t:
                        text_parts.append(t)
            if text_parts:
                return "\n".join(text_parts).strip()
        except Exception:
            # fall back to simpler shapes below
            pass

        # Fallback: r.text or stringified object
        return (getattr(r, "text", None) or str(r) or "").strip()

    # OpenRouter (OpenAI-compatible)
    if provider == "openrouter":
        client = _get_openrouter_client()
        # Curated default chosen for structured output and free tier
        use_model = model or os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        return (resp.choices[0].message.content or "").strip()
    raise HTTPException(status_code=400, detail={"error": "unknown_provider", "message": f"Unknown provider: {provider}"})


# Inventory proxy endpoints (keep param-generation self-contained for UI)
@router.get("/available-instruments")
def available_instruments_proxy():
    try:
        if callable(_inv_list):  # type: ignore
            lst = _inv_list() or []
            return {"available": lst, "count": len(lst)}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "inventory_unavailable", "message": str(e)})
    return {"available": [], "count": 0}


def _resolve_target_instruments(inv: dict, name: str) -> list[str]:
    names = list((inv.get("instruments") or {}).keys()) if isinstance(inv.get("instruments"), dict) else []
    if not names:
        return []
    lower_map = {n.lower(): n for n in names}
    q = (name or "").strip()
    ql = q.lower()

    # Helpers to aggregate groups from available names
    def _present(opts: list[str]) -> list[str]:
        return [x for x in opts if x in names]

    # synonyms / normalization -> singular instrument naming
    syn = {
        "pad": "Pad", "pads": "Pad",
        "bell": "Bell", "bells": "Bell",
        "pluck": "Pluck", "plucks": "Pluck",
        "lead": "Lead", "leads": "Lead",
        "synth": "Synth", "reese": "Reese",
        "bass": "Bass", "bass guitar": "Bass Guitar", "bass synth": "Bass Synth",
        "flute": "Flute", "guitar": "Guitar", "sax": "Sax",
        "piano": "Piano", "violin": "Violin", "brass": "Brass",
        "808": "808",
        # drum parts
        "kick": "Kick", "snare": "Snare", "clap": "Clap",
        "hihat": "Hat", "hi-hat": "Hat", "hats": "Hat", "hat": "Hat", "hh": "Hat",
    }

    # Exact
    if q in names:
        return [q]
    # Case-insensitive exact
    if ql in lower_map:
        return [lower_map[ql]]

    # Group aggregators
    if ql in ("drums", "drumkit"):
        agg = _present(["Kick", "Snare", "Hat", "Clap"]) or _present(["Kick", "Snare", "Hats", "Claps"])  # tolerate legacy plural
        return agg
    if ql == "fx":
        fx_opts = ["Texture", "Downfilter", "Impact", "Swell", "Riser", "Subdrop", "Upfilter"]
        return _present(fx_opts)

    # Synonym resolution to a single instrument
    if ql in syn:
        tgt = syn[ql]
        if tgt in names:
            return [tgt]
        if tgt.lower() in lower_map:
            return [lower_map[tgt.lower()]]

    # Pluralization tweaks
    if ql.endswith("s") and ql[:-1] in lower_map:
        return [lower_map[ql[:-1]]]
    if (ql + "s") in lower_map:
        return [lower_map[ql + "s"]]

    # Prefix/contains fuzzy (last resort)
    for n in names:
        if ql and (n.lower().startswith(ql) or ql in n.lower()):
            return [n]
    return []


@router.get("/samples/{instrument}")
def list_samples_proxy(instrument: str, offset: int = 0, limit: int = 100):
    if not callable(_inv_get_cached):
        raise HTTPException(status_code=500, detail={"error": "inventory_unavailable"})
    try:
        inv = _inv_get_cached()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "inventory_error", "message": str(e)})
    ql = (instrument or "").strip().lower()
    # Category aggregators based on sample rows for robustness
    targets: list[str] = []
    if ql in ("drums", "drumkit"):
        try:
            cat_rows = [r for r in (inv.get("samples") or []) if (r.get("category") == "Drums")]
            parts = sorted({r.get("instrument") for r in cat_rows if r.get("instrument")})
            targets = [t for t in parts if isinstance(t, str)]
        except Exception:
            targets = []
    elif ql == "fx":
        try:
            fx_rows = [r for r in (inv.get("samples") or []) if (r.get("category") == "FX")]
            parts = sorted({r.get("instrument") for r in fx_rows if r.get("instrument")})
            targets = [t for t in parts if isinstance(t, str)]
        except Exception:
            targets = []
    else:
        targets = _resolve_target_instruments(inv, instrument)
    if not targets:
        # Include resolved targets info for easier debugging/UX on the client
        return {"instrument": instrument, "resolved": [], "count": 0, "items": [], "default": None}
    tset = set(targets)
    rows = [r for r in (inv.get("samples") or []) if r.get("instrument") in tset]
    if not rows:
        return {"instrument": instrument, "resolved": targets, "count": 0, "items": [], "default": None}
    start = max(0, int(offset)); end = start + max(1, min(500, int(limit)))
    base = Path(inv.get("root") or ".").resolve()
    items: list[dict[str, Any]] = []
    for r in rows[start:end]:
        url = None
        try:
            rel = r.get("file_rel")
            if rel:
                rel_posix = Path(rel).as_posix()
                url = "/api/local-samples/" + quote(rel_posix, safe="/")
            elif r.get("file_abs"):
                rel2 = Path(r.get("file_abs")).resolve().relative_to(base).as_posix()
                url = "/api/local-samples/" + quote(rel2, safe="/")
        except Exception:
            url = None
        name = None
        try:
            if r.get("file_abs"):
                name = Path(r.get("file_abs")).name
            elif r.get("file_rel"):
                name = Path(r.get("file_rel")).name
        except Exception:
            name = r.get("id")
        items.append({
            "id": r.get("id"),
            "file": r.get("file_abs") or str((base / (r.get("file_rel") or "")).resolve()),
            "name": name,
            "url": url,
            "subtype": r.get('subtype'),
            "family": r.get('family'),
            "category": r.get('category'),
            "pitch": r.get('pitch'),
        })
    default_item = items[0] if items else None
    return {"instrument": instrument, "resolved": targets, "count": len(rows), "offset": start, "limit": limit, "items": items, "default": default_item}


class MidiPlanRequest(BaseModel):
    midi: Dict[str, Any]
    provider: Optional[str] = None
    model: Optional[str] = None


def _safe_parse_json(raw: str) -> tuple[Optional[Dict[str, Any]], list[str]]:
    """Try to parse JSON from model output, with a couple of safety nets.

    - Strips potential ```json fences.
    - On first failure, tries truncating to the last closing brace to
      recover from outputs that were cut off mid-stream.
    """
    errors: list[str] = []
    text = (raw or "").strip()

    # Strip markdown code fences if the model decided to add them anyway.
    if text.startswith("```"):
        try:
            # find first closing ``` after the opening fence
            fence_end = text.index("```", 3) + 3
            # take everything after that until the final fence (if present)
            tail = text[fence_end:]
            if "```" in tail:
                inner_end = tail.rindex("```")
                text = tail[:inner_end].strip()
            else:
                text = tail.strip()
        except ValueError:
            errors.append("parse: unable to strip markdown fences")

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            candidate = json.loads(text)
            if isinstance(candidate, dict):
                return candidate, errors
            errors.append("parse: top-level JSON must be an object")
            return None, errors
        except Exception as e:  # noqa: PERF203
            last_error = e
            if attempt == 0:
                # Try truncating to the last closing brace in case
                # the response was cut off in the middle of streaming.
                last_brace = text.rfind("}")
                if last_brace > 0:
                    text = text[: last_brace + 1]
                    errors.append(f"parse: truncated to last brace due to {e}")
                    continue
            errors.append(f"parse: {e}")
            break

    # Failed to recover
    return None, errors


@router.post("/midi-plan")
def midi_plan(body: MidiPlanRequest):
    run = DEBUG_STORE.start()
    run.log("plan", "start", {"provider": body.provider or "gemini", "model": body.model or None})
    try:
        midi = MidiPlanIn(**(body.midi or {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    system, user = _midi_plan_system(midi)
    try:
        run.log("provider_call", "request", {
            "provider": (body.provider or "gemini"),
            "model": (body.model or None),
            "system": system,
            "user": user,
        })
        raw = _call_model(body.provider or "gemini", body.model, system, user)
        run.log("provider_call", "raw_received", {"chars": len(raw)})
    except Exception as e:
        run.log("provider_call", "failed", {"error": str(e)})
        raise HTTPException(status_code=400, detail={"error": "provider_error", "message": str(e)})

    # Parse JSON with a few guard rails so that slightly malformed outputs
    # do not completely break the UX.
    parsed, errors = _safe_parse_json(raw)
    if errors:
        run.log("parse", "json_error", {"error": errors[0]})

    # Persist outputs
    run_dir = OUTPUT_DIR / f"{json.dumps(None) or ''}"
    # fix: use run_id in directory name with timestamp
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{ts}_{run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "midi_plan_raw.txt"
    json_path = run_dir / "midi_plan.json"
    try:
        with raw_path.open("w", encoding="utf-8") as f:
            f.write(raw)
        run.log("persist", "raw_saved", {"file": str(raw_path)})
    except Exception as e:
        run.log("persist", "raw_failed", {"error": str(e)})
    if isinstance(parsed, dict):
        try:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(parsed, f)
            run.log("persist", "json_saved", {"file": str(json_path)})
        except Exception as e:
            run.log("persist", "json_failed", {"error": str(e)})

    # Build relative helpers
    def _rel(p: Path | None) -> str | None:
        if p is None:
            return None
        try:
            return str(p.relative_to(OUTPUT_DIR))
        except Exception:
            return p.name

    result: Dict[str, Any] = {
        "run_id": run.run_id,
        "system": system,
        "user": user,
        "raw": raw,
        "parsed": parsed,
        "errors": errors or None,
        "saved_raw_rel": _rel(raw_path),
        "saved_json_rel": _rel(json_path) if isinstance(parsed, dict) else None,
    }
    run.log("plan", "completed", {"ok": parsed is not None, "errors": (errors[:1] if errors else None)})
    return result


@router.get("/debug/{run_id}")
def get_debug(run_id: str):
    data = DEBUG_STORE.get(run_id)
    if not data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "run not found"})
    return data
