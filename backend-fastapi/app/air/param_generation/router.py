from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import json
import os

from .schemas import ParameterPlanIn, ParameterPlanResult
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
router = APIRouter(
    prefix="/air/param-generation",
    tags=["air:param-generation"],
)

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
    """List available models for a given provider.

    We defensively de-duplicate and sanitize the list so that the
    frontend can safely use model names as React keys without
    encountering duplicates (e.g. Anthropic defaults).
    """
    raw = _models_list(provider) or []
    seen: set[str] = set()
    models: list[str] = []
    for m in raw:
        if not isinstance(m, str):
            continue
        name = m.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        models.append(name)
    return {"provider": provider, "models": models}


def _allowed_instruments_hint() -> str:
    # Prefer inventory (canonical list, may include future instruments)
    try:
        if callable(_inventory_instruments):  # type: ignore
            inv_list = _inventory_instruments() or []
            if inv_list:
                return ", ".join(inv_list)
    except Exception:
        pass
    # Final static fallback (no inventory available). Keep it close to
    # real inventory instrument names so that resolver + inventory stay aligned.
    return "Piano, Pad, Violin, Lead, Bass, Electric Guitar, Acoustic Guitar, Kick, Snare, Hat, Clap"


def _parameter_plan_system(plan: ParameterPlanIn) -> tuple[str, str]:
    """Build system and user prompts for the *parameter planner*.

    This agent is responsible ONLY for high-level musical parameters, not
    for concrete MIDI note sequences. It should return a JSON object with
    a single key `meta` that mirrors MidiPlanIn/MidiParameters-like fields.
    """
    allowed = _allowed_instruments_hint()
    system = (
        "You are an Expert Music Theorist and Orchestrator. Your role is to translate natural language descriptions "
        "into technical musical specifications for an AI backend. "
        "Respond ONLY with valid minified JSON. No markdown, no conversational filler.\n\n"
        
        "### JSON SCHEMA:\n"
        "{\"meta\":{"
        "\"style\":string,\"mood\":string,\"tempo\":number,\"key\":string,\"scale\":string,"
        "\"meter\":string,\"bars\":number,\"length_seconds\":number,"
        "\"dynamic_profile\":string,\"arrangement_density\":string,\"harmonic_color\":string,"
        "\"instruments\":[string],"
        "\"instrument_configs\":[{"
        "\"name\":string,\"role\":string,\"register\":string,\"articulation\":string,\"dynamic_range\":string"
        "}]}}\n\n"

        "### CONSTRAINTS & LOGIC:\n"
        "1. **Instrument Strictness**: You MUST ONLY use instrument names from this allowed list: [" + allowed + "]. "
        "If a user requests an instrument NOT in the list, substitute it with the closest available alternative (e.g., if 'Violin' is requested but not allowed, use 'Strings' or 'Lead Synth').\n"
        "2. **Consistency**: The number of items in 'instruments' must exactly match 'instrument_configs'. The 'name' field in both must be identical.\n"
        "3. **Musical Theory**: Ensure that 'tempo', 'scale', 'meter', and 'harmonic_color' are stylistically consistent (e.g., Techno usually has 120-130 BPM, 4/4 meter). "
        "Choose 'key' and 'scale' to match the 'mood' (e.g., Minor for sad/tense, Major for happy/bright).\n"
        "4. **Parameter Standards**:\n"
        "   - Role: [Lead, Accompaniment, Bass, Percussion, Pad, Texture, Harmony]\n"
        "   - Register: [Sub, Low, Mid, High, Very High, Full]\n"
        "   - Dynamic Range: [Pianissimo, Delicate, Moderate, Intense, Fortissimo]\n"
        "   - Articulation: [Sustain, Legato, Staccato, Pizzicato, Percussive, Muted, Tremolo]\n\n"
        
        "### TASK:\n"
        "Analyze the user's request for genre, energy, and instrumentation. "
        "Plan a professional arrangement that is coherent and mix-ready. "
        "Never use generic 'FX' names. Focus on the provided allowed list."
    )
    # For generative behavior we only send the high-level natural language
    # description from the user. All concrete parameter values are chosen by
    # the model within the schema constraints described in the system prompt.
    user = json.dumps({
        "task": "plan_music_parameters",
        "user_prompt": getattr(plan, "prompt", None),
    }, separators=(",", ":"), ensure_ascii=False)
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
        use_model = model or os.getenv("GOOGLE_MODEL", "gemini-3-pro-preview")

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

    # synonyms / normalization -> singular instrument naming
    syn = {
        # Core tonal families
        "pad": "Pad", "pads": "Pad",
        "bell": "Bell", "bells": "Bell",
        "pluck": "Pluck", "plucks": "Pluck",
        "lead": "Lead", "leads": "Lead",
        "synth": "Synth", "reese": "Reese",
        "bass": "Bass", "bass guitar": "Bass Guitar", "bass synth": "Bass Synth",
        "flute": "Flute",
        # Guitars: prefer explicit electric/acoustic when present in inventory
        "guitar": "Guitar", "guitars": "Guitar",
        "electric guitar": "Electric Guitar", "electric guitars": "Electric Guitar",
        "acoustic guitar": "Acoustic Guitar", "acoustic guitars": "Acoustic Guitar",
        "piano": "Piano",
        # String family / orchestral synonyms
        "violin": "Violin", "violins": "Violin",
        "cello": "Violin", "cellos": "Violin",
        "viola": "Violin", "violas": "Violin",
        "strings": "Violin", "string section": "Violin",
        "orchestra": "Brass",  # rough fallback if only brass/strings are available
        "brass": "Brass",
        # FX textures
        # FX bucket – treat "fx" as whatever FX-like instruments exist in inventory.
        # We DON'T hard-code Texture/Downfilter/etc. anymore; instead, we resolve
        # dynamically below based on what's actually present.
        "fx": "fx",
        # 808 / low percussion
        "808": "808",
        # high-level rhythm labels -> treat as drumkit / percussive set
        "drum": "Kick", "drums": "Kick", "drumkit": "Kick",
        "percussion": "Clap", "percussions": "Clap",
        # melodic plucked instrument not in inventory -> map to Pluck as a generic
        "harp": "Pluck", "harps": "Pluck",
        # drum parts
        "kick": "Kick", "kicks": "Kick",
        "snare": "Snare", "snares": "Snare",
        "clap": "Clap", "claps": "Clap",
        "hihat": "Hat", "hi-hat": "Hat", "hats": "Hat", "hat": "Hat", "hh": "Hat",
        # impacts / risers / swells
        "impact": "Impact", "impacts": "Impact",
        "riser": "Riser", "risers": "Riser",
        "subdrop": "Subdrop", "sub drop": "Subdrop",
        "swell": "Swell", "swells": "Swell",
    }

    # Exact
    if q in names:
        return [q]
    # Case-insensitive exact
    if ql in lower_map:
        return [lower_map[ql]]

    # Group aggregators
    if ql in ("drums", "drumkit"):
        # Prefer whatever concrete drum parts are actually present in the
        # current inventory, instead of relying on legacy plural forms.
        drum_opts = ["Kick", "Snare", "Hat", "Clap"]
        return [x for x in drum_opts if x in names]

    # Synonym resolution to a single instrument
    if ql in syn:
        tgt = syn[ql]
        # Special dynamic handling for the generic "fx" bucket:
        # map to all instruments that look like FX based on their
        # own name or category in the inventory.
        if tgt == "fx":
            fx_like = []
            # Heuristic: prefer instruments whose name contains "fx",
            # "Texture", "Impact", "Riser", "Subdrop", "Swell" etc.
            fx_keywords = ["fx", "texture", "impact", "riser", "subdrop", "swell"]
            for n in names:
                nl = n.lower()
                if any(k in nl for k in fx_keywords):
                    fx_like.append(n)
            if fx_like:
                return sorted(set(fx_like))
        # Standard single-target synonym resolution
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


