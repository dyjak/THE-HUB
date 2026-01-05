# Krok 1 — Param Generation (ParamPlan)

Ten dokument opisuje logikę kroku 1 po stronie frontendu: generowanie planu parametrów (ParamPlan) przez model AI, jego normalizację, edycję w UI oraz synchronizację wybranych danych z backendem.

Zakres: logika w komponentach:
- `ParamPlanStep.tsx` — orkiestracja kroku 1, integracja z backendem, stan kroku.
- `ParamPanel.tsx` — UI edycji ParamPlan + konfiguracje instrumentów + wybór sampli.
- `SampleSelector.tsx` — pobieranie listy sampli dla instrumentu i wybór sampla.
- `lib/paramTypes.ts`, `lib/paramUtils.ts` — typy i normalizacja danych.

> Uwaga: w repo istnieją inne README dla komponentów UI — w tym dokumencie skupiamy się na przepływie danych i wywołaniach backendu.

---

## Cel kroku 1

Krok 1 ma przygotować "meta" dla kolejnych etapów:
1) Użytkownik wpisuje prompt (opis utworu).
2) Frontend wysyła żądanie do backendu modułu `param-generation` (provider/model).
3) Backend zwraca wynik (run_id + parsed/raw + opcjonalne ostrzeżenia).
4) Frontend normalizuje wynik do `ParamPlan` i udostępnia panel edycji.
5) Użytkownik może:
   - zmieniać parametry muzyczne,
   - dobierać instrumenty,
   - edytować konfiguracje instrumentów,
   - wybierać konkretne sample.
6) Jeżeli znamy `run_id`, część zmian jest synchronizowana do backendu przez endpointy PATCH.

Wyjście z kroku 1 (dla reszty aplikacji):
- `ParamPlan` (meta) — wykorzystywane przez krok 2 (MIDI plan).
- `selectedSamples: Record<instrument, sampleId>` — wykorzystywane przez krok 3 (render) oraz opcjonalnie persistowane do backendu.
- `run_id` — używany do odtworzenia stanu kroku 1 po odświeżeniu strony i do spinania eksportów.

---

## Gdzie krok 1 jest używany

Główny orkiestrator kroków to strona AIR. Komponent kroku 1 jest wołany jako:

```tsx
<ParamPlanStep
  onMetaReady={...}
  onNavigateNext={...}
  onPlanChange={(plan, samples) => { setParamPlan(plan); setSelectedSamples(samples); }}
  initialRunId={runIdParam}
  onRunIdChange={(rid) => { setRunIdParam(rid); /* unieważnienie dalszych kroków */ }}
/>
```

Istotne zachowanie: zmiana `run_id` (czyli de facto wygenerowanie nowego planu) unieważnia dane z kolejnych kroków.

---

## Konfiguracja API

W `ParamPlanStep.tsx` endpointy są budowane przez stałe:

```ts
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
const MODULE_PREFIX = "/air/param-generation";
```

W konsekwencji wszystkie requesty w tym kroku idą na `API_BASE + API_PREFIX + MODULE_PREFIX + ...`.

---

## Model danych

### `ParamPlan` i `ParamPlanMeta`
Typy są zdefiniowane w `lib/paramTypes.ts`.

Kluczowe założenie: większość pól jest stringami, bo model AI może zwrócić wartości spoza list UI (UI ma tylko sugestie).

```ts
export interface ParamPlan {
  user_prompt?: string;
  style: string;
  genre: string;
  mood: string;
  tempo: number;
  key: string;
  scale: string;
  meter: string;
  bars: number;
  length_seconds: number;
  dynamic_profile: string;
  arrangement_density: string;
  harmonic_color: string;
  instruments: string[];
  instrument_configs: InstrumentConfig[];
  seed?: number | null;
}

export type ParamPlanMeta = ParamPlan;
```

### `InstrumentConfig`
`instrument_configs` to lista konfiguracji per instrument, trzymana równolegle do `instruments`.

```ts
export interface InstrumentConfig {
  name: string;
  register: string;
  role: string;
  articulation: string;
  dynamic_range: string;
}
```

### `selectedSamples`
W stanie frontendu jest to mapa: `instrument -> sampleId`.

Ta mapa jest:
- używana w `ParamPanel` do ustawiania selektora,
- przekazywana wyżej przez `onPlanChange`,
- opcjonalnie zapisywana w backendzie (gdy znamy `run_id`).

