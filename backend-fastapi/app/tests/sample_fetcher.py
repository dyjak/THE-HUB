import sys

import requests
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import tempfile
from urllib.parse import urljoin
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

# Załaduj .env explicite z katalogu backend-fastapi aby niezależnie od cwd mieć dostęp do kluczy
if load_dotenv is not None:
    try:
        from pathlib import Path
        # __file__ -> app/tests/sample_fetcher.py ; parents[2] -> backend-fastapi/
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            if os.environ.get("FREESOUND_API_KEY"):
                print(f"[env] FREESOUND_API_KEY loaded (len={len(os.environ.get('FREESOUND_API_KEY'))})")
        else:
            # fallback – spróbuj standardowego wyszukiwania (nie powinno być potrzebne)
            load_dotenv()
    except Exception:
        pass


@dataclass
class SampleInfo:
    """Informacje o samplu"""
    id: str
    name: str
    url: str  # canonical/source url or scheme (generated://, freesound://<id>)
    duration: float
    instrument: str
    key: Optional[str] = None
    bpm: Optional[int] = None
    # Freesound metadata (opcjonalne)
    preview_mp3_url: Optional[str] = None
    preview_ogg_url: Optional[str] = None
    download_url: Optional[str] = None  # api download endpoint, requires token
    source: Optional[str] = None  # e.g., "generated", "freesound", "commons"
    origin_url: Optional[str] = None  # bezpośredni URL (preview lub plik) do wyświetlenia w UI


