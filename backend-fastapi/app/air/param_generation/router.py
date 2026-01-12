from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import json
import os

# ten moduł wystawia endpointy fastapi dla kroku "param_generation".
#
# główna idea:
# - frontend wysyła opis muzyki (prompt) i ewentualne wartości startowe
# - backend buduje prompt systemowy + userowy i woła wybranego dostawcę llm
# - wynik (surowy tekst + próba parsowania json) zapisujemy do katalogu output
# - dodatkowo są endpointy pomocnicze do pracy z inventory (lista instrumentów i sample)
#   oraz do aktualizacji już wygenerowanego planu (meta i selected_samples)

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
    ChatError as _ProviderChatError,
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
    # prosta odpowiedź: lista dostawców llm, które są dostępne w konfiguracji
    providers: list[dict]


@router.get("/providers", response_model=ProvidersOut)
def providers() -> ProvidersOut:
    items = _providers_list()
    return ProvidersOut(providers=items)


@router.get("/models/{provider}")
def models(provider: str):
    """zwraca listę modeli dla wskazanego dostawcy.

    dodatkowo czyścimy i deduplikujemy listę, żeby frontend mógł bezpiecznie
    używać nazw modeli jako kluczy (np. w react), bez problemów z duplikatami.
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
    # preferujemy inventory (lista kanoniczna, może zawierać przyszłe instrumenty)
    try:
        if callable(_inventory_instruments):  # type: ignore
            inv_list = _inventory_instruments() or []
            if inv_list:
                return ", ".join(inv_list)
    except Exception:
        pass
    # ostateczny fallback (gdy inventory nie jest dostępne).
    # staramy się trzymać nazw blisko tych z inventory, żeby późniejsze mapowanie działało sensownie.
    return "Piano, Pad, Violin, Lead, Bass, Electric Guitar, Acoustic Guitar, Kick, Snare, Hat, Clap"


def _parameter_plan_system(plan: ParameterPlanIn) -> tuple[str, str]:
    """buduje teksty promptów (system i user) dla modelu llm.

    co ma zrobić llm:
    - przełożyć opis użytkownika na "parametry muzyczne" (tempo, tonacja, metrum, instrumenty itd.)
    - zwrócić tylko json (bez markdown), zgodny ze schematem opisanym w system prompt

    czego llm ma nie robić:
    - nie ma generować konkretnych nut ani danych midi (to inny krok pipeline)
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
    # do llm wysyłamy głównie opis użytkownika (prompt).
    # konkretne wartości parametrów llm dobiera sam, ale w ramach ograniczeń ze schematu.
    user = json.dumps({
        "task": "plan_music_parameters",
        "user_prompt": getattr(plan, "prompt", None),
    }, separators=(",", ":"), ensure_ascii=False)
    return system, user


