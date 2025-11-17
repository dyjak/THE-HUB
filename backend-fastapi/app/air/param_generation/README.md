# AIR • Parameter Generation Module

Ten moduł odpowiada **wyłącznie** za planowanie wysokopoziomowych parametrów muzycznych na potrzeby dalszych etapów pipeline'u (generowanie MIDI, render audio itd.).

Nie generuje żadnych sekwencji MIDI, nut, patternów ani plików `.mid` – zwraca jedynie opis utworu w postaci ustrukturyzowanego JSON-a.

---

## 1. Rola modułu w pipeline0

1. Użytkownik wpisuje natural language prompt opisujący utwór
	 (np. _"epicki soundtrack 90 BPM z chórem i smyczkami"_).
2. Frontend (`ParamPlanStep`) wysyła ten prompt do modułu `param-generation`.
3. Moduł buduje **system prompt** i **user payload** dla wybranego LLM
	 (Gemini, Anthropic, OpenAI, OpenRouter) i odpala zapytanie.
4. Model zwraca JSON w postaci `{"meta": {...}}` zawierający:
	 - parametry globalne (styl, nastrój, tempo, tonacja, metrum, długość),
	 - dobraną listę instrumentów,
	 - konfigurację każdego instrumentu (rola, rejestr, artykulacja, dynamika).
5. Backend parsuje odpowiedź, zapisuje wynik na dysku i zwraca payload do frontu.
6. Frontend wizualizuje parametry w panelu edycyjnym (`MidiPanel`),
	 pozwala użytkownikowi je doprecyzować oraz dobrać **konkretne sample**
	 z lokalnego inventory.
7. Taki plan parametrów + wybór próbek staje się wejściem dla późniejszych
	 modułów odpowiedzialnych za generowanie MIDI i/lub audio.

---

## 2. Kontrakt HTTP i formaty danych

### 2.1. Endpoint główny: `POST /api/air/param-generation/plan`

Router modułu:

- prefiks: `/air/param-generation`
- główny endpoint planowania: `POST /plan`

Pełna ścieżka z reverse proxy (FastAPI w tym projekcie):

```text
POST /api/air/param-generation/plan
```

#### 2.1.1. Request body

Model wejściowy na backendzie to `ParameterPlanRequest`:

```jsonc
{
	"parameters": {
		"prompt": "epicki soundtrack 90 BPM z chórem i smyczkami",
		"style": "ambient",              // opcjonalnie nadpisywane przez LLM
		"mood": "calm",
		"tempo": 80,
		"key": "C",
		"scale": "major",
		"meter": "4/4",
		"bars": 16,
		"length_seconds": 180,
		"dynamic_profile": "moderate",
		"arrangement_density": "balanced",
		"harmonic_color": "diatonic",
		"instruments": ["piano", "pad", "strings"],
		"instrument_configs": [],
		"seed": null
	},
	"provider": "gemini",             // opcjonalne, domyślnie "gemini"
	"model": "gemini-2.5-flash"       // opcjonalne, może być puste
}
```

> Uwaga: `parameters` jest walidowane przez model `ParameterPlanIn` (Pydantic).
> Jeżeli frontend poda niepełne dane, zostaną zastosowane sensowne domyślne
> wartości (np. domyślne instrumenty: piano + pad + strings).

#### 2.1.2. Response body

Główny endpoint zwraca słownik z poniższymi kluczami (uproszczone):

```jsonc
{
	"run_id": "a1b2c3d4e5f6",           // ID sesji planowania (dla debug)
	"system": "...",                     // system prompt wysłany do LLM
	"user": "{\"task\":...}",          // JSON user payload przekazany do LLM
	"raw": "...",                        // surowa odpowiedź tekstowa z modelu
	"parsed": {                           // zparsowana odpowiedź z LLM
		"meta": {
			"style": "cinematic",
			"mood": "epic",
			"tempo": 90,
			"key": "D",
			"scale": "minor",
			"meter": "4/4",
			"bars": 32,
			"length_seconds": 210,
			"dynamic_profile": "intense",
			"arrangement_density": "dense",
			"harmonic_color": "modal",
			"instruments": ["piano", "strings", "choir", "drumkit"],
			"instrument_configs": [
				{
					"name": "piano",
					"role": "Lead",
					"register": "Mid",
					"articulation": "Sustain",
					"dynamic_range": "Moderate"
				},
				{
					"name": "strings",
					"role": "Accompaniment",
					"register": "High",
					"articulation": "Legato",
					"dynamic_range": "Intense"
				}
				// ...itd. dla każdego instrumentu...
			]
		}
	},
	"errors": ["parse: truncated to last brace due to ..."],
	"saved_raw_rel": "20251117_120000_a1b2c3d4e5f6/parameter_plan_raw.txt",
	"saved_json_rel": "20251117_120000_a1b2c3d4e5f6/parameter_plan.json"
}
```

Jeżeli parsowanie JSON-a się nie powiedzie, `parsed` może być `null`, a
`errors` będzie zawierało listę komunikatów. W takim przypadku front może
wykorzystać `raw` do debugowania.

---

## 3. Integracja z inventory / wybór sampli

Moduł `param_generation` nie zna bezpośrednio plików audio, ale posiada
**proxy** na moduł inventory, dzięki czemu UI może dobrać sample dla
wybranych instrumentów.

### 3.1. Dostępne instrumenty

Endpoint:

```text
GET /api/air/param-generation/available-instruments
```

Odpowiedź:

```jsonc
{
	"available": ["Piano", "Pad", "Strings", "Bass", "Drumkit", "Choir", ...],
	"count": 7
}
```

Frontend wykorzystuje tę listę m.in. do:

- filtrowania instrumentów w generatorze parametrów,
- aktualizacji listy przełączników w `MidiPanel`.

### 3.2. Lista sampli dla instrumentu

Endpoint:

```text
GET /api/air/param-generation/samples/{instrument}?offset=0&limit=100
```

Przykład odpowiedzi:

```jsonc
{
	"instrument": "piano",
	"resolved": ["Piano"],               // nazwa/nazwy z inventory
	"count": 42,                          // łączna liczba sampli
	"offset": 0,
	"limit": 100,
	"items": [
		{
			"id": "piano_001",
			"file": "D:/.../local_samples/.../piano_001.wav", // ścieżka backendowa
			"name": "piano_001.wav",
			"url": "/api/local-samples/Instrument%20Oneshots/Piano/piano_001.wav",
			"subtype": "Grand",
			"family": "Keys",
			"category": "Instrument",
			"pitch": "C4"
		}
		// ...inne sample...
	],
	"default": {
		"id": "piano_001",
		"file": "...",
		"name": "piano_001.wav",
		"url": "/api/local-samples/...",
		"subtype": "Grand",
		"family": "Keys",
		"category": "Instrument",
		"pitch": "C4"
	}
}
```

Frontend korzysta z pola `url`, aby odtwarzać sample po HTTP (odseparowanie
od ścieżek dyskowych po stronie backendu).

Moduł korzysta z funkcji `_resolve_target_instruments`, która stara się
dopasowywać:

- synonimy (np. "pads" → "Pad"),
- grupy ("drums" → Kick, Snare, Hat, Clap),
- aliasy dla FX,
- różne warianty zapisu (case-insensitive, liczba mnoga/jednostkowa itd.).

---

## 4. Zachowanie frontendu (`ParamPlanStep`)

Główny krok w UI (`ParamPlanStep` w `frontend-next/src/app/air/step-components`) używa
modułu w następujący sposób:

1. Użytkownik wpisuje prompt opisujący utwór.
2. UI pobiera listę providerów i modeli z endpointów `/providers` i `/models`.
3. Po kliknięciu „Generuj parametry” frontend:
	 - buduje obiekt `parameters` (z domyślnymi wartościami),
	 - wysyła `POST /api/air/param-generation/plan` z `{ parameters, provider, model }`.
4. Odpowiedź z backendu (`parsed.meta`) jest normalizowana do lokalnego typu
	 `MidiParameters` (wewnętrzna reprezentacja planu w UI) i przekazywana do
	 komponentu `MidiPanel`.
5. `MidiPanel`:
	 - wyświetla aktualne parametry (tempo, tonację, listę instrumentów itd.),
	 - pozwala włączać/wyłączać instrumenty oraz modyfikować ich
		 konfigurację (`InstrumentConfig`),
	 - komunikuje się z inventory przez endpointy proxy `available-instruments`
		 i `samples/{instrument}` w celu podpowiedzenia i wyboru konkretnych sampli.
6. Wybrany plan parametrów + mapowanie instrument → sample może zostać użyty
	 jako wejście do kolejnych modułów (MIDI, render), które są rozwijane
	 niezależnie.

---

## 5. Ważne uwagi i edge-case'y

1. **Moduł nie generuje MIDI:**
	 - System prompt wprost instruuje LLM, aby **nie** generował nut, patternów,
		 pianorolki, gridów itd.
	 - Wszystkie wyjścia są w warstwie meta/parametrów.

2. **Elastyczność odpowiedzi LLM:**
	 - Model ma swobodę zmiany `tempo`, `bars`, listy instrumentów itd., aby
		 lepiej dopasować się do prompta.
	 - Frontend powinien traktować odpowiedź jako **propozycję startową** dla
		 użytkownika, nie prawdę objawioną.

3. **Parsowanie JSON:**
	 - `_safe_parse_json` próbuje odzyskać JSON nawet z lekko zepsutej
		 odpowiedzi (obcina do ostatniej klamry, usuwa bloki ```json).
	 - W przypadku problemów błędy są logowane w `errors` oraz w debug runie.

4. **Instrumenty spoza inventory:**
	 - `ParameterPlanIn` filtruje listę instrumentów względem listy dozwolonej
		 (statycznej + dynamicznej z inventory).
	 - Jeżeli LLM zaproponuje instrument, którego nie ma w inventory, może on
		 zostać odrzucony lub zastąpiony domyślnym zestawem (`piano, pad, strings`).

5. **Debugowanie:**
	 - Każde wywołanie `POST /plan` generuje `run_id` zapisany w pamięci oraz
		 logi etapów (start, wywołanie providera, parsowanie, zapis plików).
	 - `GET /api/air/param-generation/debug/{run_id}` pozwala na podejrzenie
		 pełnej historii danego wywołania (użyteczne w dev-toolsach frontendu).

---

## 6. Szybkie podsumowanie

- Moduł `param_generation` to **parameter planner** – dostarcza jedynie
	strukturalny opis utworu.
- Komunikuje się z różnymi providerami LLM przez zunifikowane API.
- Integruje się z inventory, ale sam nie dotyka plików audio (poza wskazywaniem
	ścieżek URL do odtwarzania sampli).
- Jego celem jest odseparowanie **tworzenia pomysłu na utwór** od późniejszego
	generowania **konkretnych sekwencji MIDI i audio**.

