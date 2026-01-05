# Krok 3 — Render + Export (Render)

Ten dokument opisuje logikę kroku 3 po stronie frontendu: konfigurację miksu, dobór sampli (manualnie lub automatycznie), wywołanie renderu audio na backendzie oraz eksport/pobieranie wyników.

Zakres: logika w komponentach:
- `RenderStep.tsx` — orkiestracja kroku 3, integracja z backendem render i export, stan kroku.
- `SampleSelector.tsx` — wybór sampla per instrument (endpointy z modułu param-generation).
- `SimpleAudioPlayer.tsx` i `VisualAudioPlayer.tsx` — odsłuch mixu i stemów.

---

## Cel kroku 3

Krok 3 ma zamienić wynik kroku 2 (MIDI) na audio:
1) użytkownik nadaje nazwę projektu,
2) konfiguruje ścieżki (włącz/wyłącz, głośność, panorama),
3) dobiera sample dla instrumentów (manualnie) albo prosi backend o rekomendację,
4) uruchamia render mixu i stemów,
5) odsłuchuje wynik i pobiera pliki.

Wyjście z kroku 3:
- `RenderResult` (mix + stems + sample_rate + opcjonalnie duration),
- `run_id` renderu (do odtwarzania i eksportów).

---

## Konfiguracja API

W `RenderStep.tsx` endpointy są budowane przez:

```ts
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
const MODULE_PREFIX = "/air/render";
```

Dodatkowy ważny endpoint statyczny:
- backend serwuje wygenerowane pliki audio pod `GET /api/audio/...`.

Frontend buduje bazę do URL-i audio:

```ts
const backendAudioBase = `${API_BASE}/api/audio/`;
```

---

## Model danych

### `RenderResult`

```ts
export type RenderResult = {
  project_name: string;
  run_id: string;
  mix_wav_rel: string;
  stems: { instrument: string; audio_rel: string }[];
  sample_rate: number;
  duration_seconds?: number | null;
};
```

- `mix_wav_rel` i `audio_rel` są ścieżkami zwróconymi przez backend (zwykle zawierają fragment `output/...`).
- `stems` to lista osobnych ścieżek audio per instrument.

### `selectedSamples`

Krok 3 dostaje z rodzica mapę:
- `selectedSamples: Record<string, string | undefined>`

Mapa jest wykorzystywana w `SampleSelector` oraz wysyłana do backendu w requestach renderu/rekomendacji.

Ważne: `RenderStep` nie zapisuje tej mapy bezpośrednio w backendzie — robi to opcjonalny callback `onSelectedSamplesChange` (patrz niżej).

---

## Wejścia komponentu `RenderStep`

`RenderStep` wymaga danych z kroków 1 i 2:
- `meta: ParamPlanMeta | null`
- `midi: MidiPlanResult | null`

Jeżeli ich brakuje, UI pokazuje komunikat i blokuje render.

Dodatkowe propsy:
- `initialRunId?: string` — pozwala odtworzyć ostatni render z backendu (po odświeżeniu strony).
- `onRunIdChange?: (runId) => void` — aktualizacja run_id renderu w rodzicu.
- `onSelectedSamplesChange?: (next) => void` — opcjonalna synchronizacja zmian wyboru sampli do rodzica.

---

## Inicjalizacja stanu ścieżek (tracks)

`RenderStep` buduje domyślne tracki na bazie `meta.instruments`:

```tsx
const [tracks, setTracks] = useState(() => {
  const instruments = meta?.instruments || [];
  return instruments.map((name, idx) => ({
    instrument: name,
    enabled: true,
    volume_db: name.toLowerCase() === "piano" ? -8 : (idx === 0 ? 0 : -3),
    pan: 0,
  }));
});
```

Znaczenie pól tracka:
- `enabled` — czy instrument bierze udział w renderze,
- `volume_db` — głośność w dB (przekazywana do backendu),
- `pan` — panorama w zakresie [-1, 1] (L…Center…R).

Zmiany są robione przez helper:

```ts
const handleTrackChange = (index, patch) => {
  setTracks(prev => prev.map((t, i) => (i === index ? { ...t, ...patch } : t)));
};
```