---

## Normalizacja danych z modelu

Backend może zwrócić `parsed.meta`, ale nie ma gwarancji kompletności.

Frontend robi normalizację przez `normalizeParamPlan()` z `lib/paramUtils.ts`:
- ujednolica wartości string (np. dopasowanie case-insensitive do sugestii UI, ale zachowuje niestandardowe wartości),
- clampuje liczby (`tempo`, `bars`, `length_seconds`),
- zapewnia, że `instruments` nie są puste,
- zapewnia spójne `instrument_configs` przez `ensureInstrumentConfigs()`.

Fragment normalizacji instrumentów i configów:

```ts
const instrumentsRaw = Array.isArray(input.instruments)
  ? input.instruments
  : typeof input.instruments === "string"
    ? input.instruments.split(",")
    : Array.from(DEFAULT_INSTRUMENTS);

const instruments = uniqueStrings(
  instrumentsRaw.map(item => String(item).trim()).filter(Boolean)
);

const parsedConfigs = configsRaw.map(toInstrumentConfig).filter(Boolean);
const instrument_configs = ensureInstrumentConfigs(instruments, parsedConfigs);
```

Dlaczego to jest potrzebne:
- model może zwrócić instrument bez configu,
- model może zwrócić config bez instrumentu,
- model może zwrócić wartości spoza list presetów.

---

## Stan komponentu `ParamPlanStep`

`ParamPlanStep.tsx` trzyma cały stan kroku 1. Najważniejsze pola:
- `prompt` — input użytkownika.
- `providers`, `provider`, `models`, `model` — wybór dostawcy/modelu.
- `loading`, `error`, `warnings` — statusy.
- `raw`, `parsed`, `normalized`, `systemPrompt`, `userPrompt` — debug/podgląd wymiany.
- `runId` — identyfikator bieżącego runu w backendzie.
- `midi: ParamPlan | null` — stan edycji planu (źródło prawdy dla UI).
- `available`, `selectable` — instrumenty dostępne w lokalnej bazie sampli.
- `selectedSamples` — mapa instrument -> sampleId.

Istotna zasada: frontend traktuje stan React jako źródło prawdy. Synchronizacja do backendu jest best-effort.

---

## Automatyczne pobieranie danych (useEffect)

### 1) Odtworzenie stanu po `initialRunId`
Jeżeli krok 1 dostaje `initialRunId`, próbuje pobrać zapisany plan z backendu.

Endpoint:
- `GET /api/air/param-generation/plan/{run_id}`

Logika:
- pobiera payload,
- wyciąga meta z `payload.plan.meta` (fallback: `payload.plan`),
- normalizuje do `ParamPlan`,
- ustawia `runId`, `midi` i `selectedSamples`.

Kluczowy fragment:

```tsx
const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(initialRunId)}`);
...
const rawMeta = (payload.plan.meta || payload.plan) as any;
...
const normalizedMidi = normalizeParamPlan(rawMeta);
const cloned = cloneParamPlan(normalizedMidi);
setMidi(cloned);
setRunId(initialRunId);
...
const sel = (payload.plan.meta?.selected_samples || payload.plan.selected_samples || {}) as Record<string, string>;
setSelectedSamples(sel);
```

### 2) Pobranie providerów
Endpoint:
- `GET /api/air/param-generation/providers`

Po pobraniu:
- ustawiana jest lista providerów,
- preferowany jest provider `gemini` (jeśli istnieje),
- ustawiany jest model domyślny (jeśli backend go zwraca jako `default_model`).

### 3) Pobranie modeli dla providera
Endpoint:
- `GET /api/air/param-generation/models/{provider}`

Frontend usuwa duplikaty oraz wybiera pierwszy model, jeśli nie ustawiono innego.

### 4) Pobranie listy dostępnych instrumentów
Endpoint:
- `GET /api/air/param-generation/available-instruments`

W tym widoku `selectable` jest równe `available` (pokazujemy tylko instrumenty, które backend realnie potrafi zrenderować).

---

## Główna akcja: generowanie planu parametrów (POST /plan)

Funkcja `send()` w `ParamPlanStep.tsx` odpowiada za główne wywołanie generowania.

Endpoint:
- `POST /api/air/param-generation/plan`

Body:
- `parameters` — startowe parametry (fallback, gdy model zwróci niepełne dane),
- `provider`, `model`.

Fragment:

```tsx
const parameters = {
  prompt,
  style: "ambient",
  mood: "calm",
  tempo: 80,
  key: "C",
  scale: "major",
  meter: "4/4",
  bars: 16,
  length_seconds: 180,
  dynamic_profile: "moderate",
  arrangement_density: "balanced",
  harmonic_color: "diatonic",
  instruments: ["piano", "pad", "strings"],
  instrument_configs: [],
  seed: null,
};