class SampleFetcher:
    """Klasa do pobierania sampli z różnych źródeł"""

    def __init__(self):
        # Możesz dodać API klucze do .env później
        self.freesound_api_key = os.environ.get("FREESOUND_API_KEY")  # Będzie potrzebny dla Freesound API
        self.temp_dir = tempfile.gettempdir()

    def get_basic_samples(self) -> Dict[str, SampleInfo]:
        """Zwraca podstawowe sample wbudowane (prosthetic samples)"""
        # Na początek używamy prostych tonów generowanych programowo
        basic_samples = {
            "piano_c4": SampleInfo(
                id="piano_c4",
                name="Piano C4",
                url="generated://piano/c4",
                duration=2.0,
                instrument="piano",
                key="C",
                source="generated",
                origin_url=None,
            ),
            "strings_pad": SampleInfo(
                id="strings_pad",
                name="String Pad",
                url="generated://strings/pad",
                duration=4.0,
                instrument="strings",
                source="generated",
                origin_url=None,
            ),
            "ambient_pad": SampleInfo(
                id="ambient_pad",
                name="Ambient Pad",
                url="generated://pad/ambient",
                duration=8.0,
                instrument="pad",
                source="generated",
                origin_url=None,
            ),
            "bass_c2": SampleInfo(
                id="bass_c2",
                name="Bass C2",
                url="generated://bass/c2",
                duration=1.5,
                instrument="bass",
                key="C",
                source="generated",
                origin_url=None,
            ),
            "drums_kit": SampleInfo(
                id="drums_kit",
                name="Drums Kit",
                url="generated://drums/kit",
                duration=1.0,
                instrument="drums",
                source="generated",
                origin_url=None,
            ),
            "guitar_e3": SampleInfo(
                id="guitar_e3",
                name="Guitar E3",
                url="generated://guitar/e3",
                duration=2.0,
                instrument="guitar",
                key="E",
                source="generated",
                origin_url=None,
            ),
            "sax_c4": SampleInfo(
                id="sax_c4",
                name="Saxophone C4",
                url="generated://saxophone/c4",
                duration=2.0,
                instrument="saxophone",
                key="C",
                source="generated",
                origin_url=None,
            ),
            "synth_c4": SampleInfo(
                id="synth_c4",
                name="Synth C4",
                url="generated://synth/c4",
                duration=2.5,
                instrument="synth",
                key="C",
                source="generated",
                origin_url=None,
            ),
            # dodatkowe instrumenty bazowe (fallback)
            "violin_g3": SampleInfo(
                id="violin_g3",
                name="Violin G3",
                url="generated://violin/g3",
                duration=2.0,
                instrument="violin",
                source="generated",
                origin_url=None,
            ),
            "cello_c3": SampleInfo(
                id="cello_c3",
                name="Cello C3",
                url="generated://cello/c3",
                duration=2.0,
                instrument="cello",
                source="generated",
                origin_url=None,
            ),
            "flute_c5": SampleInfo(
                id="flute_c5",
                name="Flute C5",
                url="generated://flute/c5",
                duration=2.0,
                instrument="flute",
                source="generated",
                origin_url=None,
            ),
            "trumpet_c4": SampleInfo(
                id="trumpet_c4",
                name="Trumpet C4",
                url="generated://trumpet/c4",
                duration=1.8,
                instrument="trumpet",
                source="generated",
                origin_url=None,
            ),
            "choir_c4": SampleInfo(
                id="choir_c4",
                name="Choir C4",
                url="generated://choir/c4",
                duration=3.0,
                instrument="choir",
                source="generated",
                origin_url=None,
            ),
        }
        return basic_samples

    def search_freesound_samples(self, query: str, instrument: Optional[str] = None, page_size: int = 10) -> List[SampleInfo]:
        """Wyszukuje sample w Freesound.org wg zapytania tekstowego.
        Preferuje pliki WAV i zwraca metadane preview oraz endpoint pobrania.
        Wymaga FREESOUND_API_KEY w env.
        """
        if not self.freesound_api_key:
            print("⚠️  Freesound API key not configured, using basic samples")
            return []

        url = "https://freesound.org/apiv2/search/text/"
        params = {
            "query": query,
            "filter": "type:wav duration:[0.2 TO 12]",
            "fields": "id,name,previews,duration,tags,license",
            "page_size": str(page_size),
        }
        headers = {"Authorization": f"Token {self.freesound_api_key}"}

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"⚠️  Freesound search failed: {resp.status_code} {resp.text[:200]}")
                return []
            data = resp.json()
            results = data.get("results", [])
            out: List[SampleInfo] = []
            for r in results:
                sid = str(r.get("id"))
                previews = r.get("previews", {}) or {}
                # Bezpośredni endpoint pobierania
                dl_url = f"https://freesound.org/apiv2/sounds/{sid}/download/"
                out.append(SampleInfo(
                    id=sid,
                    name=r.get("name", sid),
                    url=f"freesound://{sid}",
                    duration=float(r.get("duration", 0.0)),
                    instrument=instrument or "unknown",
                    preview_mp3_url=previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3"),
                    preview_ogg_url=previews.get("preview-hq-ogg") or previews.get("preview-lq-ogg"),
                    download_url=dl_url,
                    source="freesound",
                    origin_url=f"https://freesound.org/s/{sid}/",
                ))
            return out
        except Exception as e:
            print(f"⚠️  Freesound search error: {e}")
            return []

    # --- Diagnostics -----------------------------------------------------------------
    def validate_freesound_token(self) -> Dict[str, str | int | bool]:
        """Proste sprawdzenie poprawności tokena poprzez wywołanie /apiv2/me/.
        Zwraca dict: { ok: bool, status: int, detail: str }
        """
        if not self.freesound_api_key:
            return {"ok": False, "status": 0, "detail": "missing_token"}
        url = "https://freesound.org/apiv2/me/"
        headers = {"Authorization": f"Token {self.freesound_api_key}"}
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return {"ok": True, "status": 200, "detail": "valid"}
            else:
                # cut body to avoid leaking full response
                snippet = r.text[:180].replace('\n', ' ')
                return {"ok": False, "status": r.status_code, "detail": snippet}
        except Exception as e:
            return {"ok": False, "status": -1, "detail": str(e)}

    def get_samples_for_genre(self, genre: str, mood: Optional[str] = None) -> Dict[str, List[SampleInfo]]:
        """Zwraca odpowiednie sample dla gatunku muzycznego, z uwzględnieniem mood (jeśli podany).
        Jeśli dostępny FREESOUND_API_KEY, wykona realne wyszukiwania; w przeciwnym razie zwróci basic fallback.
        """
        # --- Query relaxation & synonyms configuration (progressive broadening) ---
        instrument_synonyms: Dict[str, List[str]] = {
            "drums": ["drum kit", "drum loop", "drum beat", "percussion"],
            "bass": ["bass guitar", "bass note"],
            "piano": ["grand piano", "acoustic piano"],
            "guitar": ["electric guitar", "guitar chord"],
            "saxophone": ["tenor sax", "alto sax"],
            "violin": ["solo violin", "violin sustain"],
            "cello": ["cello sustain"],
            "flute": ["flute sustain"],
            "trumpet": ["solo trumpet", "trumpet sustain"],
            "choir": ["choir ahh", "choir sustain"],
            "synth": ["synth pad", "synth lead"],
            "pad": ["synth pad", "ambient pad"],
            "strings": ["string ensemble", "strings sustain"],
        }

        def build_relaxed_queries(inst: str, base_query: str, biases: List[str], hints: List[str]) -> List[str]:
            # 1. base
            q: List[str] = [base_query]
            # 2. mood biased
            q.extend([f"{b} {base_query}" for b in biases])
            # 3. hints
            q.extend(hints)
            # 4. instrument + wav general
            q.append(f"{inst} wav")
            # 5. synonyms
            for syn in instrument_synonyms.get(inst, []):
                q.append(f"{syn} wav")
            # deduplicate preserving order
            seen = set()
            dedup: List[str] = []
            for item in q:
                if item not in seen:
                    dedup.append(item)
                    seen.add(item)
            return dedup
        # Dodatkowe podpowiedzi per instrument (lepsze frazy)
        inst_query_hints: Dict[str, List[str]] = {
            "trumpet": ["solo trumpet sustain wav", "trumpet long note wav", "trumpet legato wav"],
            "drums": ["drum kit one shot wav", "drum loop wav", "acoustic drums wav"],
            "piano": ["piano sustain wav", "grand piano note wav"],
            "saxophone": ["tenor sax sustain wav", "alto sax solo wav"],
            "guitar": ["electric guitar clean sustain wav", "electric guitar chord wav"],
            "bass": ["bass guitar sustain wav", "upright bass note wav"],
            "violin": ["violin sustain wav", "violin long note wav"],
            "cello": ["cello sustain wav", "cello long note wav"],
            "flute": ["flute sustain wav", "flute long note wav"],
            "trumpet": ["trumpet sustain wav", "trumpet long note wav"],
            "choir": ["choir ahh wav", "choir sustain wav"],
            "synth": ["analog synth pad wav", "synth lead sustain wav"],
        }

        genre_mappings = {
            "ambient": {
                "instruments": ["pad", "strings", "piano"],
                "queries": ["ambient pad", "soft strings", "gentle piano"]
            },
            "jazz": {
                "instruments": ["piano", "bass", "drums", "saxophone"],
                "queries": ["jazz piano", "upright bass", "jazz drums", "smooth sax"]
            },
            "rock": {
                "instruments": ["guitar", "bass", "drums"],
                "queries": ["electric guitar", "rock bass", "rock drums"]
            },
            "techno": {
                "instruments": ["synth", "bass", "drums"],
                "queries": ["techno synth", "electronic bass", "electronic drums"]
            },
            "orchestral": {
                "instruments": ["violin", "cello", "flute", "trumpet"],
                "queries": ["violin sustain", "cello sustain", "flute legato", "trumpet sustain"]
            },
            "lofi": {
                "instruments": ["piano", "bass", "drums"],
                "queries": ["lofi piano", "lofi bass", "lofi drums"]
            },
            "hiphop": {
                "instruments": ["piano", "bass", "drums"],
                "queries": ["hip hop piano", "808 bass", "hip hop drums"]
            },
            "house": {
                "instruments": ["synth", "bass", "drums"],
                "queries": ["house synth stab", "house bass", "house drums loop"]
            },
            "metal": {
                "instruments": ["guitar", "bass", "drums"],
                "queries": ["metal guitar", "metal bass", "metal drums"]
            },
        }

        mapping = genre_mappings.get(genre, genre_mappings["ambient"])
        samples_by_instrument: Dict[str, List[SampleInfo]] = {}

        # Mood bias do fraz
        mood_bias = {
            "calm": ["soft", "gentle", "warm"],
            "energetic": ["punchy", "bright", "driving"],
            "melancholic": ["sad", "dark", "mellow"],
            "joyful": ["happy", "bright", "uplifting"],
            "mysterious": ["mysterious", "eerie", "dark"],
            "epic": ["epic", "orchestral", "powerful"],
            "relaxed": ["relaxed", "chill", "warm"],
            "aggressive": ["aggressive", "hard", "distorted"],
            "dreamy": ["dreamy", "airy", "lush"],
            "groovy": ["groove", "funky", "tight"],
            "romantic": ["romantic", "intimate", "soft"],
        }

        if self.freesound_api_key:
            # Realne wyszukiwania
            biases = mood_bias.get(mood or "", [])
            for inst, base_query in zip(mapping["instruments"], mapping["queries"]):
                hints = inst_query_hints.get(inst, [])
                queries = build_relaxed_queries(inst, base_query, biases, hints)
                candidates: List[SampleInfo] = []
                for q in queries:
                    print(f"[query_attempt] inst={inst} q='{q}'")
                    found = self.search_freesound_samples(q, instrument=inst, page_size=6)
                    if found:
                        print(f"[query_success] inst={inst} q='{q}' count={len(found)}")
                        candidates.extend(found)
                    if len(candidates) >= 6:
                        break
                if candidates:
                    samples_by_instrument[inst] = candidates[:6]
                else:
                    print(f"[query_exhausted] inst={inst} attempts={len(queries)}")
            # Jeśli dla któregoś instrumentu brak, spróbuj Wikimedia Commons jako fallback bez klucza
            for inst in mapping["instruments"]:
                if inst in samples_by_instrument and samples_by_instrument[inst]:
                    continue
                hints = inst_query_hints.get(inst, [])
                base = next((q for i,q in zip(mapping["instruments"], mapping["queries"]) if i==inst), inst)
                # Reuse relaxation (without mood biases here to reduce API calls) + direct hints
                queries = [f"{base} {inst} wav"] + hints + [f"{syn} wav" for syn in instrument_synonyms.get(inst, [])]
                candidates: List[SampleInfo] = []
                for q in queries:
                    print(f"[commons_query_attempt] inst={inst} q='{q}'")
                    found = self.search_commons_samples(q, instrument=inst, page_size=6)
                    if found:
                        print(f"[commons_query_success] inst={inst} q='{q}' count={len(found)}")
                        candidates.extend(found)
                    if len(candidates) >= 6:
                        break
                if candidates:
                    samples_by_instrument[inst] = candidates[:6]
                else:
                    print(f"[commons_query_exhausted] inst={inst} attempts={len(queries)}")
            # Lightweight Commons synonyms-only fallback (ostatnia próba przed błędem w strict mode)
            for inst in mapping["instruments"]:
                if inst in samples_by_instrument and samples_by_instrument[inst]:
                    continue
                syns = instrument_synonyms.get(inst, [])
                if not syns:
                    continue
                candidates: List[SampleInfo] = []
                for syn in syns:
                    q = f"{syn} wav"
                    print(f"[commons_syn_fallback_attempt] inst={inst} q='{q}'")
                    found = self.search_commons_samples(q, instrument=inst, page_size=4)
                    if found:
                        print(f"[commons_syn_fallback_success] inst={inst} q='{q}' count={len(found)}")
                        candidates.extend(found)
                        break  # pierwszy trafiony synonim starczy
                if candidates:
                    samples_by_instrument[inst] = candidates[:4]
                else:
                    print(f"[commons_syn_fallback_exhausted] inst={inst} syns={len(syns)}")
            # Uwaga: nie używamy już synthetic basic jako fallback, kiedy dostępny jest Freesound (zgodnie z prośbą)
        else:
            # Brak klucza do Freesound → spróbuj Wikimedia Commons (bez klucza)
            biases = mood_bias.get(mood or "", [])
            for inst, base_query in zip(mapping["instruments"], mapping["queries"]):
                # commons często ma pliki nazwane nutami/technikami, dokładamy instrument
                queries = [f"{base_query} {inst} wav"] + [f"{b} {base_query} {inst} wav" for b in biases]
                candidates: List[SampleInfo] = []
                for q in queries:
                    found = self.search_commons_samples(q, instrument=inst, page_size=6)
                    if found:
                        candidates.extend(found)
                    if len(candidates) >= 6:
                        break
                if candidates:
                    samples_by_instrument[inst] = candidates[:6]

        # Fallback do basic (i uzupełnienie braków) tylko jeśli Freesound nie jest dostępny
        if not self.freesound_api_key:
            basic_samples = self.get_basic_samples()
            for instrument in mapping["instruments"]:
                if instrument in samples_by_instrument and samples_by_instrument[instrument]:
                    continue
                instrument_samples = [s for s in basic_samples.values() if s.instrument == instrument]
                if instrument_samples:
                    samples_by_instrument[instrument] = instrument_samples

        return samples_by_instrument

    def search_commons_samples(self, query: str, instrument: Optional[str] = None, page_size: int = 10) -> List[SampleInfo]:
        """Wyszukiwanie plików audio na Wikimedia Commons (bez API keya).
        Zwraca bezpośrednie URL-e do oryginalnych plików (WAV/OGG), które można pobrać.
        Uwaga: licencje mogą się różnić (CC BY/SA itd.).
        """
        api = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srnamespace": 6,  # File:
            "srlimit": str(page_size),
        }
        try:
            r = requests.get(api, params=params, timeout=20)
            if r.status_code != 200:
                return []
            data = r.json()
            results = data.get("query", {}).get("search", [])
            titles = [res.get("title") for res in results if res.get("title")]
            out: List[SampleInfo] = []
            if not titles:
                return out

            # Pobierz URL-e oryginalnych plików dla znalezionych tytułów
            info_params = {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "titles": "|".join(titles[:page_size]),
                "iiprop": "url|mime",
            }
            ir = requests.get(api, params=info_params, timeout=20)
            if ir.status_code != 200:
                return out
            idata = ir.json()
            pages = idata.get("query", {}).get("pages", {})
            for _, page in pages.items():
                ii = (page.get("imageinfo") or [])
                if not ii:
                    continue
                info = ii[0]
                url = info.get("url")
                mime = info.get("mime", "")
                if not url or not (mime.startswith("audio/") or url.endswith((".wav", ".ogg", ".mp3"))):
                    continue
                sid = page.get("title", url)
                out.append(SampleInfo(
                    id=sid,
                    name=sid.replace("File:", ""),
                    url=url,
                    duration=3.0,  # brak łatwej długości – szacunkowo
                    instrument=instrument or "unknown",
                    source="commons",
                    origin_url=url,
                ))
            return out
        except Exception:
            return []

    def download_sample(self, sample: SampleInfo, output_dir: str = None) -> str:
        """Pobiera sample do lokalnego pliku.
        Preferuje WAV: dla Freesound pobiera przez endpoint download (wymaga FREESOUND_API_KEY).
        W razie braku, fallback do preview i ewentualna konwersja do WAV (wymaga ffmpeg/pydub).
        Zwraca ścieżkę do .wav lub podnosi wyjątek.
        """
        if output_dir is None:
            output_dir = "output/samples"

        os.makedirs(output_dir, exist_ok=True)

        # Wygenerowane placeholdery
        if sample.url.startswith("generated://"):
            # Dla wygenerowanych sampli, tworzymy placeholder
            file_path = os.path.join(output_dir, f"{sample.id}.wav")
            self._generate_placeholder_audio(sample, file_path)
            return file_path

        # Freesound: spróbuj pobrać oryginalny WAV
        if (sample.source == "freesound" or (isinstance(sample.url, str) and sample.url.startswith("freesound://"))):
            if not self.freesound_api_key:
                raise RuntimeError("FREESOUND_API_KEY not set; cannot download original file")
            dl = sample.download_url or f"https://freesound.org/apiv2/sounds/{sample.id}/download/"
            headers = {"Authorization": f"Token {self.freesound_api_key}"}
            try:
                r = requests.get(dl, headers=headers, stream=True, timeout=60)
                if r.status_code == 200:
                    # Requests zwykle podąża za redirectem i zwraca docelowy strumień
                    file_path = os.path.join(output_dir, f"{sample.id}.wav")
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                f.write(chunk)
                    # szybka weryfikacja pliku > 44 bajty (nagłówek WAV)
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 44:
                        return file_path
                    else:
                        print("⚠️  Freesound download produced small file; trying preview fallback")
                elif r.status_code == 401:
                    print("❌ Freesound download unauthorized (401) – token może być nieprawidłowy lub niewystarczający. Sprawdzam /me ...")
                    diag = self.validate_freesound_token()
                    print(f"[token_diagnostic] ok={diag['ok']} status={diag['status']} detail={diag['detail']}")
                else:
                    print(f"⚠️  Freesound download failed: {r.status_code}")
            except Exception as e:
                print(f"⚠️  Freesound download error: {e}")

            # Preview fallback (mp3/ogg) + konwersja
            preview_url = sample.preview_ogg_url or sample.preview_mp3_url
            if preview_url:
                tmp_path = os.path.join(self.temp_dir, f"{sample.id}_preview")
                try:
                    pr = requests.get(preview_url, stream=True, timeout=30)
                    if pr.status_code == 200:
                        # wykryj rozszerzenie z URL
                        ext = ".ogg" if preview_url.endswith(".ogg") else ".mp3"
                        tmp_file = tmp_path + ext
                        with open(tmp_file, 'wb') as f:
                            for chunk in pr.iter_content(chunk_size=1024 * 64):
                                if chunk:
                                    f.write(chunk)
                        out_wav = os.path.join(output_dir, f"{sample.id}.wav")
                        try:
                            from pydub import AudioSegment
                            seg = AudioSegment.from_file(tmp_file)
                            seg.export(out_wav, format="wav")
                            if os.path.exists(out_wav) and os.path.getsize(out_wav) > 44:
                                return out_wav
                        except Exception as e:
                            print(f"⚠️  Preview conversion failed (pydub/ffmpeg?): {e}")
                except Exception as e:
                    print(f"⚠️  Preview download error: {e}")

            # Jeśli nic nie wyszło, rzuć wyjątek aby adapter mógł zalogować i przejść dalej
            raise RuntimeError("Could not obtain WAV from Freesound (download and preview failed)")

        # Ogólny HTTP download (jeśli mamy bezpośredni URL)
        try:
            response = requests.get(sample.url, stream=True, timeout=30)
            if response.status_code == 200:
                # Wykryj rozszerzenie / MIME
                url_lower = sample.url.lower()
                is_wav = url_lower.endswith(".wav") or response.headers.get("Content-Type", "").startswith("audio/wav")
                is_ogg = url_lower.endswith(".ogg") or response.headers.get("Content-Type", "").startswith("audio/ogg")
                is_mp3 = url_lower.endswith(".mp3") or response.headers.get("Content-Type", "").startswith("audio/mpeg")

                if is_wav:
                    out = os.path.join(output_dir, f"{sample.id}.wav")
                    with open(out, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    return out
                else:
                    # OGG/MP3 → konwersja do WAV jeśli ffmpeg dostępny
                    ext = ".ogg" if is_ogg else ".mp3" if is_mp3 else ".bin"
                    tmp = os.path.join(self.temp_dir, f"{sample.id}{ext}")
                    with open(tmp, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    out_wav = os.path.join(output_dir, f"{sample.id}.wav")
                    try:
                        from pydub import AudioSegment
                        seg = AudioSegment.from_file(tmp)
                        seg.export(out_wav, format="wav")
                        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 44:
                            return out_wav
                    except Exception as e:
                        print(f"⚠️  Direct file conversion failed: {e}")
                    raise RuntimeError("Could not convert remote file to WAV")
        except Exception as e:
            print(f"⚠️  Direct download failed: {e}")

        # Ostatecznie
        raise RuntimeError("download_sample: unsupported source or download failed")

    def _generate_placeholder_audio(self, sample: SampleInfo, file_path: str):
        """Generuje placeholder audio dla testów"""
        try:
            import numpy as np
            from scipy.io.wavfile import write

            sample_rate = 44100
            duration = sample.duration
            t = np.linspace(0, duration, int(sample_rate * duration))

            # Generuj prosty sygnał w zależności od instrumentu
            if sample.instrument == "piano":
                # Prosty ton C4 (261.63 Hz) z harmonicznymi
                frequency = 261.63
                audio = (np.sin(2 * np.pi * frequency * t) * 0.3 +
                         np.sin(2 * np.pi * frequency * 2 * t) * 0.1 +
                         np.sin(2 * np.pi * frequency * 3 * t) * 0.05)
                # Envelope ADSR
                attack = int(0.1 * sample_rate)
                release = int(0.5 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                envelope[-release:] = np.linspace(1, 0, release)
                audio *= envelope

            elif sample.instrument == "strings":
                # Akord (C-E-G)
                freq_c = 261.63
                freq_e = 329.63
                freq_g = 392.00
                audio = (np.sin(2 * np.pi * freq_c * t) * 0.3 +
                         np.sin(2 * np.pi * freq_e * t) * 0.3 +
                         np.sin(2 * np.pi * freq_g * t) * 0.3)

            elif sample.instrument == "pad":
                # Ambient pad z multiple freq
                frequencies = [261.63, 329.63, 392.00, 523.25]  # C4, E4, G4, C5
                audio = np.zeros_like(t)
                for freq in frequencies:
                    audio += np.sin(2 * np.pi * freq * t) * 0.2
                # Slow attack
                attack = int(1.0 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            elif sample.instrument == "bass":
                # Niski sinus (C2 ~ 65.41 Hz) z lekką saturacją
                frequency = 65.41
                audio = np.sin(2 * np.pi * frequency * t) * 0.5
                # Krótki atak i dość krótki release
                attack = int(0.02 * sample_rate)
                release = int(0.15 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                envelope[-release:] = np.linspace(1, 0, release)
                audio *= envelope

            elif sample.instrument == "drums":
                # Prosty zestaw perkusyjny: kick (sinus z expo-decay) + noise (hi-hat)
                kick_freq = 60.0
                kick = np.sin(2 * np.pi * kick_freq * t)
                kick *= np.exp(-t * 12)
                # Szum dla hi-hatu
                rng = np.random.default_rng(42)
                hat = rng.random(len(t)) * 2 - 1
                hat *= (np.sin(2 * np.pi * 12 * t) > 0).astype(float)
                hat *= np.exp(-t * 30)
                audio = (kick * 0.8 + hat * 0.2)

            elif sample.instrument == "guitar":
                # Pluck: mieszanina harmonicznych z szybkim atakiem i krótkim decay (E3 ~ 164.81 Hz)
                f = 164.81
                audio = (np.sin(2 * np.pi * f * t) * 0.5 +
                         np.sin(2 * np.pi * 2 * f * t) * 0.2 +
                         np.sin(2 * np.pi * 3 * f * t) * 0.1)
                attack = int(0.01 * sample_rate)
                release = int(0.3 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                envelope[-release:] = np.linspace(1, 0, release)
                audio *= envelope

            elif sample.instrument == "saxophone":
                # Reedy: dominujące nieparzyste harmoniczne
                f = 261.63
                audio = (np.sin(2 * np.pi * f * t) * 0.4 +
                         np.sin(2 * np.pi * 3 * f * t) * 0.2 +
                         np.sin(2 * np.pi * 5 * f * t) * 0.1)
                attack = int(0.05 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            elif sample.instrument == "synth":
                # Prosty saw-like (sumowanie harmonicznych)
                f = 261.63
                audio = np.zeros_like(t)
                for k in range(1, 8):
                    audio += (1.0 / k) * np.sin(2 * np.pi * k * f * t)
                audio *= 0.3

            elif sample.instrument == "violin":
                f = 196.00  # G3
                audio = (np.sin(2 * np.pi * f * t) * 0.5 +
                         np.sin(2 * np.pi * 2 * f * t) * 0.2)
                attack = int(0.03 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            elif sample.instrument == "cello":
                f = 130.81  # C3
                audio = np.sin(2 * np.pi * f * t) * 0.5
                attack = int(0.03 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            elif sample.instrument == "flute":
                f = 523.25  # C5
                audio = np.sin(2 * np.pi * f * t) * 0.3
                attack = int(0.01 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            elif sample.instrument == "trumpet":
                f = 261.63  # C4
                audio = (np.sin(2 * np.pi * f * t) * 0.4 +
                         np.sin(2 * np.pi * 3 * f * t) * 0.1)
                attack = int(0.02 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            elif sample.instrument == "choir":
                freqs = [261.63, 329.63, 392.00]
                audio = np.zeros_like(t)
                for f in freqs:
                    audio += np.sin(2 * np.pi * f * t) * 0.2
                attack = int(0.2 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            else:
                # Default sine wave
                audio = np.sin(2 * np.pi * 440 * t) * 0.3

            # Normalizuj i zapisz
            audio = np.clip(audio, -1, 1)
            write(file_path, sample_rate, (audio * 32767).astype(np.int16))
            print(f"File size: {os.path.getsize(file_path)} bytes")
            print(f"File exists: {os.path.exists(file_path)}")
            print(f"📄 Generated placeholder audio: {file_path}")

        except ImportError:
            print("⚠️  scipy not available, creating empty file")
            with open(file_path, 'w') as f:
                f.write("# Placeholder audio file")


def test_sample_fetching():
    """Test pobierania sampli"""
    fetcher = SampleFetcher()

    # Test podstawowych sampli
    print("🎵 Testing basic samples...")
    basic_samples = fetcher.get_basic_samples()
    for sample_id, sample in basic_samples.items():
        print(f"  - {sample.name} ({sample.instrument}, {sample.duration}s)")

    # Test sampli dla gatunku
    print("\n🎼 Testing genre-specific samples...")
    ambient_samples = fetcher.get_samples_for_genre("ambient")
    for instrument, samples in ambient_samples.items():
        print(f"  {instrument}: {len(samples)} samples")
        for sample in samples:
            file_path = fetcher.download_sample(sample)
            print(f"    ✅ Downloaded: {file_path}")

    print("\n✅ Sample fetching test completed!")


if __name__ == "__main__":
    test_sample_fetching()