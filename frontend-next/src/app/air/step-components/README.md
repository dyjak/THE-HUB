# step-components — dokumentacja modułów UI (AIR)

Ten folder zawiera komponenty frontendu odpowiedzialne za **kroki działania aplikacji AIR od strony wizualnej**:

- **Krok 1**: wygenerowanie planu parametrów (AI) + ręczna korekta + wybór instrumentów i sampli.
- **Krok 2**: wygenerowanie planu MIDI (AI) + wizualizacja pianoroll.
- **Krok 3**: render audio + eksport (mix, stems, paczka plików).

Dokument opisuje:
- co robi każdy moduł,
- jakie ma wejścia/wyjścia (props / callbacki),
- jaki stan utrzymuje,
- jakie side‑effecty wykonuje (`useEffect`) i czemu,
- jak wygląda przepływ danych między krokami.

Osobna, bardziej szczegółowa dokumentacja pianoroll (geometria renderu, mapowanie perkusji, zakresy nut/stepów) jest w pliku `MidiPianoroll.README.md`.

> Konwencja: w opisach używam nazw plików i symboli dokładnie jak w kodzie.

---

## 1) Architektura przepływu danych (high level)

### 1.1. Dane przepływające między krokami

W uproszczeniu, UI buduje się na 3 „paczkach” danych:

1) **Parametry (ParamPlan / ParamPlanMeta)** — wynik kroku 1 (po normalizacji i ewentualnych poprawkach użytkownika).

2) **Plan MIDI (MidiPlanResult)** — wynik kroku 2.

3) **Wynik renderu (RenderResult)** — wynik kroku 3.

Dodatkowo w kroku 1 i 3 pojawia się mapa:

- `selectedSamples: Record<string, string | undefined>`
  - klucz: nazwa instrumentu (np. `"Piano"`),
  - wartość: `sampleId` wskazujący konkretny sample z inventory.

### 1.2. UI jako „źródło prawdy” + best-effort sync

W kroku 1 widoczny jest ważny wzorzec:

- UI trzyma stan planu i wyboru sampli lokalnie w React.
- Jeśli mamy `runId`, to część stanu jest zapisywana do backendu przez endpointy `PATCH`.
- Synchronizacja jest **best-effort** (błędy patch są ignorowane), ponieważ UI ma działać płynnie i nie blokować użytkownika.

Fragment pokazujący tę zasadę:

```ts
// ParamPlanStep: zapis sampli jest best-effort
await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(runId)}/selected-samples`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ selected_samples: cleaned }),
});
// błąd synchronizacji nie powinien blokować UX
```

---

## 2) Krok 1 — generowanie parametrów + ręczna edycja

### 2.1. ParamPlanStep.tsx

**Rola**

Komponent implementuje cały krok 1:

- UI do wpisania promptu.
- Wybór `provider` i `model`.
- Wywołanie backendu `POST /air/param-generation/plan`.
- Przetworzenie odpowiedzi (raw/parsed/normalized).
- Wystawienie panelu edycji (`ParamPanel`) + synchronizacja stanu do rodzica.
- Odtworzenie kroku z `initialRunId`.
- „ProblemDialog” do ostrzeżeń i retry.

**Najważniejsze propsy (wyjścia do rodzica)**

- `onMetaReady?: (meta: ParamPlanMeta | null) => void`
  - informuje kolejny krok, czy meta jest gotowe.
- `onNavigateNext?: () => void`
  - przejście do kroku 2.
- `onPlanChange?: (plan: ParamPlan | null, selectedSamples: Record<string, string | undefined>) => void`
  - przekazanie planu + sampli wyżej.
- `initialRunId?: string | null`
  - próba odtworzenia stanu z backendu.
- `onRunIdChange?: (runId: string | null) => void`

**Stan (useState)**

ParamPlanStep utrzymuje kilka grup stanu:

1) UI/łącze z backendem:
- `provider`, `model`, `providers`, `models`
- `loading`, `error`

2) Debug/inspekcja:
- `systemPrompt`, `userPrompt`, `raw`, `parsed`, `normalized`

3) Domenowy stan kroku:
- `runId`: identyfikator planu po stronie backendu
- `available` / `selectable`: instrumenty dostępne lokalnie
- `midi: ParamPlan | null`: plan parametrów (źródło prawdy dla UI)
- `selectedSamples`: mapa instrument → sampleId

4) UX:
- `warnings`, `problemOpen` + pola do dialogu
- scrollowanie do panelu (`panelRef` + `shouldScroll`)

**Odtworzenie stanu (initialRunId)**

Mechanizm pozwala wrócić do kroku 1 po odświeżeniu strony.

- Komponent robi `GET /air/param-generation/plan/{runId}`.
- Próbuje zbudować plan:
  - preferuje `normalizeParamPlan(payload.plan.meta || payload.plan)`
  - w przypadku błędu tworzy „minimalny” plan awaryjny.

Ważny fragment:

```ts
const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(initialRunId)}`);
const payload = await res.json().catch(() => null);

const rawMeta = (payload.plan.meta || payload.plan) as any;

// normalny wariant
const normalizedMidi = normalizeParamPlan(rawMeta);
cloned = cloneParamPlan(normalizedMidi);

// awaryjny wariant (gdy payload jest częściowo uszkodzony)
cloned = {
  style: rawMeta.style ?? "ambient",
  tempo: typeof rawMeta.tempo === "number" ? rawMeta.tempo : 80,
  instruments: Array.isArray(rawMeta.instruments) && rawMeta.instruments.length > 0 ? rawMeta.instruments : ["piano"],
  instrument_configs: Array.isArray(rawMeta.instrument_configs) ? rawMeta.instrument_configs : [],
  // ...
};
```