def _call_model(provider: str, model: Optional[str], system: str, user: str) -> str:
    """wykonuje wywołanie do wybranego dostawcy llm i zwraca surowy tekst odpowiedzi.

    ten wrapper jest "defensywny":
    - różni dostawcy zwracają dane w różnych strukturach
    - szczególnie dla gemini próbujemy kilku ścieżek odczytu tekstu, bo `.text` bywa puste
    """
    provider = (provider or "gemini").lower()

    def _pick_model(explicit: Optional[str], env_name: str, fallback: str) -> str:
        # docker-compose potrafi wstrzyknąć zmienną jako pusty string (""),
        # a wtedy os.getenv zwraca "" zamiast fallbacku. Traktujemy "" jak brak.
        try:
            x = (explicit or "").strip()
            if x:
                return x
        except Exception:
            pass
        try:
            x = (os.getenv(env_name) or "").strip()
            if x:
                return x
        except Exception:
            pass
        return fallback

    # openai
    if provider == "openai":
        client = _get_openai_client()
        use_model = _pick_model(model, "OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        return (resp.choices[0].message.content or "").strip()

    # anthropic
    if provider == "anthropic":
        client = _get_anthropic_client()
        use_model = _pick_model(model, "ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
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

    # gemini / google generative ai
    if provider == "gemini":
        g = _get_gemini_client()
        use_model = _pick_model(model, "GOOGLE_MODEL", "gemini-3-pro-preview")

        # nowsze sdk czasem oczekuje system_instruction w innym formacie; mamy fallback.
        try:
            m = g.GenerativeModel(use_model, system_instruction=system)
        except TypeError:
            # w części wersji sdk `system_instruction` oczekuje listy obiektów
            m = g.GenerativeModel(
                use_model,
                system_instruction=[{"role": "system", "parts": [system]}],
            )

        r = m.generate_content(user)

        # preferowana ścieżka: candidates -> content.parts[].text
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
            # jeśli się nie uda, próbujemy prostszych pól poniżej
            pass

        # fallback: r.text albo string z obiektu
        return (getattr(r, "text", None) or str(r) or "").strip()

    # openrouter (zgodne z api openai)
    if provider == "openrouter":
        client = _get_openrouter_client()
        # domyślny model dobrany pod ustrukturyzowane wyjście i darmowy tier
        use_model = _pick_model(model, "OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
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


def _map_provider_exception(e: Exception) -> tuple[int, dict[str, str]]:
    """Mapuje wyjątki z warstwy AI/providerów na sensowne kody HTTP.

    UI pokazuje `detail.message`, więc tutaj dbamy, żeby było to czytelne.
    """
    name = e.__class__.__name__
    message = str(e) or name

    # OpenAI SDK / httpx common cases (bez twardych importów typów)
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
        # 502/504 zamiast 400: to nie jest błąd użytkownika.
        status = 504 if "timeout" in message.lower() else 502
        err = "provider_timeout" if status == 504 else "provider_connection_error"
        hint = (
            "Nie udało się połączyć z providerem AI (sieć/DNS/firewall). "        )
        if status == 504:
            hint = (
                "Timeout podczas połączenia z providerem AI. "
                "Sprawdź łączność z internetem z kontenera backend, ewentualny firewall oraz obciążenie providera."
            )
        return status, {"error": err, "message": f"{hint} (details: {message})"}

    # Default: błąd provider'a (np. zły model, niepoprawny request)
    return 400, {"error": "provider_error", "message": f"Błąd providera AI. (details: {message})"}


# endpointy proxy do inventory (żeby ui mogło działać w obrębie jednego modułu api)
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
    # mapuje nazwę instrumentu z ui/llm na nazwy instrumentów obecne w inventory.
    #
    # dlaczego to jest potrzebne:
    # - użytkownik/llm może wpisać "drums" albo "hi-hat", a w inventory mamy np. "Hat"
    # - chcemy obsłużyć podstawowe synonimy i proste dopasowania, bez ciężkiego fuzzy-matchingu
    names = list((inv.get("instruments") or {}).keys()) if isinstance(inv.get("instruments"), dict) else []
    if not names:
        return []
    lower_map = {n.lower(): n for n in names}
    q = (name or "").strip()
    ql = q.lower()

    # synonimy i normalizacja nazw -> sprowadzamy do nazw, które typowo istnieją w inventory
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
        # fx i tekstury
        # "fx" traktujemy jako "cokolwiek fx-owego" obecnego w inventory.
        # nie hardcodujemy już nazw typu texture/downfilter itd., tylko wykrywamy je dynamicznie.
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

    # dopasowanie 1:1
    if q in names:
        return [q]
    # dopasowanie bez rozróżniania wielkości liter
    if ql in lower_map:
        return [lower_map[ql]]

    # agregatory grup (np. "drums" ma zwrócić kilka instrumentów perkusyjnych)
    if ql in ("drums", "drumkit"):
        # wybieramy tylko te części perkusji, które realnie istnieją w inventory
        drum_opts = ["Kick", "Snare", "Hat", "Clap"]
        return [x for x in drum_opts if x in names]

    # synonim -> instrument docelowy
    if ql in syn:
        tgt = syn[ql]
        # specjalny przypadek dla "fx": zwracamy wszystkie instrumenty, które wyglądają na fx
        if tgt == "fx":
            fx_like = []
            # heurystyka: nazwa instrumentu zawiera słowa kluczowe związane z efektami
            fx_keywords = ["fx", "texture", "impact", "riser", "subdrop", "swell"]
            for n in names:
                nl = n.lower()
                if any(k in nl for k in fx_keywords):
                    fx_like.append(n)
            if fx_like:
                return sorted(set(fx_like))
        # standardowe dopasowanie do jednego instrumentu
        if tgt in names:
            return [tgt]
        if tgt.lower() in lower_map:
            return [lower_map[tgt.lower()]]

    # proste poprawki liczby mnogiej
    if ql.endswith("s") and ql[:-1] in lower_map:
        return [lower_map[ql[:-1]]]
    if (ql + "s") in lower_map:
        return [lower_map[ql + "s"]]

    # dopasowanie po prefiksie / zawieraniu (ostatnia deska ratunku)
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
    # agregatory kategorii na podstawie wierszy z samplami (bardziej odporne niż same nazwy)
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
        # zwracamy też informację o rozpoznanych nazwach, żeby ułatwić debug i komunikaty w ui
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
    # opcjonalny identyfikator projektu, spójny między krokami param/midi/render
    project_id: Optional[str] = None


def _safe_parse_json(raw: str) -> tuple[Optional[Dict[str, Any]], list[str]]:
    """próbuje sparsować json z odpowiedzi modelu i zwraca (doc, błędy).

    zabezpieczenia (żeby nie wywalać całego ux przy drobnych problemach):
    - usuwa ewentualne płotki markdown (```json ... ```), jeśli model je dorzucił
    - przy pierwszej porażce próbuje uciąć tekst do ostatniej klamry `}`
        (częsty przypadek, gdy streaming uciął odpowiedź w połowie)
    """
    errors: list[str] = []
    text = (raw or "").strip()

    # usuwamy płotki markdown, jeśli model mimo zakazu je dodał
    if text.startswith("```"):
        try:
            # znajdujemy pierwsze zamknięcie ``` po otwarciu
            fence_end = text.index("```", 3) + 3
            # bierzemy zawartość do końcowego ``` (jeśli jest)
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
                # próbujemy uciąć do ostatniej klamry, jeśli odpowiedź była ucięta w połowie
                last_brace = text.rfind("}")
                if last_brace > 0:
                    text = text[: last_brace + 1]
                    errors.append(f"parse: truncated to last brace due to {e}")
                    continue
            errors.append(f"parse: {e}")
            break

    # nie udało się odzyskać poprawnego json
    return None, errors


@router.post("/plan")
def generate_parameter_plan(body: ParameterPlanRequest):
    run = DEBUG_STORE.start()
    run.log("plan", "start", {"provider": body.provider or "gemini", "model": body.model or None})
    provider_used = (body.provider or "gemini")
    model_used = body.model or None
    try:
        plan = ParameterPlanIn(**(body.parameters or {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    system, user = _parameter_plan_system(plan)
    try:
        run.log("provider_call", "request", {
            "provider": provider_used,
            "model": model_used,
            "system": system,
            "user": user,
        })
        raw = _call_model(provider_used, model_used, system, user)
        run.log("provider_call", "raw_received", {"chars": len(raw)})
    except _ProviderChatError as e:
        # typowo: brak klucza api / brak sdk
        run.log("provider_call", "failed", {"type": e.__class__.__name__, "error": str(e)})
        raise HTTPException(
            status_code=400,
            detail={
                "error": "provider_config",
                "message": str(e),
                "run_id": run.run_id,
                "provider": provider_used,
                "model": model_used,
            },
        )
    except Exception as e:
        status, detail = _map_provider_exception(e)
        run.log("provider_call", "failed", {"type": e.__class__.__name__, "error": str(e), "mapped": detail.get("error")})
        # dołączamy run_id i kontekst do błędu, żeby dało się go zdebugować przez /debug/{run_id}
        try:
            if isinstance(detail, dict):
                detail = {
                    **detail,
                    "run_id": run.run_id,
                    "provider": provider_used,
                    "model": model_used,
                }
        except Exception:
            pass
        raise HTTPException(status_code=status, detail=detail)

    # parsowanie json z kilkoma "barierkami", żeby drobne błędy formatu nie psuły całego ux
    parsed, errors = _safe_parse_json(raw)
    if errors:
        run.log("parse", "json_error", {"error": errors[0]})

    # dopisujemy oryginalny prompt użytkownika obok wyniku llm.
    # trzymamy to na top-level (poza meta), żeby późniejszy patch /meta tego nie nadpisywał.
    if isinstance(parsed, dict):
        try:
            parsed.setdefault("user_prompt", getattr(plan, "prompt", "") or "")
        except Exception:
            parsed.setdefault("user_prompt", "")

    # zapis wyników do plików (do debugowania i możliwości odtworzenia stanu)
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

    # helper do tworzenia ścieżek względnych względem katalogu output
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
    """zwraca zapisany parameter_plan.json oraz podstawowe metadane dla danego run_id.

    to jest używane przez frontend do ponownego załadowania stanu kroku parametrów
    (np. gdy użytkownik wróci z kolejnych kroków pipeline).
    """

    # znajdujemy katalog runu po wzorcu *_<run_id>/parameter_plan.json
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

    # w niektórych przypadkach zapisany plik mógł zawierać "śmieci" na końcu
    # (np. doklejone fragmenty lub nadmiarowe klamry). żeby nie blokować ux,
    # próbujemy znaleźć najdłuższy poprawny prefiks json.
    try:
        text = json_path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "plan_read_failed", "message": str(e)})

    # 1) szybka ścieżka: całość jest poprawnym json-em
    try:
        doc = json.loads(text)
    except Exception:
        # 2) szukamy najdłuższego poprawnego prefiksu od pierwszej klamry
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
    """payload do aktualizacji wyboru sampli dla gotowego planu.

    oczekiwany format:
    {
        "selected_samples": {"Piano": "piano_001", "Bass": "bass_013"}
    }
    """

    selected_samples: Dict[str, str]


@router.patch("/plan/{run_id}/selected-samples")
def update_selected_samples(run_id: str, body: SelectedSamplesUpdate):
    """zapisuje/aktualizuje pole meta.selected_samples w istniejącym parameter_plan.json.

    ten endpoint nie dotyka logiki llm.
    służy wyłącznie do tego, aby frontend (po wyborze sampli z inventory)
    mógł powiązać instrumenty z konkretnymi id sampli (z inventory.json).
    """

    # odnajdujemy katalog runu w OUTPUT_DIR (wariant prosty: pattern *_<run_id>/parameter_plan.json)
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
        # używamy tej samej strategii "najdłuższego poprawnego prefiksu json"
        # co w get_parameter_plan, żeby poradzić sobie z ewentualnymi śmieciami na końcu pliku
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

        # prosta walidacja: tylko string->string, bez pustych wartości
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
    """payload do pełnej aktualizacji pola meta w parameter_plan.json.

    oczekujemy struktury zgodnej z ParamPlan/ParamPlanMeta z frontendu, np.:
    {
        "meta": { ... pełen obiekt ParamPlan ... }
    }
    """

    meta: Dict[str, Any]


@router.patch("/plan/{run_id}/meta")
def update_meta(run_id: str, body: MetaUpdate):
    """nadpisuje całe pole doc["meta"] w istniejącym parameter_plan.json.

    używane przez frontend po istotnych zmianach w panelu parametrów.
    celem jest to, aby backendowy parameter_plan.json pozostał "źródłem prawdy"
    dla późniejszych odczytów (np. przy powrocie tylko po run_id).
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

        # używamy tej samej strategii prefiksowej co w get_parameter_plan,
        # żeby poradzić sobie z ewentualnymi śmieciami na końcu pliku
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

        # podmieniamy całe meta obiektem z frontendu, ale zachowujemy ewentualne
        # istniejące selected_samples, jeśli frontend ich nie nadpisuje
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