const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ parameters, provider, model }),
});
```

Odpowiedź backendu (konwencja):
- `run_id` — ID runu,
- `parsed` — znormalizowany JSON (po stronie backendu),
- `raw` — surowa odpowiedź modelu (tekst),
- `system`, `user` — kontekst promptów,
- `errors` — lista ostrzeżeń/błędów parsowania.

Co robi frontend po odpowiedzi:
1) zapisuje `runId` i emituje `onRunIdChange(runId)` do rodzica,
2) zapisuje `systemPrompt`, `userPrompt`, `raw`, `parsed` do podglądu,
3) buduje `norm` z `parsed.meta`:

```tsx
const parsed = payload?.parsed ?? null;
const norm = parsed?.meta ? { midi: parsed.meta } : null;
```

4) jeżeli `meta` istnieje: normalizuje do `ParamPlan`, klonuje i dodaje `user_prompt`:

```tsx
const normalizedMidi = normalizeParamPlan(midiPart as any);
const cloned = cloneParamPlan({ ...normalizedMidi, user_prompt: prompt });
setMidi(cloned);
```

5) resetuje `selectedSamples` dla świeżego planu:

```tsx
await updateSelectedSamples({});
```

6) buduje listę ostrzeżeń (`warnings`) i w razie potrzeby pokazuje `ProblemDialog`.

---

## Synchronizacja do backendu (PATCH)

### 1) Persist wyboru sampli
Funkcja `updateSelectedSamples(next)`:
- zawsze aktualizuje stan lokalny,
- jeżeli `runId` istnieje, wysyła PATCH do backendu.

Endpoint:
- `PATCH /api/air/param-generation/plan/{run_id}/selected-samples`

Body:
- `{ selected_samples: Record<string, string> }`

Fragment:

```tsx
await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(runId)}/selected-samples`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ selected_samples: cleaned }),
});
```

Ważne: request jest best-effort — błędy są ignorowane, aby nie blokować UX.

### 2) Persist meta (ParamPlan)
Funkcja `persistMeta(nextMeta)`:

Endpoint:
- `PATCH /api/air/param-generation/plan/{run_id}/meta`

Body:
- `{ meta: ParamPlan }`

Wywoływana z:
- `onUpdate` (zmiana parametrów),
- `onToggleInstrument` (dodanie/usunięcie instrumentu),
- `onUpdateInstrumentConfig` (zmiana configu instrumentu).

---

## Panel edycji: `ParamPanel`

`ParamPanel.tsx` renderuje:
1) parametry muzyczne (`style`, `mood`, `key`, `scale`, `meter`, `tempo`, `bars`, `length_seconds`, itd.),
2) listę instrumentów (przyciskowy wybór),
3) konfiguracje instrumentów (`instrument_configs`) + `SampleSelector`.

### Zachowanie: wartości spoza presetów
`ParamPanel` ma helper `withCurrent()`, który dodaje bieżącą wartość do listy `<select>`, jeśli nie ma jej w presetach (case-insensitive). Dzięki temu UI nie „gubi” nietypowych wartości zwróconych przez model.

```tsx
const withCurrent = (options, current) => {
  const base = Array.from(options);
  if (!current) return base;
  if (!base.some(opt => opt.toLowerCase() === current.toLowerCase())) base.push(current);
  return base;
};
```

### Ostrzeżenie o brakujących instrumentach
Panel pokazuje baner, jeśli `midi.instruments` zawiera instrumenty spoza `availableInstruments`.

To jest spójne z ostrzeżeniami generowanymi w `send()` po kroku POST.

---

## Wybór sampla: `SampleSelector`

`SampleSelector.tsx` ma dwa efekty:

### 1) Pobranie listy sampli dla instrumentu
Endpoint (proxy do inventory):
- `GET /api/air/param-generation/samples/{instrument}?limit=200`

