from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from typing import Any, Dict, Optional, List
from pathlib import Path
import json
import os

# ten moduł wystawia endpointy fastapi dla kroku midi_generation.
#
# rola tego kroku w pipeline:
# - bierze `meta` z param_generation (tempo, tonacja, instrumenty itd.)
# - woła llm, które ma zwrócić json z danymi midi (`pattern` i/lub `layers`)
# - zapisuje wynik na dysku przez `engine.generate_midi_and_artifacts`
# - umożliwia ponowne wczytanie runu z dysku przez endpoint /run/{run_id}

from .schemas import MidiGenerationIn, MidiGenerationOut, MidiArtifactPaths
from .engine import generate_midi_and_artifacts, _safe_parse_midi_json
from app.air.providers.client import (
    get_openai_client as _get_openai_client,
    get_anthropic_client as _get_anthropic_client,
    get_gemini_client as _get_gemini_client,
    get_openrouter_client as _get_openrouter_client,
    ChatError as _ProviderChatError,
)
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/air/midi-generation",
    tags=["air:midi-generation"],
    # uwaga: autoryzacja jest obecnie egzekwowana po stronie frontendu (/air/*).
    # endpointy w tym module są publiczne (na ten moment).
)

BASE_OUTPUT_DIR = Path(__file__).parent / "output"
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _map_provider_exception(e: Exception, *, default_error: str) -> tuple[int, dict[str, str]]:
    name = e.__class__.__name__
    message = str(e) or name

    network_names = {
        "APIConnectionError",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "TimeoutError",
        "APITimeoutError",
        "RemoteProtocolError",
    }
    auth_names = {"AuthenticationError", "PermissionDeniedError"}
    rate_names = {"RateLimitError"}

    if name in rate_names:
        return 429, {
            "error": "provider_rate_limited",
            "message": f"Provider AI zwrócił limit/rate limit. Spróbuj ponownie za chwilę. (details: {message})",
        }

    if name in auth_names:
        return 400, {
            "error": "provider_auth_error",
            "message": f"Błąd autoryzacji do providera AI. Sprawdź klucz API i ewentualnie BASE_URL. (details: {message})",
        }

    if name in network_names or "connection" in message.lower() or "timeout" in message.lower():
        status = 504 if "timeout" in message.lower() else 502
        err = "provider_timeout" if status == 504 else "provider_connection_error"
        hint = (
            "Nie udało się połączyć z providerem AI (sieć/DNS/firewall). "
        )
        if status == 504:
            hint = (
                "Timeout podczas połączenia z providerem AI. "
                "Sprawdź łączność z internetem z kontenera backend, ewentualny firewall oraz obciążenie providera."
            )
        return status, {"error": err, "message": f"{hint} (details: {message})"}

    return 400, {"error": default_error, "message": f"Błąd providera AI. (details: {message})"}


