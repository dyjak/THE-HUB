from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json, time, re

from .analyze_pitch_fft import estimate_root_pitch

# ten moduł buduje oraz wczytuje inventory.json.
#
# inventory.json to "spis sampli" w `local_samples/`.
# zawiera:
# - listę instrumentów (nazwy + proste statystyki)
# - listę sampli (ścieżki, kategoria, rodzina, subtype, pitch z nazwy, itd.)
# - opcjonalnie dane "deep" (np. rms/gain_db_normalize oraz root_midi z fft)
#
# dlaczego to istnieje:
# - inne kroki (param_generation, render) potrzebują stabilnej listy instrumentów i sampli
# - zamiast za każdym razem skanować filesystem, robimy to raz i zapisujemy do json


INVENTORY_FILE = Path(__file__).parent / "inventory.json"
INVENTORY_SCHEMA_VERSION = "air-inventory-1"

# domyślny katalog sampli, jeśli inventory.json nie definiuje pola `root`.
# uwaga: parents[4] wskazuje na root repo (THE-HUB) przy obecnej strukturze projektu.
DEFAULT_LOCAL_SAMPLES_ROOT = Path(__file__).resolve().parents[4] / "local_samples"


def _rel(path: Path) -> str:
    # zwraca ścieżkę względną względem `DEFAULT_LOCAL_SAMPLES_ROOT` (do stabilnego id i url)
    try:
        return str(path.relative_to(DEFAULT_LOCAL_SAMPLES_ROOT))
    except Exception:
        return path.name