---

## Dobór sampli

### 1) Manualny wybór sampla
Dla każdego tracka renderowany jest `SampleSelector`:

```tsx
<SampleSelector
  apiBase={API_BASE}
  apiPrefix={API_PREFIX}
  modulePrefix={"/air/param-generation"}
  instrument={t.instrument}
  selectedId={selectedSamples[t.instrument] || null}
  onChange={handleSampleChange}
/>
```

`SampleSelector` pobiera listę sampli z backendu (proxy do inventory):
- `GET /api/air/param-generation/samples/{instrument}?limit=200`

### 2) Zmiana mapy `selectedSamples`
Zmiana sampla w UI wywołuje `handleSampleChange`, który:
- buduje nową mapę instrument → sample_id,
- emituje ją do rodzica przez `onSelectedSamplesChange`.

```ts
const handleSampleChange = (instrument, sampleId) => {
  const next = { ...selectedSamples };
  if (!sampleId) delete next[instrument];
  else next[instrument] = sampleId;
  onSelectedSamplesChange?.(next);
};
```

W praktyce (w aplikacji) rodzic może persistować to do backendu (best-effort) w kroku 1 przez endpoint:
- `PATCH /api/air/param-generation/plan/{param_run_id}/selected-samples`

To umożliwia późniejsze odtworzenie projektu.

### 3) Automatyczna rekomendacja sampli
UI ma przycisk „Dobierz rekomendowane sample”, który wywołuje `handleRecommendSamples()`.

Endpoint:
- `POST /api/air/render/recommend-samples`

Body zawiera kontekst potrzebny do doboru:
- `run_id` (z kroku MIDI),
- `midi`,
- `midi_per_instrument` (jeśli dostępne),
- `tracks`,
- `selected_samples` (stan aktualny),
- `fadeout_seconds`,
- `project_name` (fallback do stylu).

```ts
const body = {
  project_name: projectName.trim() || meta.style || "air_demo",
  run_id: midi.run_id,
  midi: midi.midi,
  midi_per_instrument: midi.midi_per_instrument ?? null,
  tracks,
  selected_samples: selectedSamples,
  fadeout_seconds: fadeoutMs / 1000,
};

await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/recommend-samples`, { method: "POST", ... });
```

Odpowiedź backendu (konwencja):
- `recommended_samples` — mapowanie `instrument -> { instrument, sample_id }`.

Frontend scala rekomendacje z istniejącym wyborem i emituje wynik do rodzica:

```ts
const merged = { ...selectedSamples };
for (const [inst, rec] of Object.entries(recommended)) {
  if (rec?.sample_id) merged[inst] = rec.sample_id;
}
onSelectedSamplesChange?.(merged);
```

---

## Render audio (POST /render-audio)

Warunki uruchomienia renderu:
- istnieje `meta`,
- istnieje `midi`,
- ustawiona jest niepusta `projectName`,
- nie trwa `loading`.

Endpoint:
- `POST /api/air/render/render-audio`

Body:

```ts
const body = {
  project_name: projectName.trim(),
  run_id: midi.run_id,
  user_id: session?.user?.id ? Number(session.user.id) : null,
  midi: midi.midi,
  midi_per_instrument: midi.midi_per_instrument ?? null,
  tracks,
  selected_samples: selectedSamples,
  fadeout_seconds: Math.max(0, Math.min(100, fadeoutMs)) / 1000,
};
```

Uwaga o `user_id`:
- komponent korzysta z `next-auth` (`useSession()`),
- jeżeli `session.user.id` istnieje, jest przekazywany do backendu (numer).

Po sukcesie:
- wynik jest zapisany w `result`,
- dopisany do `history`,
- `onRunIdChange(rr.run_id)` aktualizuje run_id w rodzicu.

---

## Odtworzenie stanu renderu po `initialRunId`

Jeżeli `initialRunId` jest ustawione, a `result` jeszcze nie istnieje, krok 3 próbuje pobrać stan z backendu.

Endpoint:
- `GET /api/air/render/run/{run_id}`

Po sukcesie:
- ustawia `result`,
- dodaje do `history` (bez duplikatów),
- emituje `onRunIdChange(initialRunId)`.

---

## Odsłuch wyników

### Mix
W historii renderów dla każdej wersji renderowany jest `VisualAudioPlayer`:

```tsx
<VisualAudioPlayer
  src={resolveRenderUrl(h.mix_wav_rel)}
  title={h.project_name || "Mix"}
  ...
