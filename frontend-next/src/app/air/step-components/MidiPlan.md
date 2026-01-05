# Krok 2 — MIDI Generation (MidiPlan)

Ten dokument opisuje logikę kroku 2 po stronie frontendu: generowanie planu MIDI na bazie meta z kroku 1, obsługę `run_id`, walidację/ostrzeżenia oraz wizualizację wyniku w pianoroll.

Zakres: logika w komponentach:
- `MidiPlanStep.tsx` — orkiestracja kroku 2, integracja z backendem, stan kroku.
- `MidiPianoroll.tsx` — wizualizacja JSON MIDI (pattern/layers) w HTML/CSS.
- `ProblemDialog.tsx` — prezentacyjny dialog ostrzeżeń (bez logiki generowania).

---

## Cel kroku 2

Krok 2 zamienia meta z kroku 1 (`ParamPlanMeta`) na szczegółowy plan MIDI:
1) wejście: `meta` (ParamPlanMeta) oraz opcjonalnie `paramRunId`.
2) użytkownik wybiera provider/model (AI).
3) frontend wysyła request do backendu `midi-generation`.
4) backend zwraca:
   - `run_id`,
   - JSON MIDI (pattern/layers + meta),
   - artefakty eksportu (np. ścieżka do `.mid` i obraz pianoroll).
5) frontend renderuje wynik oraz `MidiPianoroll`.

Wyjście z kroku 2:
- `MidiPlanResult` (przekazywany wyżej przez `onReady`) — wykorzystywany bezpośrednio w kroku 3 (render audio).
- `run_id` (przekazywany wyżej przez `onRunIdChange`) — używany do odtwarzania stanu kroku 2 oraz do eksportów.

---

## Konfiguracja API

W `MidiPlanStep.tsx` endpointy są budowane przez:

```ts
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
const MODULE_PREFIX = "/air/midi-generation";
```

Dodatkowo krok 2 korzysta z endpointów `param-generation` do pobrania list providerów/modeli i dostępnych instrumentów:

```ts
const PROVIDERS_URL = `${API_BASE}/api/air/param-generation/providers`;
const MODELS_URL = (p: string) => `${API_BASE}/api/air/param-generation/models/${encodeURIComponent(p)}`;
const AVAILABLE_INSTRUMENTS_URL = `${API_BASE}/api/air/param-generation/available-instruments`;
```

To celowe: źródłem providerów/modeli jest jeden moduł (param-generation), a midi-generation wykorzystuje tę samą konfigurację.

---

## Model danych: `MidiPlanResult`

Wynik kroku 2 ma typ `MidiPlanResult`:

```ts
export type MidiPlanResult = {
  run_id: string;
  midi: any;
  artifacts: {
    midi_json_rel?: string | null;
    midi_mid_rel?: string | null;
    midi_image_rel?: string | null;
  };
  midi_per_instrument?: Record<string, any> | null;
  artifacts_per_instrument?: Record<string, { ... }> | null;
  provider?: string | null;
  model?: string | null;
  errors?: string[] | null;
};
```

Ważne:
- `midi` jest typowane jako `any`, bo struktura może ewoluować (backend prompt/format).
- `artifacts` trzyma relatywne ścieżki (backendowe), wykorzystywane później do eksportu.
- `errors` jest traktowane jako źródło ostrzeżeń (nie zawsze krytycznych).

---

## Stan komponentu `MidiPlanStep`

Najważniejsze elementy stanu:
- `providers`, `provider`, `models`, `model` — wybór dostawcy/modelu.
- `loading`, `error` — statusy requestu.
- `result: MidiPlanResult | null` — bieżący wynik kroku.
- `systemPrompt`, `userPrompt`, `rawText`, `normalized` — podgląd wymiany z modelem.
- `availableInstruments` — lista instrumentów dostępnych w inventory (dla ostrzeżeń).
- `problemOpen`, `problemTitle`, `problemDescription`, `problemDetails` — dialog ostrzeżeń/błędów (`ProblemDialog`).

Źródłem prawdy dla UI jest `result` w stanie React.

---

## Pobieranie danych pomocniczych (useEffect)

### 1) Lista providerów
Endpoint:
- `GET /api/air/param-generation/providers`