def build_inventory(deep: bool = False) -> Dict[str, Any]:
    """skanuje `local_samples/` i generuje (albo przebudowuje) inventory.json.

    co dokładnie robimy:
    - klasyfikujemy sample do instrumentów prostym, odpornym klasyfikatorem (słowa kluczowe w ścieżce)
    - zapisujemy ścieżki absolutne i względne, żeby później łatwo budować url do odsłuchu
    - opcjonalnie (deep=True) liczymy proste statystyki audio (rms, gain_db_normalize, root_midi)
    - pomijamy pliki uszkodzone/nieczytelne, żeby nie trafiały do ui ani renderu
    - trzymamy stabilny schemat json, żeby inne moduły nie musiały się zmieniać
    """
    root = DEFAULT_LOCAL_SAMPLES_ROOT
    audio_exts = {".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg", ".m4a", ".wvp"}

    def _tokenize_path(parts: List[str], filename: str) -> set[str]:
        """tokenizuje ścieżkę katalogów i nazwę pliku na zestaw "tokenów" (lowercase).

        po co:
        - chcemy prosto i odporne wyłapywać słowa kluczowe (bez zależności od konkretnego nazewnictwa paczek)
        - dodajemy też dopasowania po substringach, żeby np. "clubkick" nadal pasowało do "kick"
        """
        raw = "/".join(parts + [filename])
        raw_low = raw.lower()
        toks = re.split(r"[^A-Za-z0-9#]+", raw_low)
        out: set[str] = set()

        # słowa kluczowe, które chcemy wykrywać nawet jako część większego tokena.
        # lista powinna być krótka i "wysokosygnałowa", bo bezpośrednio wpływa na klasyfikację.
        substr_keywords = {
            # drums
            "kick",
            "snare",
            "clap",
            "hat",
            "hihat",
            "crash",
            "ride",
            "splash",
            "tom",
            "rim",
            "shaker",
            "shake",
            # percs / misc
            "perc",
            "percs",
            "guiro",
            "tamb",
            "tambourine",
            "cowbell",
            "clave",
            # generic
            "fx",
            "hit",
            "hits",
            # common short variants
            "snap",  # e.g. "Snaph" -> treat as snare-ish
        }

        for t in toks:
            if not t:
                continue
            out.add(t)
            if len(t) > 3 and t.endswith("s"):
                out.add(t[:-1])
            # Add keyword sub-tokens if they are substrings of the token
            for kw in substr_keywords:
                if kw in t:
                    out.add(kw)

        # normalizacja częstych wariantów
        if "hi" in out and "hat" in out:
            out.add("hihat")
        if "hi-hat" in raw_low:
            out.add("hihat")
        if "808s" in raw_low:
            out.add("808")
        return out

    def _detect_pitch(name: str) -> str | None:
        """wyciąga pitch (np. A, A#3, Bb2, F) z nazwy pliku, jeśli da się go rozpoznać.

        zwracamy ostatnie dopasowanie, bo często bardziej szczegółowe oznaczenie jest na końcu.
        """
        # dopasowanie z "word boundary" żeby ograniczyć false positive
        # przykłady: "C", "C#", "Db", "F3", "A#4"
        pat = re.compile(r"(?<![A-Za-z])([A-G])([#b]?)([0-8]?)(?![A-Za-z])")
        matches = list(pat.finditer(name))
        if not matches:
            return None
        m = matches[-1]
        note = m.group(1).upper()
        acc = m.group(2)
        octv = m.group(3)
        return note + acc + (octv or "")

    def classify(rel_parts: List[str], file_name: str) -> Tuple[str, str | None, str | None, str | None, str | None]:
        """klasyfikuje plik do instrumentu na podstawie ścieżki i nazwy.

        zwraca krotkę: (instrument, family, category, subtype, pitch)

        znaczenie pól:
        - family: najwyższy katalog pod root (często nazwa paczki)
        - category: szersza kategoria typu "Drums" lub "FX" (jeśli ma sens)
        - subtype: dodatkowy detal (często równy instrumentowi dla perkusji)
        - pitch: rozpoznany z nazwy pliku (jeśli występuje)
        """
        tokens = _tokenize_path(rel_parts, file_name)
        family = rel_parts[0] if rel_parts else None
        container = family.lower() if family else None
        # typowy układ: root/Instruments/<pack>/... oraz root/Drums/<pack>/...
        pack = rel_parts[1] if len(rel_parts) > 1 and container in {"instruments", "drums"} else None
        pitch = _detect_pitch(file_name)

        name_upper = file_name.upper()

        # 1) jawne reguły po nazwie pliku (specjalne przypadki)
        # acoustic guitar: nazwa zawiera "ACOUSTICG"
        if "ACOUSTICG" in name_upper:
            return "Acoustic Guitar", family, None, None, pitch

        # electric guitar: nazwa zawiera "DARK STAR METAL"
        if "DARK STAR METAL" in name_upper:
            return "Electric Guitar", family, None, None, pitch

        # bass guitar: nazwa zawiera "DEEPER PURPLE"
        if "DEEPER PURPLE" in name_upper:
            return "Bass Guitar", family, None, None, pitch

        # trombone: nazwa zawiera "TRO MLON"
        if "TRO MLON" in name_upper:
            return "Trombone", family, None, None, pitch

        # piano: specjalne przypadki: "CHANGPIANOHARD" albo prefix "Gz_"
        if "CHANGPIANOHARD" in name_upper or name_upper.startswith("GZ_"):
            return "Piano", family, None, None, pitch

        # 2) reguły po folderach (wysokopoziomowe)
        # wspieramy układ bezpośredni (root/Piano/...) oraz zgrupowany (root/Instruments/Piano/...)
        if family:
            fam_low = family.lower()
            pack_low = pack.lower() if isinstance(pack, str) else None

            # Direct root-level categories
            if fam_low == "choirs":
                return "Choirs", family, None, None, pitch
            if fam_low == "fx":
                return "FX", family, "FX", None, pitch
            if fam_low == "pads":
                return "Pads", family, None, None, pitch
            if fam_low == "strings":
                return "Strings", family, None, None, pitch
            if fam_low == "sax":
                return "Sax", family, None, None, pitch
            if fam_low == "trombone":
                return "Trombone", family, None, None, pitch
            if fam_low == "piano":
                return "Piano", family, None, None, pitch

            # Grouped under Instruments
            if fam_low == "instruments" and pack_low:
                if pack_low == "choirs":
                    return "Choirs", family, None, None, pitch
                if pack_low == "pads":
                    return "Pads", family, None, None, pitch
                if pack_low == "strings":
                    return "Strings", family, None, None, pitch
                if pack_low == "piano":
                    return "Piano", family, None, None, pitch
                if pack_low == "bass":
                    return "Bass", family, None, None, pitch
                if pack_low == "sax":
                    return "Sax", family, None, None, pitch
                if pack_low == "trombone":
                    return "Trombone", family, None, None, pitch
                if pack_low == "orchestral":
                    # w tej bibliotece orchestral to głównie smyczki/dęte.
                    # trzymamy to prosto i mapujemy na strings (frontend to rozumie).
                    return "Strings", family, None, None, pitch
                if pack_low == "hits":
                    # impacts/hits zachowują się bardziej jak fx niż pads.
                    return "FX", family, "FX", None, pitch
                if pack_low in {"perc", "percs"}:
                    # jeśli później chcemy osobny instrument "percs", to tutaj jest miejsce do zmiany.
                    return "Shake", family, None, None, pitch
                if pack_low == "guitar":
                    # preferujemy klasyfikację po katalogach, jeśli jest dostępna:
                    # root/Instruments/Guitar/<Bass|Acoustic|Electric>/...
                    sub = rel_parts[2].lower() if len(rel_parts) > 2 else ""
                    if sub == "bass" or "bass" in tokens:
                        return "Bass Guitar", family, None, None, pitch
                    if sub == "acoustic" or "acoustic" in tokens:
                        return "Acoustic Guitar", family, None, None, pitch
                    if sub == "electric" or "electric" in tokens:
                        return "Electric Guitar", family, None, None, pitch
                    # jeśli nie wiemy, nie wciskamy tego na siłę w pads; lecimy do reguł tokenowych.

        # 3) perkusja: szczegółowe subtype (wszystko pod category "Drums")
        drum_subs = {
            "clap": "Clap",
            "hat": "Hat",
            "hihat": "Hat",
            "kick": "Kick",
            "snare": "Snare",
            "snap": "Snare",
            "crash": "Crash",
            "ride": "Ride",
            "splash": "Splash",
            "tom": "Tom",
            "rim": "Rim",
            "shake": "Shake",
            "shaker": "Shake",
        }
        for kw, sub in drum_subs.items():
            if kw in tokens:
                return sub, family or "Drums", "Drums", sub, pitch

        # dodatkowe tokeny perkusyjne, które nie powinny trafiać do pads.
        # jeśli plik żyje pod /Drums, wolimy potraktować go jako shake.
        if container == "drums":
            for kw in ("guiro", "tamb", "tambourine", "cowbell", "clave", "perc", "percs"):
                if kw in tokens:
                    return "Shake", family or "Drums", "Drums", "Shake", pitch
            if "fx" in tokens or "hit" in tokens:
                return "FX", family or "Drums", "Drums", "FX", pitch

        # 4) pozostałe, szersze kategorie instrumentów
        # uwaga: nie dodajemy ogólnego fallbacku "guitar", żeby nie mylić electric/acoustic.
        single_map = [
            ("choir", "Choirs"),
            ("string", "Strings"),
            ("sax", "Sax"),
            ("trombone", "Trombone"),
            ("pad", "Pads"),
            ("piano", "Piano"),
            ("bass", "Bass"),
            ("fx", "FX"),
            ("hit", "FX"),
        ]
        for kw, inst in single_map:
            if kw in tokens:
                return inst, family, None, None, pitch

        # 5) fallback: fx lub pads w zależności od folderu
        if family and family.lower() == "fx":
            return "FX", family, "FX", None, pitch

        # neutralny fallback melodyczny.
        # unikamy przepełniania pads: wybieramy pads tylko jeśli ścieżka/nazwa to sugeruje.
        if "pad" in tokens or (container == "instruments" and isinstance(pack, str) and pack.lower() == "pads"):
            return "Pads", family, None, None, pitch
        # w przeciwnym razie pod /Drums traktujemy to jako fx (one-shoty), a na końcu jako pads.
        if container == "drums":
            return "FX", family, "Drums", "FX", pitch
        return "Pads", family, None, None, pitch

    instruments: Dict[str, Any] = {}
    all_samples: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0

    try:
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in audio_exts:
                continue
            # pomijamy niektóre fx, których nie chcemy w inventory
            name_lower = f.name.lower()
            if "downlifter" in name_lower or "uplifter" in name_lower:
                continue
            try:
                rel = f.relative_to(root)
            except Exception:
                # jeśli plik jest poza oczekiwanym rootem, pomijamy
                continue

            # lekki test poprawności: próbujemy raz otworzyć plik audio.
            # dzięki temu uszkodzone/nieczytelne pliki nie trafiają do inventory,
            # i tym samym nie pojawią się w panelu ani w playbacku.
            try:
                if f.suffix.lower() == ".wav":
                    import wave as _wav  # type: ignore
                    with _wav.open(str(f), "rb") as _wf:  # type: ignore
                        _ = _wf.getnframes()
                else:
                    # na razie inne formaty traktujemy jako "zaufane"; można rozszerzyć w przyszłości.
                    pass
            except Exception:
                # plik uszkodzony/nieczytelny -> całkowicie pomijamy
                continue

            rel_parts = list(rel.parts[:-1])  # directory parts only
            instrument, family, category, subtype, pitch = classify(rel_parts, f.name)
            size = 0
            try:
                size = f.stat().st_size
            except Exception:
                pass

            # opcjonalna analiza "deep" (głośność/długość/pitch) w trybie deep=True
            sample_rate: int | None = None
            length_sec: float | None = None
            loudness_rms: float | None = None
            gain_db_normalize: float | None = None
            root_midi: float | None = None
            if deep:
                try:
                    import wave as _wav  # type: ignore
                    import contextlib as _ctx  # type: ignore
                    import math as _math  # type: ignore
                    with _ctx.closing(_wav.open(str(f), "rb")) as wf:
                        sr = wf.getframerate()
                        n_channels = wf.getnchannels()
                        n_frames = wf.getnframes()
                        # limit klatek dla rms, żeby było szybko na dużych plikach
                        max_frames = min(n_frames, sr * 60)
                        frames = wf.readframes(max_frames)
                        import struct as _struct  # type: ignore

                        if wf.getsampwidth() == 2 and n_channels > 0:
                            total_samples = max_frames * n_channels
                            fmt = "<" + "h" * total_samples
                            try:
                                ints = _struct.unpack(fmt, frames)
                                # downmix do mono: bierzemy pierwszy kanał
                                mono = ints[0::n_channels]
                                if mono:
                                    # normalizacja do [-1, 1]
                                    vals = [x / 32768.0 for x in mono]
                                    n = float(len(vals))
                                    if n > 0:
                                        rms = _math.sqrt(sum(v * v for v in vals) / n)
                                        loudness_rms = float(rms)
                                        # cel rms ~0.2 (umowny, ale sensowny pod headroom)
                                        target = 0.2
                                        if rms > 0:
                                            gain_db_normalize = float(-20.0 * _math.log10(rms / target))
                            except Exception:
                                pass
                        sample_rate = int(sr)
                        if sr > 0:
                            length_sec = float(n_frames) / float(sr)
                except Exception:
                    pass

                # opcjonalna estymacja root pitch przez fft
                try:
                    est = estimate_root_pitch(f)
                    if est and "pitch_midi" in est:
                        root_midi = float(est["pitch_midi"])
                except Exception:
                    root_midi = None

            row = {
                "instrument": instrument,
                "id": rel.as_posix(),  # stable, human-inspectable id
                "file_rel": rel.as_posix(),
                "file_abs": str(f.resolve()),
                "bytes": size,
                "source": "local",
                "pitch": pitch,
                "category": category,
                "family": family,
                "subtype": subtype,
                "root_midi": root_midi,
                "sample_rate": sample_rate,
                "length_sec": length_sec,
                "loudness_rms": loudness_rms,
                "gain_db_normalize": gain_db_normalize,
            }
            all_samples.append(row)
            total_files += 1
            total_bytes += size
            inst_meta = instruments.setdefault(instrument, {"count": 0, "examples": []})
            inst_meta["count"] += 1
            if len(inst_meta["examples"]) < 5:
                inst_meta["examples"].append(f.name)
    except FileNotFoundError:
        # Empty inventory when folder is missing
        pass
    # pole `root`: preferujemy istniejące inventory root, w przeciwnym razie fallback
    try:
        existing = load_inventory() or {}
        root_str = existing.get("root") or str(DEFAULT_LOCAL_SAMPLES_ROOT)
    except Exception:
        root_str = str(DEFAULT_LOCAL_SAMPLES_ROOT)

    payload = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "generated_at": time.time(),
        "root": root_str,
        "instrument_count": len(instruments),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "instruments": instruments,
        "samples": all_samples,
        "deep": deep,
    }
    try:
        with INVENTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return payload


def load_inventory() -> Dict[str, Any] | None:
    # wczytuje inventory.json z dysku (zwraca None, jeśli pliku nie ma albo jest niepoprawny)
    if not INVENTORY_FILE.exists():
        return None
    try:
        return json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
