# Techniczny Deep Dive

## 1. MIDI Generator - Szczegóły implementacji

### 1.1 Mapowanie parametrów na dane muzyczne

```python
KEY_SIGNATURES = {
    "C": [60, 62, 64, 65, 67, 69, 71],  # C major scale
    "F": [65, 67, 69, 70, 72, 74, 76],  # F major scale
}
```

**Co się dzieje:**
- Każda liczba to **MIDI note number** (60 = C4, 62 = D4, etc.)
- Skala muzyczna definiuje dostępne nuty dla melodii
- F major = F-G-A-Bb-C-D-E (65-67-69-70-72-74-76)

### 1.2 Generowanie tempo w MIDI

```python
tempo = int(60000000 / self.params.tempo)  # Mikrosekund na beat
```

**Matematyka:**
- MIDI tempo = mikrosekundy na quarter note
- 120 BPM = 60,000,000 / 120 = 500,000 μs per beat
- 60 BPM = 60,000,000 / 60 = 1,000,000 μs per beat

### 1.3 Algorytm generowania akordów (Pad)

```python
def _generate_pad_chords(self, track, channel, notes, bars, ticks_per_beat):
    chord_duration = ticks_per_beat * 4  # Cały takt = 1920 ticks
    
    chords = [
        [notes[0], notes[2], notes[4]],  # I triad (F-A-C)
        [notes[3], notes[5], notes[0] + 12],  # IV triad (Bb-D-F)
        [notes[4], notes[6], notes[1] + 12],  # V triad (C-E-G) 
        [notes[0], notes[2], notes[4]],  # Powrót do I
    ]
```

**Teoria muzyczna:**
- **I-IV-V-I** - najbardziej podstawowa progresja harmoniczna
- **Triad** = akord trzydźwiękowy (root + tercja + kwinta)
- **+12** = oktawa wyżej (doubling w wyższym rejestrze)

**Timing w MIDI:**
- **ticks_per_beat = 480** (standard MIDI resolution)
- **Cały takt = 480 × 4 = 1920 ticks**
- Każdy akord gra przez cały takt

### 1.4 Algorytm melodii pianina

```python
def _generate_piano_melody(self, track, channel, notes, bars, ticks_per_beat):
    note_duration = ticks_per_beat // 2  # 240 ticks = ósemka
    
    for bar in range(8):  # 8 taktów
        for beat in range(8):  # 8 ósemek na takt
            note = random.choice(notes)  # Losowa nuta ze skali
            if random.random() > 0.3:  # 70% szans na nutę
                velocity = random.randint(50, 80)  # Siła uderzenia
                track.append(Message('note_on', note=note, velocity=velocity))
                track.append(Message('note_off', note=note, time=note_duration))
```

**Algorytm:**
1. **Podział rytmiczny:** 8 ósemek na takt (240 ticks każda)
2. **Selekcja nut:** Tylko nuty z zadanej skali (tonalność)
3. **Probabilistyka:** 70% szans na nutę, 30% na pauzę
4. **Velocity:** Random 50-80 (średnia głośność z wariacjami)

## 2. Sample Fetcher - Synteza dźwięku

### 2.1 Generowanie tonu pianina

```python
# Częstotliwość bazowa (C4)
frequency = 261.63  # Hz

# Harmoniczne (overtones)
audio = (np.sin(2 * np.pi * frequency * t) * 0.3 +      # Fundamental
         np.sin(2 * np.pi * frequency * 2 * t) * 0.1 +   # 2nd harmonic
         np.sin(2 * np.pi * frequency * 3 * t) * 0.05)   # 3rd harmonic
```

**Fizyka dźwięku:**
- **Fundamental frequency** - główna częstotliwość nuty
- **Harmoniczne** - wielokrotności frequency (2f, 3f, 4f...)
- **Amplitudes** malejące (0.3, 0.1, 0.05) = naturalny ton

### 2.2 ADSR Envelope dla pianina

```python
attack = int(0.01 * sample_rate)   # 10ms attack
decay = int(0.3 * sample_rate)     # 300ms decay  
sustain_level = 0.7                # 70% of peak
release = int(0.5 * sample_rate)   # 500ms release

envelope = np.ones_like(audio)
envelope[:attack] = np.linspace(0, 1, attack)              # Ramp up
envelope[attack:attack + decay] = np.linspace(1, 0.7, decay)  # Decay to sustain
envelope[-release:] = np.linspace(0.7, 0, release)         # Fade out
```

**ADSR Model:**
- **Attack:** Jak szybko dźwięk osiąga peak (10ms = szybki atak pianina)
- **Decay:** Jak szybko spada do sustain (300ms)
- **Sustain:** Poziom podtrzymania (70% = naturalne dla pianina)
- **Release:** Jak długo schodzi do zera (500ms)

### 2.3 Generowanie akordu (Strings)

```python
freq_c = 261.63  # C4
freq_e = 329.63  # E4  
freq_g = 392.00  # G4

audio = (np.sin(2 * np.pi * freq_c * t) * 0.3 +
         np.sin(2 * np.pi * freq_e * t) * 0.3 +
         np.sin(2 * np.pi * freq_g * t) * 0.3)
```

**Teoria:**
- **C Major Triad** = C + E + G (tercja wielka + kwinta czysta)
- **Równe amplitudy** = zbalansowany akord
- **Częstotliwości** obliczone z równostrojowego systemu

## 3. Audio Synthesizer - Konwersja MIDI→Audio

