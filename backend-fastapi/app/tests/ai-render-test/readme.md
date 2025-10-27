## Moduł ai-param-test — przewodnik krok po kroku

Ten moduł testuje proces „AI-assisted parametrization” kompozycji: model LLM pomaga dobrać parametry (styl, nastrój, tempo, instrumentarium itd.), a następnie prosty silnik proceduralny generuje wzór MIDI i renderuje audio z lokalnych sampli. Na dziś:

- AI działa w warstwie doboru parametrów (LLM → JSON ze schematem midi+audio).
- Generowanie MIDI jest proceduralne (nie-ML), ale respektuje parametry wejściowe.
- Render audio korzysta wyłącznie z lokalnych plików WAV w katalogu `local_samples/` i jest celowo uproszczony.


### Co dostajesz po uruchomieniu
- Wygenerowane artefakty per-run w `app/tests/ai-param-test/output/<UTC>_<RUN_ID>/`:
	- `midi.json` — wewnętrzna reprezentacja wzoru (bary, eventy, warstwy).
	- `midi.mid` + opcjonalnie `midi_<instrument>.mid` — eksport do pliku MIDI (jeśli zainstalowano `mido`).
	- `pianoroll_<run>.png` + `pianoroll_<run>_<instrument>.png` — wizualizacje piano roll (jeśli zainstalowano `matplotlib`).
	- `audio.wav` — miks mono.
	- `stem_<instrument>.wav` — stem per instrument.
	- `selection.json` — migawka użytych sampli (pełna reprodukowalność).
- Szczegółowy log kroków (timeline) dostępny przez endpoint debug.


## Architektura (pliki kluczowe)
- `parameters.py` — walidacja i normalizacja parametrów MIDI/Audio (typy, domyślne, zakresy).
- `midi_engine.py` — generator wzoru (warstwy per instrument, 8 kroków na takt, proste losowanie nut w skali).
- `local_library.py` — skan lokalnych sampli WAV → mapowanie na instrumenty (heurystyki nazw katalogów/plików).
- `audio_renderer.py` — prosty renderer audio: nakłada zdarzenia na zsamplowany dźwięk, zapisuje miks i stem’y.
- `midi_visualizer.py` — render pianoroll do PNG (Matplotlib, tryb headless).
- `inventory.py` — budowa i odczyt `inventory.json` (podsumowanie bibliotek lokalnych).
- `pipeline.py` — spinacz przepływu (run_midi, run_render, run_full) + I/O artefaktów i logowanie.
- `router.py` — endpointy FastAPI pod prefiksem `/api/ai-param-test` (w tym chat-smoke/paramify do LLM).


## Przepływ działania (end-to-end)
1) Klient (lub LLM) dostarcza parametry w schemacie JSON (sekcje `midi` i `audio`).
2) `MidiParameters`/`AudioRenderParameters` walidują i uzupełniają wartości domyślne.
3) `midi_engine.generate_midi` tworzy wzór (warstwy: po jednym patternie na instrument) i łączy je w całość.
4) `local_library.discover_samples` skanuje `local_samples/` i wskazuje pliki .wav dopasowane do nazw instrumentów.
5) `audio_renderer.render_audio` renderuje plik `audio.wav` oraz stem’y — pitch-shift przez resampling (jeśli `numpy/scipy`).
6) Eksport: `midi.json`, `.mid` (jeśli `mido`), `pianoroll*.png` (jeśli `matplotlib`), `selection.json` i debug timeline.

Ważne: jeśli jakikolwiek instrument nie ma zmapowanego sample’u, run kończy się błędem 422 (strict mode).


## Dane wejściowe (schemat)
Sekcja `midi` (kluczowe pola):
- `style`, `mood`, `genre`(alias), `tempo`, `key`, `scale`, `meter` (np. "4/4"), `bars`, `length_seconds`.
- `form`: lista sekcji np. ["intro", "theme_A", "outro"].
- `dynamic_profile` (gentle|moderate|energetic), `arrangement_density` (minimal|balanced|dense), `harmonic_color` (diatonic|...).
- `instruments`: lista nazw instrumentów (np. ["flute", "synth_pad"]).
- `instrument_configs`: konfiguracje per instrument: `name`, `register` (low|mid|high|full), `role`, `volume` (0..1), `pan` (-1..1), `articulation`, `dynamic_range`, `effects`.
- `seed`: liczba lub null (powtarzalność losowania).

