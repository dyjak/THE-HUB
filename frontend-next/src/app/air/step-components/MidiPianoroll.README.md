# MidiPianoroll — szczegółowa dokumentacja

Ten dokument opisuje komponent `MidiPianoroll` (plik: `MidiPianoroll.tsx`) — lekki pianoroll na froncie, renderowany w HTML/CSS, bez canvasów.

Cel: **czytelny podgląd JSON-owego planu MIDI** (z backendu) w UI.

---

## 1) Wejście i format danych

### 1.1. Props

```ts
type Props = {
  midi: MidiData | null | undefined;
  stepsPerBar?: number; // domyślnie 8
};
```

- `midi` — obiekt z danymi MIDI po stronie UI (zazwyczaj `result.midi` z kroku 2).
- `stepsPerBar` — liczba kroków na takt (aplikacja domyślnie przyjmuje **8**, zgodnie z założeniami promptu backendu).

### 1.2. Typy danych (model domenowy pianoroll)

```ts
export type MidiEvent = {
  bar: number;
  step: number;
  note: number;
  vel?: number;
  len?: number;
  instrument?: string;
};

export type MidiLayer = {
  bar: number;
  events: MidiEvent[];
  mergedLane?: { instrument: string; events: MidiEvent[] } | null;
};

export type MidiData = {
  pattern?: MidiLayer[];
  layers?: Record<string, MidiLayer[]>;
  meta?: {
    tempo?: number;
    bars?: number;
  } & Record<string, any>;
};
```

- `bar` — indeks taktu.
- `step` — indeks kroku w obrębie taktu (0..stepsPerBar-1).
- `note` — numer nuty MIDI.
- `vel` — velocity 0..127 (domyślnie 80).
- `len` — długość nuty w krokach (domyślnie 1).

**Ważne:** komponent jest defensywny — jeśli `vel/len/step/bar` są niepoprawne, przyjmuje fallbacki.

---

## 2) Celowe założenia i ograniczenia

1) Komponent nie implementuje edycji nut. To jest **tylko wizualizacja**.

2) Brak canvasa = prostszy kod i CSS, ale dużo elementów DOM przy dużej liczbie nut.

3) Kolory instrumentów są losowane w trakcie budowania `colorMap`.
- To oznacza, że przy pewnych zmianach danych/ponownym obliczeniu `useMemo` kolory mogą się zmienić.

---

## 3) Budowanie danych do renderu (useMemo)

Cała logika przygotowania danych do renderu jest w `useMemo`:

- zbiera eventy,
- buduje lanes (per instrument),
- wylicza zakres czasu i zakres nut,
- tworzy mapę kolorów,
- przygotowuje dane do renderu merged lane.

Pseudostruktura zwracana przez `useMemo`:

```ts
{
  lanes: { instrument: string; events: MidiEvent[] }[];
  mergedLane: { instrument: "Merged"; events: MidiEvent[] } | null;
  minNote: number;
  maxNote: number;
  totalSteps: number;
  minAbsStep: number;
  colorMap: Record<string, string>;
  laneNoteRanges: Record<string, { min: number; max: number }>;
}
```

### 3.1. Normalizacja nazw instrumentów (`canon`)

W wielu miejscach występuje normalizacja nazwy:

```ts
const canon = (name: unknown) => String(name || "")
  .trim()
  .toLowerCase()
  .replace(/\s+/g, " ");
```

Cel: ujednolicić porównania (np. `"Hi Hat"` vs `"hihat"`).

### 3.2. `pushLayer` — główna funkcja zbierająca eventy

`pushLayer(instrument, layers?)`:

- iteruje po `MidiLayer[]` (takty),
- wyciąga eventy,
- filtruje eventy bez `note`,
- przypisuje domyślne wartości:
  - `step` → 0,
  - `vel` → 80,
  - `len` → 1,
- dokleja `instrument` do `MidiEvent` (własne pole użyte później m.in. w merged lane),
- dopisuje event do `lanes` oraz `mergedEvents`,
- buduje `laneNoteRanges` (min/max note per instrument),
- zapewnia kolor w `colorMap`.

Kluczowy fragment (w skrócie):