**Generowanie planu (`send`)**

- Buduje `parameters` jako zestaw startowy.
- Wysyła `POST /air/param-generation/plan` z `{ parameters, provider, model }`.
- Odbiera `run_id` i odpowiedzi `system/user/raw/parsed`.
- Normalizuje meta do `ParamPlan`, klonuje (`cloneParamPlan`) i ustawia jako `midi`.
- Czyści wybór sampli (`updateSelectedSamples({})`).
- Wykrywa ostrzeżenia (`warnings`) i pokazuje `ProblemDialog`.

**Synchronizacja do rodzica**

Jest osobny efekt, który przekazuje `midi` + `selectedSamples` do rodzica.

```ts
useEffect(() => {
  if (!onPlanChange) return;
  onPlanChange(midi, selectedSamples);
}, [midi, selectedSamples, onPlanChange]);
```

**Zapisy do backendu (PATCH)**

- `persistMeta(nextMeta)` zapisuje aktualne meta.
- `updateSelectedSamples(next)` zapisuje mapę sampli.

To jest intencjonalnie best-effort — błędy nie blokują UI.

---

### 2.2. ParamPanel.tsx

**Rola**

To panel edycji wygenerowanych parametrów oraz konfiguracji instrumentów.

- Umożliwia zmianę: styl, mood, key, skala, metrum, tempo, długość, gęstość aranżu itd.
- Pozwala włączać/wyłączać instrumenty.
- Dla instrumentów pokazuje konfigurację (rola/rejestr/dynamic range/articulation).
- Dla każdego instrumentu umożliwia wybór konkretnego sampla przez `SampleSelector`.

**Wejścia (props)**

Najważniejsze:

- `midi: ParamPlan` — plan, który edytujemy.
- `availableInstruments: string[]` — instrumenty, które backend może realnie zrenderować (ma sample).
- `selectableInstruments: string[]` — instrumenty pokazywane w UI.
- `onUpdate(patch)` — aktualizacja pól planu.
- `onToggleInstrument(instrument)` — dodanie/usunięcie instrumentu.
- `onUpdateInstrumentConfig(name, patch)` — aktualizacja konfiguracji instrumentu.
- `selectedSamples` + `onSelectSample` — mapowanie instrument → sampleId.

**Mechanizmy warte uwagi**

1) `withCurrent(...)` — dba o to, żeby wartość spoza presetów (z AI) nadal była widoczna w select.