def _call_composer(provider: str, model: Optional[str], meta: Dict[str, Any]) -> tuple[str, str, str]:
    """wywołuje model llm, który ma zwrócić json z danymi midi.

    wejście do modelu opieramy na `meta` z param_generation.
    funkcja zwraca:
    - system: prompt systemowy (instrukcje + schemat json)
    - user: prompt użytkownika (payload json z meta)
    - content: surową odpowiedź tekstową modelu (powinna być json-em)
    """

    provider = (provider or "gemini").lower()

    key = str(meta.get("key") or "C")
    scale = str(meta.get("scale") or "Major")

    system = (
        "You are a Professional MIDI Orchestrator. Your task is to generate MIDI data for ALL requested instruments without exception. "
        "Respond ONLY with valid minified JSON. No markdown, no comments.\n\n"

        "### SEGREGATION LOGIC:\n"
        "1. **Percussion (pattern)**: Every instrument in `meta.instruments` with a role of 'Percussion' (e.g., Kick, Snare, Hat, Tom, Ride, Crash) MUST have its own events within the 'pattern' array using standard MIDI notes.\n"
        "2. **Melodic (layers)**: Every instrument in `meta.instruments` with roles like 'Lead', 'Bass', 'Pad', 'Accompaniment' MUST have a dedicated key in the 'layers' object.\n\n"

        "### CONSTRAINTS:\n"
        "1. **Exhaustive Coverage**: You MUST NOT skip any instrument listed in `meta.instruments`. Even if an instrument (like 'Tom' or 'Ride') plays only once, it must be present in the JSON.\n"
        "2. **Grid**: Use exactly 8 steps per bar (0-7). 8th-note grid.\n"
        "3. **Drum Mapping**: Kick: 36, Snare: 38, Clap: 39, Rim: 37, Closed Hat: 42, Open Hat: 46, Crash: 49, Ride: 51, Splash: 55, Shake: 82, 808: 35, Low Tom: 45, Mid Tom: 47, High Tom: 50.\n"
        f"4. **Music Theory**: All notes in 'layers' MUST be in the scale of {key} {scale}. For Rock, use power chords (root + fifth) for guitars.\n"
        "5. **Velocity & Length**: Use velocity (0-127) to create groove. 'len' 1 = 8th note, 2 = quarter note.\n\n"

        "### JSON SCHEMA:\n"
        "{"
        "\"pattern\":[{\"bar\":int,\"events\":[{\"step\":int,\"note\":int,\"vel\":int,\"len\":int}]}], "
        "\"layers\":{\"InstrumentName\":[{\"bar\":int,\"events\":[{\"step\":int,\"note\":int,\"vel\":int,\"len\":int}]}]}, "
        "\"meta\":{\"status\":\"success\"}"
        "}\n\n"

        "### COMPOSITION STRATEGY:\n"
        "- **Full Arrangement**: Ensure the interaction between 'Electric Guitar' and 'Bass Guitar' is tight.\n"
        "- **Drums**: Use all requested percussion types. If 'Ride' is requested, use it for steady rhythms; if 'Crash' is requested, use it on step 0 of new sections."
    )

    user_payload = {
        "task": "compose_midi_pattern",
        "meta": meta,
    }

    import json

    user = json.dumps(user_payload, separators=(",", ":"), ensure_ascii=False)

    # openai
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

    # anthropic
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

    # gemini
    if provider == "gemini":
        g = _get_gemini_client()
        use_model = model or os.getenv("GOOGLE_MIDI_MODEL", os.getenv("GOOGLE_MODEL", "gemini-3-pro-preview"))
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

    # openrouter
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
    """główny endpoint: przyjmuje meta z param_generation i generuje dane midi + artefakty.

    typowy scenariusz w ui:
    1) /air/param-generation/plan -> pobranie `parsed.meta`
    2) /air/midi-generation/compose -> wysłanie meta i odebranie run_id + plików output
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
        # ręcznie wstrzyknięty json (debug / eksperymenty)
        raw_midi_json = req.ai_midi
    else:
        try:
            system, user, raw_text = _call_composer(provider, model, meta)
        except HTTPException:
            raise
        except _ProviderChatError as e:
            raise HTTPException(status_code=400, detail={"error": "provider_config", "message": str(e)})
        except Exception as e:
            status, detail = _map_provider_exception(e, default_error="composer_error")
            raise HTTPException(status_code=status, detail=detail)
        parsed, parse_errors = _safe_parse_midi_json(raw_text)
        raw_midi_json = parsed
        errors.extend(parse_errors)

    from .engine import generate_midi_and_artifacts

    (
        run_id,
        midi_data,
        artifacts,
        midi_per_instrument,
        artifacts_per_instrument,
    ) = generate_midi_and_artifacts(meta, raw_midi_json)

    # best-effort powiązanie runów:
    # w tej aplikacji render_run_id == midi run_id, a param_run_id przechowujemy osobno,
    # żeby później dało się wyeksportować artefakty param+midi+render razem.
    try:
        if getattr(req, "param_run_id", None):
            from app.air.export.links import link_param_to_render

            link_param_to_render(run_id, str(req.param_run_id))
    except Exception:
        # linkowanie jest opcjonalne i nie może wpływać na generowanie midi
        pass

    return MidiGenerationOut(
        run_id=run_id,
        midi=midi_data,
        artifacts=MidiArtifactPaths(**artifacts),
        midi_per_instrument=midi_per_instrument or None,
        artifacts_per_instrument={k: MidiArtifactPaths(**v) for k, v in (artifacts_per_instrument or {}).items()} or None,
        provider=provider,
        model=model,
        errors=errors or None,
        system=system,
        user=user,
        raw=raw_text,
        parsed=raw_midi_json,
    )


@router.get("/run/{run_id}", response_model=MidiGenerationOut)
def get_midi_run(run_id: str) -> MidiGenerationOut:
    """zwraca zapisany stan midi dla danego run_id z dysku.

    frontend używa tego do ponownego załadowania kroku midi (np. po odświeżeniu strony):
    - pattern/layers
    - ścieżki do artefaktów
    - podział per instrument (jeśli istnieje)
    """

    # struktura katalogu jest zgodna z generate_midi_and_artifacts: *_<run_id>/midi.json itd.
    run_dir: Optional[Path] = None
    for p in BASE_OUTPUT_DIR.iterdir():
        if not p.is_dir():
            continue
        if p.name.endswith(run_id) and (p / "midi.json").exists():
            run_dir = p
            break
    if run_dir is None:
        raise HTTPException(status_code=404, detail={"error": "midi_not_found", "message": "midi.json not found for run_id"})

    midi_json_path = run_dir / "midi.json"
    try:
        midi_data: Dict[str, Any] = json.loads(midi_json_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "midi_read_failed", "message": str(e)})

    # artefakty globalne
    def _rel(p: Optional[Path]) -> Optional[str]:
        if p is None:
            return None
        try:
            return str(p.relative_to(BASE_OUTPUT_DIR))
        except Exception:
            return p.name

    midi_mid_path = run_dir / "midi.mid"
    midi_svg_path = run_dir / "pianoroll.svg"

    artifacts = MidiArtifactPaths(
        midi_json_rel=_rel(midi_json_path),
        midi_mid_rel=_rel(midi_mid_path) if midi_mid_path.exists() else None,
        midi_image_rel=_rel(midi_svg_path) if midi_svg_path.exists() else None,
    )

    # per-instrument midi + artefakty
    midi_per_instrument: Dict[str, Dict[str, Any]] = {}
    artifacts_per_instrument: Dict[str, MidiArtifactPaths] = {}

    for p in run_dir.glob("midi_*.json"):
        if p.name == "midi.json":
            continue
        name = p.stem[len("midi_"):]
        try:
            inst_midi = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        midi_per_instrument[name] = inst_midi

        inst_mid = run_dir / f"midi_{name}.mid"
        inst_svg = run_dir / f"pianoroll_{name}.svg"
        artifacts_per_instrument[name] = MidiArtifactPaths(
            midi_json_rel=_rel(p),
            midi_mid_rel=_rel(inst_mid) if inst_mid.exists() else None,
            midi_image_rel=_rel(inst_svg) if inst_svg.exists() else None,
        )

    return MidiGenerationOut(
        run_id=run_id,
        midi=midi_data,
        artifacts=artifacts,
        midi_per_instrument=midi_per_instrument or None,
        artifacts_per_instrument=artifacts_per_instrument or None,
        provider=None,
        model=None,
        errors=None,
        system=None,
        user=None,
        raw=None,
        parsed=midi_data,
    )