class ParameterPlanRequest(BaseModel):
    parameters: Dict[str, Any]
    provider: Optional[str] = None
    model: Optional[str] = None
    # Opcjonalny identyfikator projektu, spójny między krokami param/midi/render.
    project_id: Optional[str] = None


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


@router.post("/plan")
def generate_parameter_plan(body: ParameterPlanRequest):
    run = DEBUG_STORE.start()
    run.log("plan", "start", {"provider": body.provider or "gemini", "model": body.model or None})
    try:
        plan = ParameterPlanIn(**(body.parameters or {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    system, user = _parameter_plan_system(plan)
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

    # Persist the original user prompt alongside model output.
    # Keep it top-level (not inside meta) so later PATCH /meta does not overwrite it.
    if isinstance(parsed, dict):
        try:
            parsed.setdefault("user_prompt", getattr(plan, "prompt", "") or "")
        except Exception:
            parsed.setdefault("user_prompt", "")

    # Persist outputs
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{ts}_{run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "parameter_plan_raw.txt"
    json_path = run_dir / "parameter_plan.json"
    try:
        with raw_path.open("w", encoding="utf-8") as f:
            f.write(raw)
        run.log("persist", "raw_saved", {"file": str(raw_path)})
    except Exception as e:
        run.log("persist", "raw_failed", {"error": str(e)})
    if isinstance(parsed, dict):
        try:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False)
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
        "project_id": body.project_id or None,
    }
    run.log("plan", "completed", {"ok": parsed is not None, "errors": (errors[:1] if errors else None)})
    return result


@router.get("/debug/{run_id}")
def get_debug(run_id: str):
    data = DEBUG_STORE.get(run_id)
    if not data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "run not found"})
    return data