```ts
const withCurrent = <T extends string>(options: readonly T[], current: string | undefined | null): string[] => {
  const base = Array.from(options) as string[];
  if (!current) return base;
  const lower = current.toLowerCase();
  if (!base.some(opt => opt.toLowerCase() === lower)) {
    base.push(current);
  }
  return base;
};
```

2) Blokowanie instrumentów bez lokalnych sampli

- `isInstrumentDisabled` sprawdza, czy instrument jest poza `availableInstruments`.
- Toggle pozwala kliknąć tylko jeśli instrument jest dostępny (albo lista `availableInstruments` jest pusta — tryb „inventory opcjonalne”).

3) Baner ostrzegawczy o „missing instruments”

- `missingInstruments` = instrumenty z planu, których nie ma w lokalnej bazie.

4) Lista instrumentów jest podzielona na:

- `DRUMS` — dedykowana grupa
- `FX` — lista kompatybilności
- reszta jako `genericInstruments`

**Relacja z ParamPlanStep**

ParamPanel jest „głupim” panelem: nie zna backendu. Wszystkie aktualizacje idą przez callbacki, a ParamPlanStep decyduje:

- jak zaktualizować stan,
- czy robić `PATCH`.

---

### 2.3. SampleSelector.tsx

**Rola**

Komponent do wyboru sampla dla jednego instrumentu.

- Pobiera listę sampli dla `instrument`.
- Renderuje `<select>`.
- Pokazuje preview audio (SimpleAudioPlayer).
- Jeśli nic nie wybrano, ustawia domyślny wybór startowy.

**Wejścia (props)**

- `apiBase`, `apiPrefix`, `modulePrefix` — budowa URL.
- `instrument` — aktualny instrument.
- `selectedId` — wybrany sample.
- `onChange(instrument, sampleId)` — zapis wyboru na zewnątrz.

**Pobieranie listy sampli**

- Efekt zależy od `instrument`.
- Używa `mounted` flagi, aby nie robić `setState` po odmontowaniu.

```ts
useEffect(() => {
  let mounted = true;
  const load = async () => {
    const res = await fetch(`${apiBase}${apiPrefix}${modulePrefix}/samples/${encodeURIComponent(instrument)}?limit=200`);
    const data = await res.json();
    if (!mounted) return;
    setItems(Array.isArray(data.items) ? data.items : []);
  };
  load();
  return () => { mounted = false; };
}, [apiBase, apiPrefix, modulePrefix, instrument]);
```

**Wybór startowy (oddzielny useEffect)**

To ważne rozdzielenie:
- pobranie listy ≠ ustawienie default.

Mechanizm:
- jeśli backend przekazał `_default`, użyj go,
- w przeciwnym razie losuj z listy (żeby nie zawsze brać pierwszy).

```ts
if (!items || items.length === 0) return;
if (selectedId) return;
const preferred = dataDefault && items.find(x => x.id === dataDefault.id);
const fallback = preferred || items[Math.floor(Math.random() * items.length)];
if (fallback?.id) onChange(instrument, fallback.id);
```

**Sytuacja „no local samples”**

- gdy lista jest pusta, select pokazuje `(no local samples)` i komponent dostaje czerwone obramowanie.

---

## 3) Krok 2 — generowanie planu MIDI + pianoroll

### 3.1. MidiPlanStep.tsx

**Rola**

Komponent realizuje krok 2:

- Wybór provider/model.
- `POST /air/midi-generation/compose` z `meta`.
- Odczyt wcześniejszego runa (`initialRunId`) przez `GET /air/midi-generation/run/{runId}`.
- Wyświetlenie wyniku:
  - run_id, provider/model,
  - `MidiPianoroll` dla `result.midi`,
  - panel debug (`systemPrompt/userPrompt/normalized/raw`).
- Wykrywanie ostrzeżeń i pokaz `ProblemDialog`.

**Wejścia (props)**

- `meta: ParamPlanMeta | null` — wejście z kroku 1.
- `paramRunId?: string | null` — opcjonalne spięcie eksportów po stronie backendu.
- `onReady?: (result: MidiPlanResult) => void` — przekazanie wyniku do rodzica.
- `initialRunId?: string | null` + `onRunIdChange` — odtwarzanie kroku i synchronizacja.
- `onNavigateNext` — przejście do renderu.