Fragment:

```tsx
const res = await fetch(`${apiBase}${apiPrefix}${modulePrefix}/samples/${encodeURIComponent(instrument)}?limit=200`);
const data: SampleListResponse = await res.json();
setItems(Array.isArray(data.items) ? data.items : []);
```

### 2) Automatyczny wybór startowy
Jeżeli `selectedId` nie jest ustawione, a lista sampli przyszła:
- próbuje użyć podpowiedzi default (jeżeli backend ją zwróci),
- w przeciwnym razie losuje element z listy.

```tsx
if (!items || items.length === 0) return;
if (selectedId) return;
const fallback = preferred || items[Math.floor(Math.random() * items.length)];
if (fallback?.id) onChange(instrument, fallback.id);
```

To zachowanie jest celowe: UI nie zostaje „puste”, a użytkownik od razu ma odsłuch.

---

## Operacje edycyjne i ich skutki

### Zmiana parametrów
W `ParamPlanStep`:
- `setMidi(prev => ({ ...prev, ...patch }))`
- `persistMeta(next)` (best-effort)

### Toggle instrumentu
W `ParamPlanStep`:
1) dodaje/usuwa instrument z `midi.instruments`,
2) usuwa przypisany sample z `selectedSamples` dla usuniętego instrumentu,
3) przelicza `instrument_configs` przez `ensureInstrumentConfigs()`,
4) persistuje meta.

```tsx
const nextPlan: ParamPlan = {
  ...prev,
  instruments: nextInstruments,
  instrument_configs: ensureInstrumentConfigs(nextInstruments, prev.instrument_configs),
};
void persistMeta(nextPlan);
```

### Zmiana configu instrumentu
Modyfikuje element `instrument_configs` i ponownie dba o spójność przez `ensureInstrumentConfigs()`.

---

## Obsługa błędów i ostrzeżeń

W kroku 1 są dwa kanały sygnalizacji problemów:
- `error` — błąd krytyczny (np. request POST nieudany), pokazuje czerwony box.
- `warnings` + `ProblemDialog` — problemy niekrytyczne (np. parsowanie, brak meta, braki instrumentów), użytkownik może kontynuować albo ponowić generowanie.

Dodatkowo w UI jest sekcja `<details>` "Pełny kontekst wymiany z modelem" (system/user/normalized/raw) ułatwiająca debug.

---

## Kontrakt wejść/wyjść komponentu

Wejścia (`Props`):
- `initialRunId` — jeżeli podane, krok próbuje odtworzyć stan z backendu.
- `onRunIdChange` — emitowane po udanym POST /plan.
- `onPlanChange(plan, selectedSamples)` — ciągła synchronizacja do rodzica (React state).
- `onMetaReady(meta)` — sygnał „meta gotowe” (używane przez rodzica jako lekki callback).
- `onNavigateNext()` — nawigacja do kroku 2.

Wyjścia (dane runtime):
- `midi: ParamPlan | null`
- `selectedSamples: Record<string, string | undefined>`
- `runId: string | null`

---

## Checklista spójności (co musi być prawdą)

1) `midi.instruments` i `midi.instrument_configs` muszą odnosić się do tych samych instrumentów.
   - Zapewniane przez `ensureInstrumentConfigs()`.
2) Po usunięciu instrumentu nie powinno zostać przypisanie w `selectedSamples`.
   - Sprzątane w `onToggleInstrument`.
3) UI musi tolerować nietypowe wartości string z modelu.
   - `withCurrent()` w `ParamPanel`.
4) Brak synchronizacji do backendu nie może blokować pracy.
   - PATCH jest best-effort.

---

## Najważniejsze endpointy backendu (krok 1)

- `GET /api/air/param-generation/providers`
- `GET /api/air/param-generation/models/{provider}`
- `GET /api/air/param-generation/available-instruments`
- `POST /api/air/param-generation/plan`
- `GET /api/air/param-generation/plan/{run_id}`
- `PATCH /api/air/param-generation/plan/{run_id}/meta`
- `PATCH /api/air/param-generation/plan/{run_id}/selected-samples`
- `GET /api/air/param-generation/samples/{instrument}?limit=200`

---

## Następny dokument

Kolejny krok dokumentacji: MIDI generation (krok 2) — `MidiPlan.md`.