Po pobraniu:
- ustawiana jest lista providerów,
- preferowany jest `gemini`, jeśli istnieje,
- ustawiany jest model domyślny (`default_model`).

### 2) Lista modeli dla providera
Endpoint:
- `GET /api/air/param-generation/models/{provider}`

Frontend:
- usuwa duplikaty i puste wartości,
- ustawia `model` na pierwszy dostępny, jeśli dotychczasowy nie pasuje.

### 3) Lista instrumentów z inventory
Endpoint:
- `GET /api/air/param-generation/available-instruments`

To jest opcjonalne: brak inventory nie blokuje kroku 2.

---

## Odtworzenie wyniku po `initialRunId`

Jeżeli krok 2 dostaje `initialRunId`, próbuje odczytać wynik z backendu bez ponownego generowania.

Endpoint:
- `GET /api/air/midi-generation/run/{run_id}`

Fragment logiki:

```tsx
const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/run/${encodeURIComponent(initialRunId)}`);
...
setResult(data as MidiPlanResult);
setSystemPrompt(typeof data.system === "string" ? data.system : null);
setUserPrompt(typeof data.user === "string" ? data.user : null);
setRawText(typeof data.raw === "string" ? data.raw : null);
const parsed = data.parsed ?? data.midi ?? null;
setNormalized(parsed ?? null);
if (onReady) onReady(data as MidiPlanResult);
if (onRunIdChange) onRunIdChange(initialRunId);
```

Ważne:
- `normalized` jest ustawiane z `data.parsed` (jeśli istnieje), a w fallbacku z `data.midi`.
- efekt nie odpala się, jeżeli `result` już istnieje (żeby nie nadpisywać świeżo wygenerowanego wyniku).

---

## Główna akcja: generowanie MIDI (POST /compose)

Za generowanie odpowiada funkcja `handleRun()`.

Warunek uruchomienia:
- `meta` musi istnieć,
- `loading` musi być `false`.

Endpoint:
- `POST /api/air/midi-generation/compose`

Body:
- `meta` — ParamPlanMeta z kroku 1,
- `provider`,
- `model` (lub `null`),
- opcjonalnie `param_run_id` (jeśli krok 1 zwrócił run_id i chcemy spiąć eksporty).

```tsx
const body: any = { meta, provider, model: model || null };
if (paramRunId) body.param_run_id = paramRunId;

const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/compose`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
```

Obsługa błędów HTTP:
- jeżeli backend zwraca `detail.message`, ten tekst jest preferowany jako komunikat.

Po sukcesie:
- `result` jest ustawiany na odpowiedź backendu,
- `systemPrompt`, `userPrompt`, `rawText`, `normalized` są zapisywane do debug view,
- `onReady(data)` jest wywoływane dla rodzica,
- `onRunIdChange(data.run_id)` aktualizuje stan w rodzicu.

---

## Ostrzeżenia i walidacja wyniku

Krok 2 ma logikę „niewstrzymujących” ostrzeżeń (pokazywanych w `ProblemDialog`).

Źródła ostrzeżeń:

1) `data.errors` z backendu

```ts
const errorsArr = Array.isArray(data?.errors) ? data.errors.filter(e => typeof e === "string" && e.trim()) : [];
```

2) Braki instrumentów w inventory
- instrumenty wymagane przez plan (preferencyjnie `data.midi.meta.instruments`, fallback: `meta.instruments`) są porównywane z `availableInstruments`.

```ts
const reqInstrumentsRaw = (data?.midi?.meta?.instruments ?? meta?.instruments ?? []) as any;
const reqInstruments = Array.isArray(reqInstrumentsRaw) ? reqInstrumentsRaw.filter(x => typeof x === "string" && x.trim()) : [];
...
const missing = reqInstruments.filter(inst => !availableInstruments.includes(inst));
```

3) Braki w artefaktach eksportu
- brak `.mid` i/lub brak SVG pianoroll traktowany jest jako ostrzeżenie.

```ts
const midRel = artifacts?.midi_mid_rel;
const svgRel = artifacts?.midi_image_rel;
if (!midRel) warn.push("Nie wygenerowano pliku .mid (brak mido albo błąd eksportu)." );
if (!svgRel) warn.push("Nie wygenerowano pianoroll SVG (pusty pattern lub błąd renderowania)." );
```