/>
```

`VisualAudioPlayer`:
- steruje `<audio>` (play/pause/seek/volume),
- tworzy WebAudio `AudioContext + AnalyserNode` przy pierwszym odtworzeniu,
- rysuje wizualizację widma na `<canvas>` tylko podczas odtwarzania.

### Stems
Stemy są dostępne po rozwinięciu `<details>` i używają `SimpleAudioPlayer`:

```tsx
<SimpleAudioPlayer
  src={resolveRenderUrl(stem.audio_rel)}
  height={32}
  variant="compact"
/>
```

---

## Budowanie URL do plików audio

Backend zwraca ścieżki typu `...output\{run_id}\file.wav` lub podobne.

Frontend mapuje `rel` na URL pod `/api/audio/`:

```ts
const marker = "output\\";
const idx = rel.indexOf(marker);
const tail = idx >= 0 ? rel.slice(idx + marker.length) : rel;
return `${backendAudioBase}${tail}`;
```

Uwaga praktyczna:
- `resolveRenderUrl()` używa markera `output\\` (backslash). Jest to dostosowane do backendu na Windows.
- Dla MIDI istnieje osobny helper `resolveMidiUrl()`, który dodatkowo obsługuje `output/` i normalizuje slashe do URL.

---

## Pobieranie plików (export)

Krok 3 oferuje dwa tryby pobierania:

### 1) Pobranie samego mixu
Przycisk „Mix” pobiera tylko `mix_wav_rel`:

```ts
downloadFile(resolveRenderUrl(h.mix_wav_rel), `${project}_mix.wav`)
```

`downloadFile(url, filename)`:
- robi `fetch(url)`,
- tworzy `Blob` i `ObjectURL`,
- odpala pobieranie przez tymczasowy `<a download>`.

### 2) Pobranie „Wszystko”
Funkcja `downloadAll(h)` próbuje:

#### 2.1) ZIP (preferowane)
Endpoint:
- `GET /api/air/export/zip/{run_id}`

Jeżeli status OK:
- pobiera jeden plik zip i zapisuje jako `project__export.zip`.

#### 2.2) Manifest (fallback)
Jeżeli zip nie jest dostępny:
- pobiera manifest listy plików.

Endpoint:
- `GET /api/air/export/list/{run_id}`

Manifest (konwencja):

```ts
type ExportManifest = {
  render_run_id: string;
  midi_run_id?: string | null;
  param_run_id?: string | null;
  files: { step: string; rel_path: string; url: string; bytes?: number | null }[];
  missing: string[];
};
```

Frontend iteruje `files` i pobiera każdy `url` przez `downloadFile()`.

Nazewnictwo plików:
- spłaszczenie ścieżki `rel_path` i dodanie prefixu z `step`.

---

## Historia renderów

Każdy udany render dopisywany jest do `history`, a UI pokazuje listę wersji (od najnowszej):
- odtwarzacz mixu,
- opcjonalne stemy,
- przyciski pobierania.

W efekcie użytkownik może generować kolejne wersje bez tracenia poprzednich.

---

## Najważniejsze endpointy backendu (krok 3)

Render:
- `POST /api/air/render/render-audio`
- `POST /api/air/render/recommend-samples`
- `GET /api/air/render/run/{run_id}`

Inventory / sample selection (proxy):
- `GET /api/air/param-generation/samples/{instrument}?limit=200`

Export:
- `GET /api/air/export/zip/{run_id}`
- `GET /api/air/export/list/{run_id}`

Pliki audio:
- `GET /api/audio/{run_id}/{file}`

---

## Następny krok dokumentacji

Jeżeli chcesz domknąć całość w tej samej konwencji, kolejnym logicznym dokumentem jest opis orkiestratora kroków (strona AIR):
- `src/app/air/page.tsx` — trzymanie stanu, unieważnianie kroków, persist sampli do backendu.