Sekcja `audio`:
- `sample_rate` (8000..192000), `seconds` (0.5..600), `master_gain_db` (globalny gain miksu).

Przykład (od LLM):
```json
{
	"midi": {
		"style": "ambient",
		"mood": "calm",
		"tempo": 60,
		"key": "C",
		"scale": "major",
		"meter": "4/4",
		"bars": 32,
		"length_seconds": 32,
		"form": ["intro", "theme_A", "outro"],
		"dynamic_profile": "moderate",
		"arrangement_density": "balanced",
		"harmonic_color": "diatonic",
		"instruments": ["flute", "synth_pad"],
		"instrument_configs": [
			{"name":"flute","register":"mid","role":"accompaniment","volume":0.8,"pan":0,"articulation":"legato","dynamic_range":"moderate","effects":["reverb_long","delay_subtle"]},
			{"name":"synth_pad","register":"mid","role":"accompaniment","volume":0.6,"pan":0,"articulation":"sustain","dynamic_range":"moderate","effects":["reverb_long","chorus"]}
		],
		"seed": null,
		"genre": "ambient"
	},
	"audio": {"sample_rate":44100, "seconds":32, "master_gain_db":-3}
}
```


## Wymagania i przygotowanie środowiska
Minimalnie Python 3.12. Zainstaluj zależności z `backend-fastapi/requirements.txt`:

```powershell
cd "d:\Informatyka URZ\THE-HUB\backend-fastapi"
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Opcjonalne (zalecane) biblioteki dla dodatkowych artefaktów:
- `mido` — eksport `.mid`.
- `matplotlib` — pianoroll `.png`.
- `numpy`, `scipy` — lepsze próbkowanie/pitch-shift i szersze wsparcie WAV.

Klucze do dostawców LLM (dla endpointów `chat-smoke/*`) umieść w `backend-fastapi/.env` (np. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`).


## Katalog lokalnych sampli
- Domyślny katalog: `THE-HUB/local_samples/` (czyli obok `backend-fastapi/`).
- Moduł skanuje rekursywnie pliki: `.wav`, `.aiff`, `.aif`, `.flac`.
- Mapowanie instrumentów opiera się o tokeny w ścieżce nazwy, np. `piano`, `pad`, `strings`, `flute`, `bass`, perkusja: `kick`, `snare`, `hihat`, `clap`, `808`, `perc`, `tom`, `rim`, FX: `uplifter`, `downlifter`, `riser`, `impact`, `subdrop`, `fx`.
- Błędny lub brakujący instrument → 422 (strict mode). Najpierw sprawdź `/available-instruments`.


## Jak uruchomić backend i sprawdzić moduł
1) Uruchom FastAPI (UVicorn):

```powershell
cd "d:\Informatyka URZ\THE-HUB\backend-fastapi"
uvicorn app.main:app --reload --port 8000
```

2) Sprawdź metadane modułu:

```powershell
Invoke-RestMethod -Method GET http://localhost:8000/api/ai-param-test/meta | ConvertTo-Json -Depth 6
```

3) Zobacz listę dostępnych instrumentów (na podstawie `local_samples/`):

```powershell
Invoke-RestMethod -Method GET http://localhost:8000/api/ai-param-test/available-instruments | ConvertTo-Json -Depth 4
```

4) Wygeneruj MIDI (bez audio):

```powershell
$body = @{ genre="ambient"; mood="calm"; tempo=80; key="C"; scale="major"; bars=8; instruments=@("piano") } | ConvertTo-Json
Invoke-RestMethod -Method POST http://localhost:8000/api/ai-param-test/run/midi -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 8
```

5) Pełny render (MIDI + audio):

```powershell
$payload = @{ midi = @{ bars=8; instruments=@("flute"); tempo=80 }; audio = @{ seconds=6; sample_rate=44100 } } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method POST http://localhost:8000/api/ai-param-test/run/render -ContentType 'application/json' -Body $payload | ConvertTo-Json -Depth 8
```

Artefakty pojawią się w `app/tests/ai-param-test/output/<TS>_<RUN_ID>/`. Możesz je też serwować statycznie z 
`/api/ai-param-test/output/...` (patrz `app.main` → `StaticFiles`).


## Endpointy (skrót)
- `GET /api/ai-param-test/presets` — gotowe presety parametrów (minimal/full).
- `GET /api/ai-param-test/meta` — metadane modułu, wersja schematu.
- `GET /api/ai-param-test/available-instruments` — szybki spis instrumentów.
- `GET /api/ai-param-test/inventory` — pełny inwentarz sampli (zliczenia, przykłady, wiersze `samples`).
- `POST /api/ai-param-test/inventory/rebuild?mode=deep` — przebuduj inwentarz (w `deep` dodaje `sample_rate`, `length_sec`).
- `POST /api/ai-param-test/run/midi` — tylko MIDI (+ eksporty).
- `POST /api/ai-param-test/run/render` — MIDI + wybór sampli + render audio.
- `POST /api/ai-param-test/run/full` — alias `run/render`.
- `GET /api/ai-param-test/debug/{run_id}` — timeline debug dla wskazanego run’u.

Opcjonalnie (LLM):
- `POST /api/ai-param-test/chat-smoke/paramify` — poproś LLM o zwrócenie JSON-a w naszym schemacie i normalizację.
- `POST /api/ai-param-test/chat-smoke/send` — czat surowy lub „structured” (jak wyżej) zależnie od parametru.


## Przykładowy timeline (debug)
Fragment struktury zdarzeń (czas, stage, message, data), np.:

```
[run] started
[meta] module_version {"module":"ai_param_test","version":"0.1.0"}
[run] render_phase
[params] composition { ... }
[params] instrumentarium { ... }
[params] audio_render { ... }
[call] generate_midi {"seed":null}
[func] enter {"module":"midi_engine","function":"generate_midi"}
[midi] bar_composed {"bar":0,"events":7,"layer":"flute"}
...
[audio] render_done {"file":".../audio.wav","bytes":2822444}
[viz] pianoroll_saved {"file":".../pianoroll_<run>.png"}
[midi] export_mid {"file":".../midi.mid"}
[run] completed
```

Użyj `GET /api/ai-param-test/debug/{run_id}` aby pobrać pełen timeline.


## Ograniczenia i uwagi
- MIDI: prosty generator (losowość w ramach skali i siatki 8 kroków/takt). Nie jest to model ml.
- Audio: render uproszczony, mono, bez zaawansowanego miksu/FX; pitch-shift przez resampling.
- Strict mode: wymagany co najmniej jeden plik na każdy wnioskowany instrument.
- Mapowanie instrumentów jest heurystyczne (na podstawie nazw). Dostosuj strukturę `local_samples/`, aby poprawić trafność.


## Troubleshooting
- 422 unknown_instruments — sprawdź `GET /available-instruments`, dopasuj nazwy `instruments` do wyników.
- 422 missing_samples — brak sample’a dla któregoś instrumentu. Dodaj pliki do `local_samples/` lub usuń instrument z listy.
- Brak `midi.mid` — doinstaluj `mido` (jest w `requirements.txt`).
- Brak `pianoroll_*.png` — doinstaluj `matplotlib`.
- Błędy odczytu WAV — zainstaluj `numpy` i `scipy` (szersza obsługa formatów), sprawdź 16‑bit PCM.
- Ścieżka `local_samples/` — moduł oczekuje katalogu na poziomie repo (`THE-HUB/local_samples`).
- Windows/PowerShell — jeśli masz restrykcje ExecutionPolicy, włącz sesyjnie: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.


## Roadmap (kierunki rozwoju)
- Lepszy silnik kompozycyjny (motywy, harmonie, patterny per styl).
- Wielościeżkowy eksport MIDI (per warstwa do osobnych tracków).
- Miks wielokanałowy i efekty (reverb/delay/chorus) konfigurowalne z `instrument_configs`.
- Lepsze odwzorowanie głośności/panoramy z `instrument_configs` podczas renderu.
- Konfigurowalne mapowanie instrument↔folder (JSON/ENV).


## Szybka ściąga
- Prefiks API: `/api/ai-param-test`.
- Artefakty: `app/tests/ai-param-test/output/<TS>_<RUN_ID>/` oraz statycznie pod `/api/ai-param-test/output/...`.
- Klucze LLM w `.env` jeśli używasz `chat-smoke/*`.
- Najpierw sprawdź `/available-instruments`, potem wołaj `/run/render`.


Miłej eksploracji — jeśli chcesz, mogę przygotować też gotowe zapytania w formacie `.http` lub skrypty PowerShell do szybkich testów.