@router.get("/plan/{run_id}")
def get_parameter_plan(run_id: str):
    """Zwraca zapisany parameter_plan.json oraz podstawowe metadane dla danego run_id.

    Używane przez frontend do ponownego załadowania stanu kroku parametrów
    (np. po powrocie z dalszych kroków).
    """

    # Znajdź katalog runu po wzorcu *_<run_id>/parameter_plan.json
    run_dir: Path | None = None
    for p in OUTPUT_DIR.iterdir():
        if not p.is_dir():
            continue
        if p.name.endswith(run_id) and (p / "parameter_plan.json").exists():
            run_dir = p
            break
    if run_dir is None:
        raise HTTPException(status_code=404, detail={"error": "plan_not_found", "message": "parameter_plan.json not found for run_id"})

    json_path = run_dir / "parameter_plan.json"
    raw_path = run_dir / "parameter_plan_raw.txt"

    # W niektórych przypadkach zapisany plik mógł zawierać śmieci na końcu
    # (np. doklejone fragmenty ścieżek plików lub nadmiarowe klamry). Żeby
    # nie blokować UX, próbujemy znaleźć najdłuższy poprawny prefiks JSON.
    try:
        text = json_path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": str(e)})

    # 1) Szybka ścieżka: całość jest poprawnym JSON-em.
    try:
        doc = json.loads(text)
    except Exception:
        # 2) Szukamy najdłuższego poprawnego prefiksu od pierwszej klamry.
        first = text.find("{")
        if first == -1:
            raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": "no json object start found"})

        last_error: Exception | None = None
        doc = None  # type: ignore[assignment]
        for i in range(len(text) - 1, first - 1, -1):
            chunk = text[first : i + 1]
            try:
                candidate = json.loads(chunk)
                if isinstance(candidate, dict):
                    doc = candidate
                    break
            except Exception as e:  # noqa: PERF203
                last_error = e
                continue

        if doc is None:
            raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": str(last_error or "unable to recover json")})

    raw_text: Optional[str] = None
    try:
        if raw_path.exists():
            raw_text = raw_path.read_text(encoding="utf-8")
    except Exception:
        raw_text = None

    return {
        "run_id": run_id,
        "plan": doc,
        "raw": raw_text,
        "saved_json_rel": str(json_path.relative_to(OUTPUT_DIR)),
        "saved_raw_rel": str(raw_path.relative_to(OUTPUT_DIR)) if raw_path.exists() else None,
    }


class SelectedSamplesUpdate(BaseModel):
    """Payload do aktualizacji wyboru sampli dla gotowego parameter planu.

    expected format:
    {
      "selected_samples": {"Piano": "piano_001", "Bass": "bass_013"}
    }
    """

    selected_samples: Dict[str, str]