Ostrzeżenia są deduplikowane i prezentowane:

```ts
const uniqWarn = Array.from(new Set(warn));
if (uniqWarn.length > 0) {
  setProblemTitle("Wykryto problem w kroku MIDI");
  setProblemDescription("Możesz kontynuować z aktualnym wynikiem lub ponowić generowanie.");
  setProblemDetails(uniqWarn);
  setProblemOpen(true);
}
```

Ważne: ostrzeżenia nie blokują przejścia dalej — użytkownik decyduje, czy kontynuować.

---

## Nawigacja do kroku 3

Po wygenerowaniu `result`, UI pokazuje przycisk:
- „Przejdź do renderowania ścieżek audio”

Jest to tylko callback do rodzica:

```tsx
onClick={() => onNavigateNext && onNavigateNext()}
```

Rodzic (strona AIR) kontroluje faktyczną zmianę kroku.

---

## Podgląd debug: kontekst wymiany z modelem

Analogicznie jak w kroku 1, krok 2 ma `<details>`:
- system prompt,
- user payload,
- normalizowana odpowiedź,
- surowy tekst (fallback, jeśli nie ma normalizowanej odpowiedzi).

Służy to do diagnostyki sytuacji, w której model nie trzyma się formatu JSON.

---

## Wizualizacja: `MidiPianoroll`

`MidiPianoroll.tsx` renderuje prosty pianoroll w HTML/CSS (bez canvas).

### Wejście

```ts
type MidiData = {
  pattern?: MidiLayer[];
  layers?: Record<string, MidiLayer[]>;
  meta?: { tempo?: number; bars?: number } & Record<string, any>;
};
```

Wizualizacja zakłada domyślnie `stepsPerBar = 8` (zgodnie z backendowym promptem).

### Budowa lane’ów (ścieżek)

Komponent w `useMemo()`:
- iteruje `midi.layers` i buduje lane per instrument (`pushLayer()`),
- iteruje `midi.pattern` (perkusja) i próbuje rozbić pattern na lane per instrument przez mapowanie nut GM → instrument.

Perkusja: mapowanie instrumentu do nut (przykłady):
- Kick → 36
- Snare → 38
- Hat → 42 / 46
- Crash → 49

Mechanizm pattern:
1) zbiera potencjalne instrumenty perkusyjne z `midi.meta.instrument_configs` (rola „percussion”),
2) fallback do `midi.meta.instruments`,
3) ostateczny fallback do domyślnego zestawu (Kick/Snare/Hat/Crash/Ride/Tom),
4) buduje mapę „nuta → instrument” i rozdziela eventy.

### Gwarancja lane’ów dla instrumentów z meta
Jeżeli model zwrócił meta z instrumentami, ale bez eventów dla części z nich, UI i tak pokaże puste lane:

```ts
const requested = Array.isArray(meta.instruments) ? meta.instruments : [];
for (const inst of requested) {
  if (!lanes.some(l => l.instrument === inst)) lanes.push({ instrument: inst, events: [] });
}
```

### Zakres nut i czasu
Komponent oblicza:
- `minNote`, `maxNote` z eventów,
- `minAbsStep` i `totalSteps` (czas) z `bar * stepsPerBar + step`.

### Zoom i siatka
- `zoomX` skaluje szerokość komórki (czas),
- `zoomY` skaluje wysokość komórki (pitch),
- siatka jest rysowana przez `backgroundImage` (repeating-linear-gradient).

### Kolory
- lane’y dostają losowy kolor HSL (generowany przy pierwszym użyciu instrumentu).

### Stany brzegowe
- brak `midi` → komunikat „Brak danych MIDI do wizualizacji”.
- brak lane’ów (pusty pattern) → baner „Pusty pattern MIDI”.

---

## Najważniejsze endpointy backendu (krok 2)

- `GET /api/air/param-generation/providers`
- `GET /api/air/param-generation/models/{provider}`
- `GET /api/air/param-generation/available-instruments`
- `POST /api/air/midi-generation/compose`
- `GET /api/air/midi-generation/run/{run_id}`

---

## Następny dokument

Kolejny krok dokumentacji: render audio i eksport (krok 3) — `Render.md`.