```ts
const full: MidiEvent = { bar, step, note: ev.note, vel, len, instrument: instrument || undefined };

let lane = lanes.find(l => l.instrument === instrument);
if (!lane) {
  lane = { instrument, events: [] };
  lanes.push(lane);
  if (!colorMap[instrument]) {
    const hue = Math.floor(Math.random() * 360);
    const sat = 60 + Math.floor(Math.random() * 20);
    const light = 50 + Math.floor(Math.random() * 10);
    colorMap[instrument] = `hsl(${hue} ${sat}% ${light}%)`;
  }
}

lane.events.push(full);
mergedEvents.push(full);
```

**Konsekwencje:**
- Złożoność `lanes.find(...)` przy każdym evencie jest liniowa w liczbie lanes (zwykle mała).
- Kolor jest losowy, ale „przyjemny” (HSL w ograniczonym zakresie).

### 3.3. Obsługa `midi.layers` (warstwy per instrument)

Jeśli `midi.layers` istnieje:

- iterujemy po kluczach obiektu,
- każdy klucz traktujemy jako instrument,
- warstwy lądują w `pushLayer(key, midi.layers[key])`.

To jest tryb „najczystszy”, bo backend już pogrupował dane per instrument.

### 3.4. Obsługa `midi.pattern` (perkusja) i mapowanie GM

`pattern` jest traktowany specjalnie: komponent próbuje rozdzielić perkusję na lane per instrument.

#### 3.4.1. Jak wyznaczamy listę instrumentów perkusyjnych

1) Z `meta.instrument_configs`:
- jeśli config ma `role == "percussion"` i `name`, to dodajemy `name`.

2) Jeśli to puste, z `meta.instruments`:
- bierzemy nazwy, które wyglądają na perkusyjne (`notesForPercussionInstrument(name)` != null).

3) Fallback awaryjny:

```ts
["Kick", "Snare", "Hat", "Crash", "Ride", "Tom"].forEach(n => percSet.add(n));
```

#### 3.4.2. Mapowanie nazwy instrumentu → nuty GM

Funkcja `notesForPercussionInstrument(name)` ma mapę bezpośrednią i heurystyki `includes(...)`.

Przykłady:
- `Kick` → `[36]`
- `Snare` → `[38]`
- `Hat` / `Hi Hat` → `[42, 46]`
- `Crash` → `[49]`

Jeśli nazwa jest niejednoznaczna (np. `"tom"`), zwracana jest lista kilku nut.

#### 3.4.3. Rozbijanie eventów z `pattern` na instrumenty

- dla każdego eventu bierzemy `note` i szukamy pierwszego pasującego instrumentu,
- priorytet mają instrumenty bardziej specyficzne (z mniejszą liczbą nut w mapie).

```ts
const percMap = percNames
  .map(name => ({ name, notes: notesForPercussionInstrument(name) || [] }))
  .filter(x => x.notes.length > 0)
  .sort((a, b) => a.notes.length - b.notes.length);
```

Jeżeli nuta nie pasuje do żadnego instrumentu → idzie do fallback instrumentu `"Drums"`.

Po zbudowaniu per-instrument warstw, każda trafia do `pushLayer(inst, byInst[inst])`.

### 3.5. Lane bez eventów (instrumenty „żądane”)

Komponent próbuje zapewnić lane dla każdego instrumentu z `midi.meta.instruments`, nawet jeśli brak eventów.

Cel UX:
- użytkownik widzi, że instrument był planowany, ale model nie wygenerował nut.

---

## 4) Oś czasu i zakresy

### 4.1. Absolutny krok czasu (absStep)

Wszędzie w renderze używa się przeliczenia:

```ts
absStep = bar * stepsPerBar + step
```

### 4.2. minAbsStep i totalSteps

Komponent liczy:

- `minAbsStep`: najmniejszy start nuty,
- `maxAbsStep`: największy koniec nuty (`start + len`),
- `totalSteps = maxAbsStep - minAbsStep`.

To umożliwia przycięcie osi czasu do faktycznych danych.

### 4.3. Zakres nut

Są dwa tryby:

1) Globalny zakres dla merged lane:
- `minNote/maxNote` z wszystkich eventów.

2) Per-lane zakres nut:
- `laneNoteRanges[instrument] = {min, max}`.

To pozwala, aby lane z wąskim rejestrem nie miało gigantycznej, pustej przestrzeni.

---