@router.patch("/plan/{run_id}/selected-samples")
def update_selected_samples(run_id: str, body: SelectedSamplesUpdate):
    """Zapisz/aktualizuj pole meta.selected_samples w istniejącym parameter_plan.json.

    Ten endpoint nie dotyka logiki LLM – służy wyłącznie do tego, aby frontend
    po wyborze sampli z inventory mógł powiązać instrumenty z konkrentymi
    ID sampli (z inventory.json).
    """

    # Odnajdź katalog runu po saved_json_rel w istniejących plikach OUTPUT_DIR
    # (prosty wariant: pattern *_<run_id>/parameter_plan.json)
    try:
        run_dir: Path | None = None
        for p in OUTPUT_DIR.iterdir():
            if not p.is_dir():
                continue
            if p.name.endswith(run_id) and (p / "parameter_plan.json").exists():
                run_dir = p
                break
        if run_dir is None:
            raise HTTPException(status_code=404, detail={"error": "plan_not_found", "message": "parameter_plan.json not found for run_id"})
        json_path = run_dir / "parameter_plan.json"
        # Używamy tej samej strategii "najdłuższego poprawnego prefiksu JSON"
        # co w get_parameter_plan, żeby poradzić sobie z ewentualnymi śmieciami
        # na końcu pliku.
        try:
            text = json_path.read_text(encoding="utf-8")
        except Exception as e:  # noqa: PERF203
            raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": str(e)})

        try:
            doc = json.loads(text)
        except Exception:
            first = text.find("{")
            if first == -1:
                raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": "no json object start found"})

            last_error: Exception | None = None
            doc = None  # type: ignore[assignment]
            for i in range(len(text) - 1, first - 1, -1):
                chunk = text[first : i + 1]
                try:
                    candidate = json.loads(chunk)
                    if isinstance(candidate, dict):
                        doc = candidate
                        break
                except Exception as e:  # noqa: PERF203
                    last_error = e
                    continue

            if doc is None:
                raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": str(last_error or "unable to recover json")})

        if not isinstance(doc, dict):
            doc = {}
        meta = doc.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            doc["meta"] = meta

        # Prosta walidacja: tylko string->string, bez pustych wartości
        cleaned: Dict[str, str] = {}
        for k, v in (body.selected_samples or {}).items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            ik = k.strip()
            iv = v.strip()
            if not ik or not iv:
                continue
            cleaned[ik] = iv

        meta["selected_samples"] = cleaned

        try:
            json_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # noqa: PERF203
            raise HTTPException(status_code=500, detail={"error": "plan_write_failed", "message": str(e)})

        return {"run_id": run_id, "updated": True, "selected_samples": cleaned}
    except HTTPException:
        raise
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "selected_samples_update_failed", "message": str(e)})


class MetaUpdate(BaseModel):
    """Payload do pełnej aktualizacji pola meta w parameter_plan.json.

    Oczekujemy struktury zgodnej z ParamPlan/ParamPlanMeta z frontendu, np.:
    {
      "meta": { ... pełen obiekt ParamPlan ... }
    }
    """

    meta: Dict[str, Any]


@router.patch("/plan/{run_id}/meta")
def update_meta(run_id: str, body: MetaUpdate):
    """Nadpisz całe pole doc["meta"] w istniejącym parameter_plan.json.

    Używane przez frontend po każdej istotnej zmianie w Panelu parametrów,
    tak aby backendowy parameter_plan.json pozostał źródłem prawdy dla
    późniejszych odczytów (np. przy powrocie po samym run_id).
    """

    try:
        run_dir: Path | None = None
        for p in OUTPUT_DIR.iterdir():
            if not p.is_dir():
                continue
            if p.name.endswith(run_id) and (p / "parameter_plan.json").exists():
                run_dir = p
                break
        if run_dir is None:
            raise HTTPException(status_code=404, detail={"error": "plan_not_found", "message": "parameter_plan.json not found for run_id"})

        json_path = run_dir / "parameter_plan.json"

        try:
            text = json_path.read_text(encoding="utf-8")
        except Exception as e:  # noqa: PERF203
            raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": str(e)})

        # Użyjemy tej samej strategii prefiksowej, co w get_parameter_plan,
        # żeby poradzić sobie z ewentualnymi śmieciami na końcu pliku.
        try:
            doc = json.loads(text)
        except Exception:
            first = text.find("{")
            if first == -1:
                raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": "no json object start found"})

            last_error: Exception | None = None
            doc = None  # type: ignore[assignment]
            for i in range(len(text) - 1, first - 1, -1):
                chunk = text[first : i + 1]
                try:
                    candidate = json.loads(chunk)
                    if isinstance(candidate, dict):
                        doc = candidate
                        break
                except Exception as e:  # noqa: PERF203
                    last_error = e
                    continue

            if doc is None:
                raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": str(last_error or "unable to recover json")})

        if not isinstance(doc, dict):
            doc = {}

        # Podmień całe meta obiektem z frontendu, ale zachowaj ewentualne
        # istniejące selected_samples jeśli frontend ich nie nadpisuje.
        incoming_meta = dict(body.meta or {})
        existing_meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
        if isinstance(existing_meta, dict) and "selected_samples" in existing_meta and "selected_samples" not in incoming_meta:
            incoming_meta["selected_samples"] = existing_meta["selected_samples"]

        doc["meta"] = incoming_meta

        try:
            json_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # noqa: PERF203
            raise HTTPException(status_code=500, detail={"error": "plan_write_failed", "message": str(e)})

        return {"run_id": run_id, "updated": True}
    except HTTPException:
        raise
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "meta_update_failed", "message": str(e)})