**Ważny mechanizm: inventory → ostrzeżenia**

MidiPlanStep pobiera listę instrumentów dostępnych w inventory (`/available-instruments`) i po udanym compose:

- wyciąga instrumenty żądane przez plan (`data.midi.meta.instruments` albo `meta.instruments`),
- raportuje brakujące jako ostrzeżenie.

To ma sens, bo krok 2 potrafi zaproponować instrumenty, których realnie nie da się zrenderować.

**Wykrywanie problemów niekrytycznych**

Po sukcesie:
- zbierane są `data.errors`,
- sprawdzane jest czy są artefakty `.mid` oraz `svg`.

```ts
if (!midRel) warn.push("Nie wygenerowano pliku .mid (brak mido albo błąd eksportu).");
if (!svgRel) warn.push("Nie wygenerowano pianoroll SVG (pusty pattern lub błąd renderowania).");
```

Jeśli ostrzeżeń jest dużo → `ProblemDialog` z możliwością retry.

---

### 3.2. MidiPianoroll.tsx

**Rola**

Lekka wizualizacja pianoroll po stronie frontu:

- bez canvasów (poza audio playerami),
- zbudowana w HTML/CSS,
- obsługuje zoom poziomy/pionowy,
- rozbija MIDI na "lanes" per instrument i rysuje prostokąty nut.

**Wejścia (props)**

- `midi: MidiData | null | undefined`
- `stepsPerBar?: number` (domyślnie 8)

**Model danych**

- `MidiData` może mieć:
  - `layers?: Record<string, MidiLayer[]>` — już pogrupowane per instrument,
  - `pattern?: MidiLayer[]` — typowy wariant perkusyjny,
  - `meta?: { tempo?: number; bars?: number; ... }`.

`MidiEvent` zawiera m.in. `bar`, `step`, `note` oraz opcjonalnie `vel`, `len`.

**Najważniejsza logika: budowanie lanes (useMemo)**

Pianoroll w `useMemo` buduje:

- `lanes: { instrument: string; events: MidiEvent[] }[]`
- `mergedLane` (opcjonalnie) — wspólna oś dla wszystkich eventów
- zakres nut `minNote/maxNote`
- zakres czasu `minAbsStep/totalSteps`
- `colorMap` — mapowanie instrument → kolor
- `laneNoteRanges` — osobne zakresy nut per lane

**Warstwy z `midi.layers`**

To najprostszy przypadek: każda właściwość w `layers` staje się lane.

**Perkusja z `midi.pattern`**

To ważny mechanizm:

1) Komponent próbuje znaleźć instrumenty perkusyjne:
- z `meta.instrument_configs` (rola = percussion),
- lub z `meta.instruments`,
- a jeśli nadal nic: fallback do standardowych nazw.

2) Mapuje nazwy instrumentów do nut GM (kick/snare/hat...).

3) Rozbija zdarzenia z `pattern` na lane per instrument na podstawie `note`.

Fragment mapowania (uproszczony):

```ts
const direct = {
  kick: [36],
  snare: [38],
  hat: [42, 46],
  crash: [49],
  ride: [51],
};
```

**Stabilność listy lane**

- takty w perkusji są sortowane (`byInst[inst].sort((a,b)=>...)`), żeby UI nie "skakało" między renderami.

**Lane nawet bez eventów**

Jeśli `midi.meta.instruments` podaje instrumenty, komponent tworzy lane nawet gdy eventów brak (dla czytelności wyniku).

**Render i geometria**

- oś czasu: `absStep = bar * stepsPerBar + step`
- pozycja X: `(absStep - minAbsStep) * cellWidth`
- pozycja Y: zależna od wysokości nuty (albo globalnie, albo w obrębie lane)
- szerokość nuty zależy od `len`.

**Zoom**

- `zoomX` i `zoomY` sterują `cellWidth` i `cellHeight`.

**Stany brzegowe**

- `!midi` → "Brak danych MIDI".
- brak lanes/eventów → komunikat o pustym patternie.