## 5) Render UI (geometria, CSS, zoom)

### 5.1. Stany brzegowe

- `midi == null` → komunikat "Brak danych MIDI do wizualizacji".
- `lanes.length == 0` → komunikat "Pusty pattern MIDI".

### 5.2. Rozmiary komórki i zoom

Bazowe wartości:

```ts
const baseCellWidth = 36;
const baseCellHeight = 14;

const cellWidth = baseCellWidth * zoomX;
const cellHeight = baseCellHeight * zoomY;

const width = (totalSteps || 1) * cellWidth;
const height = noteRange * cellHeight;
```

Zoomy:
- `zoomX` i `zoomY` są sterowane suwakami `range` (0.5..3.0).

### 5.3. Siatka tła

Tło jest rysowane przez `backgroundImage` z `repeating-linear-gradient`.

- pionowe linie: subtelne co krok i mocniejsze co 8 kroków (36px vs 288px)
- poziome linie: delikatne pasy co wysokość komórki

Ważne: `backgroundSize` jest ustawiane zgodnie z `cellWidth` i `cellHeight`.

### 5.4. Render nut (prostokąty)

Dla każdego eventu:

- X:

```ts
const abs = ev.bar * stepsPerBar + ev.step;
const x = (abs - minAbsStep) * cellWidth;
```

- Y:
  - merged lane: `(maxNote - ev.note) * cellHeight`
  - lane: `(laneMax - ev.note) * cellHeight` (w obrębie lane)

- W:

```ts
const w = Math.max(cellWidth * (ev.len || 1) - 1, 3);
```

- H:

```ts
const h = cellHeight - 2;
```

- Przezroczystość zależna od velocity:

```ts
const opacity = Math.min(1, Math.max(0.4, (ev.vel || 80) / 127));
```

- Label nuty (np. `C#4`) jest pokazywany tylko gdy `zoomX > 0.8`.

### 5.5. Kolory

- Dla merged lane kolor może zależeć od `ev.instrument` (jeśli event ma instrument), w przeciwnym razie fallback.
- Dla lane kolor jest zawsze `colorMap[lane.instrument]`.

---

## 6) Stabilność i wydajność

### 6.1. `useMemo` i zależności

`useMemo` zależy od:

- `midi`
- `stepsPerBar`

To znaczy: każda zmiana referencji `midi` przelicza lanes i kolory.

### 6.2. Potencjalna niestabilność kolorów

Ponieważ kolory są losowane, a `useMemo` przelicza się po zmianie `midi`, w praktyce można zobaczyć:

- inne kolory po regeneracji,
- inne kolory po odtworzeniu runa,
- inne kolory gdy dane zostały minimalnie zmienione.

Jeśli chcemy deterministycznie: można zastąpić losowanie hashem od nazwy instrumentu.

### 6.3. Koszt DOM

Każda nuta = jeden `<div>` absolutnie pozycjonowany.

Jeśli pattern ma tysiące eventów, DOM może być ciężki.

---

## 7) Jak używać z kroku MIDI (praktycznie)

Najczęściej:

```tsx
<MidiPianoroll midi={result.midi as any} stepsPerBar={8} />
```

W praktyce `stepsPerBar` jest pomijane, bo domyślne = 8.

---

## 8) Typowe problemy i diagnostyka

1) "Pusty pattern MIDI" mimo że backend coś zwrócił
- Zwykle model zwrócił JSON niezgodny z oczekiwanym schematem (np. brak `note` w eventach).

2) Perkusja nie rozbita na Kick/Snare/Hat
- `meta` nie zawiera instrumentów/configów, a nuty nie pasują do mapy GM.
- Wtedy eventy lądują w lane `Drums`.

3) Lane jest widoczne, ale bez nut
- `midi.meta.instruments` wymusiło lane, ale model nie wygenerował eventów.

---

## 9) Checklist do przyszłych zmian

Jeśli będziemy rozbudowywać `MidiPianoroll`, najpierw trzeba ustalić:

- Czy `stepsPerBar` jest zawsze 8, czy zależy od metrum/kroku w backendzie.
- Czy chcemy deterministyczne kolory.
- Czy chcemy wirtualizację (dużo nut) lub canvas dla wydajności.
- Czy rozbijanie perkusji ma bazować tylko na GM, czy na mapie z backendu.