### 3.1 Analiza struktury MIDI

```python
for track_idx, track in enumerate(midi_file.tracks):
    current_time_ticks = 0
    active_notes = {}
    current_instrument = "piano"
    
    for msg in track:
        current_time_ticks += msg.time  # Akumuluj czas
        current_time_seconds = current_time_ticks * seconds_per_tick
        current_sample = int(current_time_seconds * sample_rate)
```

**Time conversion:**
- **MIDI time** = relative ticks od poprzedniej wiadomości
- **Absolute time** = akumulacja wszystkich msg.time
- **Sample time** = seconds × 44100 = index w buforze audio

### 3.2 Pitch Shifting sampli

```python
def _generate_note_audio(self, midi_note: int, velocity: int, instrument: str):
    frequency = self.note_frequencies[midi_note]  # Hz dla tej nuty
    sample_data = self.loaded_samples[instrument]['audio_data']
    
    # Pitch shifting
    base_freq = 261.63  # C4 reference
    pitch_ratio = frequency / base_freq
    
    # Resample przez zmianę długości
    new_length = int(len(sample_data) / pitch_ratio)
    indices = np.linspace(0, len(sample_data) - 1, new_length)
    pitched_sample = np.interp(indices, range(len(sample_data)), sample_data)
```

**Algorytm pitch shifting:**
1. **Oblicz pitch ratio:** target_freq / base_freq
2. **Zmień długość sampla:** więcej samples = niższa częstotliwość
3. **Interpolacja:** np.interp() = liniowa interpolacja między samples
4. **Przykład:** A4 (440Hz) vs C4 (261.63Hz) = ratio 1.68 = sample 68% krótszy

### 3.3 Velocity mapping

```python
amplitude = velocity / 127.0  # MIDI velocity 0-127 → 0.0-1.0
audio = audio * amplitude     # Pomnóż amplitude
```

**MIDI velocity:**
- **0** = cicho (note off equivalent)
- **64** = mezzo-forte (średnia głośność)
- **127** = fortissimo (maksymalna głośność)

### 3.4 Stereo mixing i panning

```python
for i, track in enumerate(audio_tracks):
    if i % 2 == 0:
        # Left channel bias
        mixed_audio[:, 0] += padded_track * 0.7  # 70% left
        mixed_audio[:, 1] += padded_track * 0.3  # 30% right
    else:
        # Right channel bias  
        mixed_audio[:, 0] += padded_track * 0.3  # 30% left
        mixed_audio[:, 1] += padded_track * 0.7  # 70% right
```

**Stereo field:**
- **Track 0** (Piano): 70% left, 30% right
- **Track 1** (Strings): 30% left, 70% right
- **Track 2** (Pad): 70% left, 30% right
- = Przestrzenny mix zamiast mono

### 3.5 Normalizacja audio

```python
max_amplitude = np.max(np.abs(mixed_audio))
if max_amplitude > 0:
    mixed_audio = mixed_audio / max_amplitude * 0.9  # 90% max to prevent clipping
```

**Dlaczego 0.9:**
- **Digital clipping** występuje przy amplitude = 1.0
- **Headroom** 10% zapobiega distortion
- **Peak normalization** = najgłośniejszy sample → 90% max

## 4. Kluczowe algorytmy muzyczne

### 4.1 Frequency→MIDI note conversion

```python
def freq_to_midi(frequency):
    return 69 + 12 * math.log2(frequency / 440.0)

def midi_to_freq(midi_note):
    return 440.0 * (2 ** ((midi_note - 69) / 12.0))
```

**Matematyka:**
- **A4 = MIDI note 69 = 440 Hz** (reference)
- **Equal temperament:** każdy półton = 2^(1/12) ratio
- **Octave = 12 półtonów = frequency × 2**

### 4.2 Time quantization

```python
seconds_per_tick = (tempo_microseconds / 1000000.0) / ticks_per_beat
# tempo=500000μs, tpb=480 → 0.00108 seconds per tick
```

**MIDI timing:**
- **Tempo** w μs per quarter note
- **Ticks per beat** = resolution (480 = wysoka dokładność)
- **1 tick** = najmniejsza jednostka czasu w MIDI

### 4.3 Harmonic series generation

```python
def generate_harmonics(fundamental, num_harmonics=4):
    harmonics = []
    for n in range(1, num_harmonics + 1):
        freq = fundamental * n
        amplitude = 1.0 / n  # Natural decay
        harmonics.append((freq, amplitude))
    return harmonics
```

**Fizyka:**
- **Harmoniczne** = wielokrotności częstotliwości podstawowej
- **Natural amplitude decay** = 1/n (brzmi naturalnie)
- **Timbre** instrumentu = unique harmonic profile

## 5. Dlaczego to brzmi jak muzyka?

### 5.1 Matematyczne podstawy

1. **Skale muzyczne** = matematyczne ratios między częstotliwościami
2. **Harmonie** = częstotliwości o prostych proporcjach (2:3, 3:4, 4:5)
3. **Rytm** = regularne podziały czasu
4. **ADSR** = imituje naturalne zachowania instrumentów

### 5.2 Psychoakustyka

1. **Pitch perception** = logarytmiczna (stąd równostrojny system)
2. **Harmonic consonance** = mózg preferuje proste ratios
3. **Temporal expectation** = regularny beat = przewidywalność
4. **Stereo imaging** = przestrzenność = bogatsza percepcja

To wszystko razem tworzy **emergent musical behavior** z relatywnie prostych algorytmów!