# AIR — orkiestrator kroków (frontend „mózg operacji”)

Ten dokument opisuje logikę strony orkiestrującej cały proces AIR: przełączanie kroków, trzymanie stanu pośredniego, zależności między krokami, obsługę `run_id` i synchronizację wyboru sampli do backendu.

Plik źródłowy:
- `src/app/air/page.tsx`

---

## Cel orkiestratora

Orkiestrator:
- trzyma aktualny krok widoku (`step`),
- trzyma dane wyprodukowane przez kroki (ParamPlan → MidiPlanResult → RenderResult),
- kontroluje kiedy dany krok jest „gotowy” do uruchomienia,
- obsługuje ostrzeżenie przy cofaniu się do wcześniejszego kroku,
- utrzymuje i persistuje wybór sampli (`selectedSamples`) do backendu (best-effort).

---

## Model kroków i nawigacja

### Identyfikatory kroków

```ts
type StepId = "param-plan" | "midi-plan" | "midi-export" | "render";
```

W praktyce w UI używane są 3 kroki:
- `param-plan` — Krok 1
- `midi-plan` — Krok 2
- `midi-export` — Krok 3 (RenderStep)

`render` jest placeholderem na przyszłość.

### Kolejność i "ready" gating

Orkiestrator definiuje kolejność i warunki dostępności:

```ts
const steps = [
  { id: "param-plan", ready: true },
  { id: "midi-plan", ready: !!paramPlan },
  { id: "midi-export", ready: !!midiResult },
];
```

Znaczenie:
- do kroku 2 nie przejdziesz bez `paramPlan`,
- do kroku 3 nie przejdziesz bez `midiResult`.

To jest świadomy „contract”: krok 2 wymaga meta, krok 3 wymaga wyniku MIDI.

---

## Stan trzymany w `page.tsx`

Najważniejsze pola stanu:

- `step: StepId` — aktualnie wyświetlany krok.
- `paramPlan: ParamPlan | null` — wynik kroku 1 (źródło meta).
- `midiResult: MidiPlanResult | null` — wynik kroku 2.
- `selectedSamples: Record<string, string | undefined>` — mapa instrument → sample_id.

Oraz identyfikatory runów:
- `runIdParam` — run_id kroku 1 (param-generation)
- `runIdMidi` — run_id kroku 2 (midi-generation)
- `runIdRender` — run_id kroku 3 (render)

---

## Przekazywanie danych między krokami

### Krok 1 → orkiestrator

`ParamPlanStep` emituje pełny plan + wybór sampli:

```tsx
onPlanChange={(plan, samples) => {
  setParamPlan(plan);
  setSelectedSamples(samples);
}}
```

To jest ważne: orkiestrator nie odpyta backendu o meta — bierze dane z React state.

### Krok 2 → orkiestrator

`MidiPlanStep` ustawia wynik MIDI:

```tsx
onReady={setMidiResult}
```

### Krok 3 → orkiestrator

`RenderStep` nie zwraca obecnie całego `RenderResult` wyżej. Orkiestrator trzyma natomiast:
- `runIdRender` przez `onRunIdChange` (umożliwia odtwarzanie kroku 3 przez `initialRunId`).

---

## Polityka „cofnięcia kroku” (utrata postępu)

Orkiestrator pokazuje dialog ostrzegawczy tylko przy cofnięciu do wcześniejszego kroku:

- wylicza indeksy w `stepOrder`,
- jeśli `nextIndex < currentIndex`, to nie zmienia kroku od razu, tylko ustawia `pendingStep` i pokazuje modal.

Efekt UX:
- przejście do przodu jest natychmiastowe,
- cofanie wymaga potwierdzenia.

---

## Unieważnianie wyników po zmianach

To jest jedna z najważniejszych części „mózgu operacji”: gdy wcześniejszy krok zmienia `run_id`, dalsze wyniki przestają być wiarygodne.

### Zmiana `runIdParam`

Gdy `ParamPlanStep` emituje zmianę run_id, orkiestrator:
- zapisuje `runIdParam`,
- a jeśli `rid` jest puste (reset), to czyści wyniki późniejszych kroków.

```tsx
onRunIdChange={(rid) => {
  setRunIdParam(rid);
  if (!rid) {
    setMidiResult(null);
    setRunIdMidi(null);
    setRunIdRender(null);
  }
}}
```

Założenie: jeśli nie mamy aktualnego param runu, nie ma sensu trzymać MIDI i render.

### Zmiana `runIdMidi`

Analogicznie dla kroku 2:

```tsx
onRunIdChange={(rid) => {
  setRunIdMidi(rid);
  if (!rid) {
    setMidiResult(null);
    setRunIdRender(null);
  }
}}
```

---

## Persist wyboru sampli do backendu (best-effort)

Orkiestrator posiada helper `persistSelectedSamples(next)`.

Cel:
- frontend nadal jest źródłem prawdy,
- ale backend dostaje kopię `selectedSamples` powiązaną z `runIdParam`, żeby można było:
  - odtworzyć projekt,
  - pokazać "co było wybrane" w artefaktach.

Endpoint:
- `PATCH /api/air/param-generation/plan/{runIdParam}/selected-samples`

Fragment:

```ts
await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(runIdParam)}/selected-samples`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ selected_samples: cleaned }),
});
```

Błędy są ignorowane, bo synchronizacja nie może blokować UX.

`RenderStep` dostaje callback:

```tsx
onSelectedSamplesChange={persistSelectedSamples}
```

Dzięki temu zmiany sampli w kroku 3 także trafiają do backendu (pod runem kroku 1), bez dublowania logiki w samym RenderStep.

---

## Odtwarzanie stanu po odświeżeniu

Każdy krok ma własny mechanizm „initialRunId”:
- krok 1: `initialRunId={runIdParam}`
- krok 2: `initialRunId={runIdMidi}`
- krok 3: `initialRunId={runIdRender}`

Orkiestrator trzyma te runId w stanie, więc po odświeżeniu strony (jeżeli są odtwarzane z zewnątrz) można odtworzyć wyniki kroków.

W aktualnej implementacji nie ma jeszcze globalnego mechanizmu zapisu/odczytu tych runId np. z URL lub localStorage — to jest tylko „interfejs” między orkiestratorem a krokami.

---

## Jak ta dokumentacja ma się do dokumentacji kroków

Orkiestrator jest spoiwem. Dokumenty kroków opisują szczegółowo:
- Param generation: `step-components/ParamPlan.md`
- MIDI generation: `step-components/MidiPlan.md`
- Render + export: `step-components/Render.md`

Ten dokument opisuje:
- gdzie te kroki są renderowane,
- jak dane przechodzą między nimi,
- jak i kiedy czyścimy stan,
- gdzie wykonywana jest synchronizacja wyboru sampli do backendu.