---

## 4) Krok 3 — render audio + export

### 4.1. RenderStep.tsx

**Rola**

Krok 3 spina MIDI z backendowym renderem audio:

- nadanie `projectName`,
- konfiguracja ścieżek (enabled / volume / pan),
- dobór sampli (manualnie) albo rekomendacja backendu,
- render audio: mix + stems,
- odsłuch (VisualAudioPlayer / SimpleAudioPlayer),
- pobieranie plików (mix lub "Wszystko" — zip/manifest).

**Wejścia (props)**

- `meta: ParamPlanMeta | null`
- `midi: MidiPlanResult | null`
- `selectedSamples: Record<string, string | undefined>`
- `initialRunId?: string | null` — odtworzenie renderu
- `onRunIdChange?: (runId) => void`
- `onSelectedSamplesChange?: (next) => void` — zapis wyboru sampli z kroku 3 do rodzica

**Stan**

- `projectName`, `loading`, `error`
- `result` + `history`
- `tracks`: lista ścieżek tworzona początkowo z `meta.instruments`
- `fadeoutMs`
- `recommending` oraz `downloadingAllRunId`

**Rozwiązywanie URL do plików audio**

Backend serwuje output pod `/api/audio/`.
RenderStep dostaje `rel_path` (czasem z `output\`), więc musi:

- uciąć prefiks `output\` / `output/`,
- znormalizować `\\` na `/`,
- skleić w URL.

```ts
const markerBack = "output\\";
const markerFwd = "output/";
// ...
const normalizedTail = tail.replace(/\\/g, '/');
const finalUrl = `${backendAudioBase}${normalizedTail}`;
```

**Render (`handleRender`)**

Wysyła `POST /air/render/render-audio` z payloadem:

- `project_name`
- `run_id` (z kroku MIDI)
- `user_id` (z session)
- `midi` i opcjonalnie `midi_per_instrument`
- `tracks`
- `selected_samples`
- `fadeout_seconds`

Ważne: `fadeoutMs` jest przeliczany na sekundy.

```ts
fadeout_seconds: Math.max(0, Math.min(100, fadeoutMs)) / 1000,
```

**Rekomendacja sampli (`handleRecommendSamples`)**

Wywołuje backend `POST /air/render/recommend-samples`, odbiera mapę rekomendacji i scala ją z aktualnym wyborem.

```ts
const recommended = (data?.recommended_samples || {}) as Record<string, { instrument: string; sample_id: string }>;
const merged: Record<string, string | undefined> = { ...selectedSamples };
for (const [inst, rec] of Object.entries(recommended)) {
  if (rec?.sample_id) merged[inst] = rec.sample_id;
}
onSelectedSamplesChange?.(merged);
```

**Pobieranie eksportu (`downloadAll`)**

Strategia:

1) Spróbuj pobrać zip: `GET /air/export/zip/{run_id}`.
2) Jeśli zip nie działa, pobierz manifest: `GET /air/export/list/{run_id}` i pobierz pliki pojedynczo.

To jest bardzo praktyczne podejście: zip jest szybki, ale manifest daje fallback.

---

## 5) Wspólne komponenty UX

### 5.1. ProblemDialog.tsx

**Rola**

Wspólny dialog ostrzeżeń/błędów używany w krokach 1 i 2.

- Pokazuje `title`, `description`, listę `details`.
- Może pokazać aktualny `provider/model`.
- Opcjonalnie pozwala zmienić provider/model (jeśli rodzic poda listy + callbacki).
- Ma dwa wyjścia:
  - `onContinue()` — zamknięcie dialogu (kontynuacja z obecnym stanem),
  - `onRetry()` — ponowienie generowania w komponencie rodzica.

**Defensywne filtrowanie danych**

- `details` są czyszczone do listy stringów.
- `availableProviders` i `availableModels` są deduplikowane.

```ts
const items = Array.isArray(details) ? details.filter((x) => typeof x === "string" && x.trim()) : [];
const models = Array.isArray(availableModels)
  ? Array.from(new Set(availableModels.filter((m) => typeof m === "string" && m.trim())))
  : [];
```

To stabilizuje UI nawet gdy backend zwróci nietypowy payload.

---

### 5.2. SimpleAudioPlayer.tsx

**Rola**

Prosty odtwarzacz audio do preview sampla i prostych odsłuchów.

- play/pause
- pasek postępu z seek
- czasy `current/duration`
- regulacja głośności

**Kluczowe mechanizmy**

- `ready` ustawia się dopiero po `loadedmetadata`.
- `timeupdate` synchronizuje `current`.
- `seek` przelicza klik w pikselach na ułamek `duration`.

```ts
const rect = bar.getBoundingClientRect();
const ratio = Math.min(Math.max(x / rect.width, 0), 1);
el.currentTime = ratio * duration;
```

---

### 5.3. VisualAudioPlayer.tsx

**Rola**

Odtwarzacz audio z wizualizacją widma na canvasie.

- Tworzy `AudioContext` + `AnalyserNode`.
- Podpina `MediaElementAudioSourceNode` dla `<audio>`.
- Rysuje słupki częstotliwości tylko gdy audio gra.

**Najważniejsze ograniczenie przeglądarek**

`AudioContext` zwykle wymaga „gestu użytkownika”. W kodzie jest to uwzględnione:

- context tworzy się przy pierwszym odtworzeniu (`toggle`).
- jeśli state jest `suspended`, robi `resume()`.

```ts
if (!audioContextRef.current) setupAudioContext();
if (audioContextRef.current?.state === "suspended") audioContextRef.current.resume();
```

**Wydajność**

- `requestAnimationFrame` działa tylko gdy `playing === true`.
- przy pauzie animacja się zatrzymuje.

**Stabilna „losowość” wizualizera**

Szerokość słupków ma losowe mnożniki (`barPropsRef`) stworzone raz na długość bufora.

To daje wizualnie „żywy” efekt bez losowania w każdej klatce.

---

## 6) Mapa zależności w folderze

- `ParamPlanStep.tsx`
  - używa: `ParamPanel`, `ProblemDialog`
- `ParamPanel.tsx`
  - używa: `SampleSelector`
- `MidiPlanStep.tsx`
  - używa: `MidiPianoroll`, `ProblemDialog`
- `RenderStep.tsx`
  - używa: `SampleSelector`, `VisualAudioPlayer`, `SimpleAudioPlayer`
- `SampleSelector.tsx`
  - używa: `SimpleAudioPlayer`

---

## 7) Szybkie FAQ (pułapki i powody decyzji)

1) **Czemu w kilku miejscach jest `mounted` flag?**
- żeby nie robić `setState` po odmontowaniu, gdy fetch wróci później.

2) **Czemu `selectedSamples` jest trzymane jako mapa, a nie w obiektach tracków?**
- bo ta mapa jest współdzielona między krokami i łatwo ją patchować oraz przesyłać do backendu.

3) **Czemu w krokach AI jest `ProblemDialog` zamiast twardego erroru?**
- bo wiele problemów jest niekrytycznych (np. brak svg, brak mid) i użytkownik może kontynuować.

4) **Czemu `MidiPianoroll` nie używa canvas?**
- komponent jest celowo „lekki” i czytelny, renderuje nuty jako elementy DOM.

---

## 8) Jak czytać logikę kroków podczas pisania pełnej dokumentacji projektu

Rekomendowana kolejność analizy:

1) `ParamPlanStep.tsx` — wejście do całego flow, generowanie meta i jego stabilizacja.
2) `ParamPanel.tsx` + `SampleSelector.tsx` — jak użytkownik modyfikuje plan i dobiera sample.
3) `MidiPlanStep.tsx` — generowanie planu MIDI i diagnostyka jakości odpowiedzi.
4) `MidiPianoroll.tsx` — jak UI interpretuje JSON MIDI i jak rozbija perkusję.
5) `RenderStep.tsx` — payload renderu, rekomendacje sampli, eksport.
6) `SimpleAudioPlayer.tsx` / `VisualAudioPlayer.tsx` — odsłuch i wizualizacje.
7) `ProblemDialog.tsx` — wspólna warstwa UX dla problemów.
