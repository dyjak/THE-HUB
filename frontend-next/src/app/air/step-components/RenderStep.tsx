"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import type { ParamPlanMeta } from "../lib/paramTypes";
import type { MidiPlanResult } from "./MidiPlanStep";
import { SampleSelector } from "./SampleSelector";
import { SimpleAudioPlayer } from "./SimpleAudioPlayer";
import { VisualAudioPlayer } from "./VisualAudioPlayer";
import ElectricBorder from "@/components/ui/ElectricBorder";
import LoadingOverlay from "@/components/ui/LoadingOverlay";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
const MODULE_PREFIX = "/air/render";

export type RenderResult = {
  project_name: string;
  run_id: string;
  mix_wav_rel: string;
  stems: { instrument: string; audio_rel: string }[];
  sample_rate: number;
  duration_seconds?: number | null;
};

type Props = {
  meta: ParamPlanMeta | null;
  midi: MidiPlanResult | null;
  selectedSamples: Record<string, string | undefined>;
  // run_id z backendu dla kroku renderu (zwykle ten sam co z MIDI)
  initialRunId?: string | null;
  onRunIdChange?: (runId: string | null) => void;
  // Opcjonalne powiadomienie rodzica o zmianie wyboru sampli w kroku render
  onSelectedSamplesChange?: (next: Record<string, string | undefined>) => void;
};

export default function RenderStep({ meta, midi, selectedSamples, initialRunId, onRunIdChange, onSelectedSamplesChange }: Props) {
  const { data: session } = useSession();
  const [projectName, setProjectName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RenderResult | null>(null);
  const [history, setHistory] = useState<RenderResult[]>([]);
  const [fadeoutMs, setFadeoutMs] = useState(10);
  const [recommending, setRecommending] = useState(false);

  const [tracks, setTracks] = useState(() => {
    const instruments = meta?.instruments || [];
    return instruments.map((name, idx) => ({
      instrument: name,
      enabled: true,
      volume_db: idx === 0 ? 0 : -3,
      pan: 0,
    }));
  });

  const canRender = !!meta && !!midi && !loading && !!projectName.trim();

  const backendAudioBase = useMemo(() => {
    // Backend: app.mount("/api/audio", StaticFiles(directory=render_output))
    // => pliki siedzą w: output/<run_id>/<file>, URL: /api/audio/<run_id>/<file>
    return `${API_BASE}/api/audio/`;
  }, []);

  const resolveRenderUrl = useCallback(
    (rel: string) => {
      if (!rel) return backendAudioBase;

      const marker = "output\\";
      const idx = rel.indexOf(marker);
      const tail = idx >= 0 ? rel.slice(idx + marker.length) : rel;

      const finalUrl = `${backendAudioBase}${tail}`;
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.log("[RenderStep] resolveRenderUrl", { rel, tail, finalUrl });
      }
      return finalUrl;
    },
    [backendAudioBase],
  );

  // Resolve MIDI file URL from midi artifacts
  const resolveMidiUrl = useCallback(
    (rel: string | null | undefined) => {
      if (!rel) return null;
      // MIDI files are also served from /api/audio/ endpoint
      // Handle both forward slashes and backslashes
      const markerBack = "output\\";
      const markerFwd = "output/";
      let idx = rel.indexOf(markerBack);
      let marker = markerBack;
      if (idx < 0) {
        idx = rel.indexOf(markerFwd);
        marker = markerFwd;
      }
      const tail = idx >= 0 ? rel.slice(idx + marker.length) : rel;
      // Normalize path separators to forward slashes for URL
      const normalizedTail = tail.replace(/\\/g, '/');
      const finalUrl = `${backendAudioBase}${normalizedTail}`;
      if (process.env.NODE_ENV === "development") {
        console.log("[RenderStep] resolveMidiUrl", { rel, tail: normalizedTail, finalUrl });
      }
      return finalUrl;
    },
    [backendAudioBase],
  );

  // Download a single file - returns true on success, false on failure
  const downloadFile = useCallback(async (url: string, filename: string, silentOn404 = false): Promise<boolean> => {
    try {
      if (process.env.NODE_ENV === "development") {
        console.log("[RenderStep] downloadFile attempting:", { url, filename });
      }
      const response = await fetch(url);
      if (!response.ok) {
        if (response.status === 404 && silentOn404) {
          console.warn(`[RenderStep] File not found (404), skipping: ${url}`);
          return false;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
      return true;
    } catch (e) {
      console.error('Download failed:', e);
      setError(`Błąd pobierania ${filename}: ${e instanceof Error ? e.message : String(e)}`);
      return false;
    }
  }, []);

  // Download all files (mix, stems, and midi)
  const downloadAll = useCallback(async (h: RenderResult) => {
    const projectNameClean = h.project_name.replace(/[^a-zA-Z0-9_-]/g, '_');
    setError(null); // Clear any previous errors

    // Download mix
    const mixUrl = resolveRenderUrl(h.mix_wav_rel);
    await downloadFile(mixUrl, `${projectNameClean}_mix.wav`);

    // Download stems
    for (const stem of h.stems) {
      const stemUrl = resolveRenderUrl(stem.audio_rel);
      const instrumentClean = stem.instrument.replace(/[^a-zA-Z0-9_-]/g, '_');
      await downloadFile(stemUrl, `${projectNameClean}_${instrumentClean}.wav`);
    }

    // Download MIDI files if available - silently skip if 404
    if (midi?.artifacts?.midi_mid_rel) {
      const midiUrl = resolveMidiUrl(midi.artifacts.midi_mid_rel);
      if (midiUrl) {
        await downloadFile(midiUrl, `${projectNameClean}.mid`, true);
      }
    }
  }, [resolveRenderUrl, resolveMidiUrl, downloadFile, midi]);

  const handleTrackChange = (index: number, patch: Partial<(typeof tracks)[number]>) => {
    setTracks(prev => prev.map((t, i) => (i === index ? { ...t, ...patch } : t)));
  };

  const handleSampleChange = useCallback(
    (instrument: string, sampleId: string | null) => {
      const next: Record<string, string | undefined> = { ...selectedSamples };
      if (!sampleId) {
        delete next[instrument];
      } else {
        next[instrument] = sampleId;
      }
      if (onSelectedSamplesChange) {
        onSelectedSamplesChange(next);
      }
    },
    [selectedSamples, onSelectedSamplesChange],
  );

  const handleRender = async () => {
    if (!meta || !midi || !projectName.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = {
        project_name: projectName.trim(),
        run_id: midi.run_id,
        user_id: session?.user && (session.user as any).id ? Number((session.user as any).id) : null,
        midi: midi.midi,
        tracks,
        selected_samples: selectedSamples,
        // Umożliwiamy delikatne dostrojenie długości fade-outu poprzedniej
        // nuty w ramach jednego instrumentu. Backend oczekuje sekund.
        fadeout_seconds: Math.max(0, Math.min(100, fadeoutMs)) / 1000,
      };
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/render-audio`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail?.message || `HTTP ${res.status}`);
      }
      const rr = data as RenderResult;
      setResult(rr);
      setHistory(prev => [...prev, rr]);
      if (onRunIdChange && typeof rr.run_id === "string") {
        onRunIdChange(rr.run_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleRecommendSamples = async () => {
    if (!meta || !midi) return;
    setRecommending(true);
    setError(null);
    try {
      const body = {
        project_name: projectName.trim() || meta.style || "air_demo",
        run_id: midi.run_id,
        midi: midi.midi,
        // midi_per_instrument removed as it's not in MidiPlanResult type
        tracks,
        selected_samples: selectedSamples,
        fadeout_seconds: Math.max(0, Math.min(100, fadeoutMs)) / 1000,
      };

      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/recommend-samples`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail?.message || `HTTP ${res.status}`);
      }

      const recommended = (data?.recommended_samples || {}) as Record<
        string,
        { instrument: string; sample_id: string }
      >;

      // Zbuduj mapę instrument -> sample_id
      const merged: Record<string, string | undefined> = { ...selectedSamples };
      for (const [inst, rec] of Object.entries(recommended)) {
        if (rec?.sample_id) {
          merged[inst] = rec.sample_id;
        }
      }

      if (onSelectedSamplesChange) {
        onSelectedSamplesChange(merged);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRecommending(false);
    }
  };

  // Przy initialRunId spróbujmy odczytać ostatni stan renderu
  useEffect(() => {
    if (!initialRunId || result) return;
    let active = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/run/${encodeURIComponent(initialRunId)}`);
        if (!res.ok) return;
        const data: any = await res.json().catch(() => null);
        if (!active || !data) return;
        const rr = data as RenderResult;
        setResult(rr);
        setHistory(prev => {
          const exists = prev.some(h => h.run_id === rr.run_id && h.mix_wav_rel === rr.mix_wav_rel);
          return exists ? prev : [...prev, rr];
        });
        if (onRunIdChange) onRunIdChange(initialRunId);
      } catch {
        // brak stanu renderu jest akceptowalny
      }
    })();
    return () => { active = false; };
  }, [initialRunId, result, onRunIdChange]);

  return (
    <section className="bg-gray-900/40 border border-emerald-700/40 rounded-2xl shadow-lg shadow-emerald-900/10 px-6 pt-6 pb-4 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-3xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-emerald-100 to-green-600 animate-pulse">
          Krok 3 • Export & Render
        </h2>
      </div>
      <p className="text-xs text-gray-400 max-w-2xl">
        Nazwij projekt, dopasuj poziomy instrumentów i wygeneruj <span className="text-emerald-300">miks audio</span> razem z osobnymi ścieżkami (stems).
      </p>

      {!meta || !midi ? (
        <div className="text-xs text-gray-500 border border-gray-800/50 rounded-xl p-4 bg-black/30 text-center">
          Ten krok wymaga ukończonych kroków 1 i 2 (parametry + MIDI).
        </div>
      ) : (
        <div className="space-y-6">

          {/* 1. Recommend Samples */}
          <div className="flex flex-col sm:flex-row gap-4 items-start bg-black/80 p-5 rounded-xl border border-emerald-900/40">
            <button
              type="button"
              onClick={handleRecommendSamples}
              disabled={!meta || !midi || recommending}
              className={`flex-1 px-4 py-5 rounded-lg text-ss font-semibold transition-all duration-300 border ${!meta || !midi || recommending
                ? "bg-black/40 text-gray-500 border-gray-700 cursor-not-allowed"
                : "bg-white/10 text-emerald-100 border-emerald-600/50 hover:bg-emerald-900/40 hover:border-emerald-500 hover:shadow-lg hover:shadow-emerald-900/20"
                }`}
            >
              {recommending ? "Dobieranie sampli…" : "Dobierz rekomendowane sample"}
            </button>
            <div className="flex-1 flex gap-3 items-start text-[14px] text-gray-400 bg-black/40 p-3 rounded-lg border border-emerald-900/80">
              <div className="text-emerald-500 mt-0.5">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-6 h-6 scale-120">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM8.94 6.94a.75.75 0 11-1.061-1.061 3 3 0 112.871 5.026v.345a.75.75 0 01-1.5 0v-.5c0-.72.57-1.172 1.081-1.287A1.5 1.5 0 108.94 6.94zM10 15a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
              </div>
              <p>
                Algorytm wyliczy zrównoważoną proporcję oktaw na których grają poszczególne instrumenty na ścieżce MIDI i odpowiednio dobierze sample biorąc pod uwagę ich bazową skalę.
              </p>
            </div>
          </div>

          {/* 2. Track Configuration */}
          <div className="space-y-3">
            <div className="space-y-2 max-h-[500px] overflow-y-auto scroll-container-emerald pr-2 border border-emerald-500/30 rounded-2xl p-4 bg-black/40">
              <label className="block text-xs uppercase tracking-widest text-emerald-300 mb-1 pl-1">Konfiguracja ścieżek</label>

              {tracks.map((t, idx) => (
                <div
                  key={t.instrument || idx}
                  className="border border-emerald-800/30 rounded-xl px-4 py-3 bg-black/40 hover:bg-black/50 transition-colors grid grid-cols-1 sm:grid-cols-12 gap-6 items-center"
                >
                  {/* Left: Instrument Name + Dot Checkbox */}
                  <div className="sm:col-span-3 flex items-center justify-center gap-3">
                    <button
                      type="button"
                      onClick={() => handleTrackChange(idx, { enabled: !t.enabled })}
                      className={`w-4 h-4 rounded-full shadow-md transition-all duration-300 ${t.enabled ? 'bg-emerald-500 shadow-emerald-500/50 scale-110' : 'bg-red-500/50 shadow-red-500/30 scale-90 hover:bg-red-500 hover:scale-100'}`}
                      title={t.enabled ? "Wyłącz ścieżkę" : "Włącz ścieżkę"}
                    />
                    <div className={`font-semibold text-sm transition-colors ${t.enabled ? 'text-emerald-200' : 'text-gray-500'}`}>
                      {t.instrument}
                    </div>
                  </div>

                  {/* Middle: Volume and Pan Sliders Stacked */}
                  <div className="sm:col-span-5 flex flex-col gap-2">
                    {/* Volume */}
                    <div className="flex items-center gap-2 text-[11px] text-gray-400">
                      <span className="w-6 shrink-0">Vol</span>
                      <input
                        type="range"
                        min={-24}
                        max={6}
                        step={1}
                        value={t.volume_db}
                        onChange={e => handleTrackChange(idx, { volume_db: Number(e.target.value) })}
                        disabled={!t.enabled}
                        className={`flex-1 h-1.5 rounded-lg appearance-none cursor-pointer ${t.enabled ? 'accent-emerald-500 bg-gray-700 hover:bg-gray-600' : 'accent-gray-600 bg-gray-800 cursor-not-allowed'}`}
                      />
                      <span className="w-12 text-right text-gray-300 font-mono shrink-0">{t.volume_db > 0 ? `+${t.volume_db}` : t.volume_db} dB</span>
                    </div>
                    {/* Pan */}
                    <div className="flex items-center gap-2 text-[11px] text-gray-400">
                      <span className="w-6 shrink-0">Pan</span>
                      <input
                        type="range"
                        min={-1}
                        max={1}
                        step={0.1}
                        value={t.pan}
                        onChange={e => handleTrackChange(idx, { pan: Number(e.target.value) })}
                        disabled={!t.enabled}
                        className={`flex-2 h-1 rounded-lg appearance-none cursor-pointer ${t.enabled ? 'accent-emerald-500 bg-gray-700 hover:bg-gray-600' : 'accent-gray-600 bg-gray-800 cursor-not-allowed'}`}
                      />
                      <span className="w-10 text-right text-gray-300 font-mono shrink-0">
                        {t.pan < 0 ? `L${Math.abs(t.pan).toFixed(1)}` : t.pan > 0 ? `R${t.pan.toFixed(1)}` : "Center"}
                      </span>
                    </div>
                  </div>

                  {/* Right: Sample Selector */}
                  <div className="sm:col-span-4">
                    <div className="text-[9px] text-gray-400 mb-1">Sample</div>
                    <SampleSelector
                      apiBase={API_BASE}
                      apiPrefix={API_PREFIX}
                      modulePrefix={"/air/param-generation"}
                      instrument={t.instrument}
                      selectedId={selectedSamples[t.instrument] || null}
                      onChange={handleSampleChange}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 3. Fade-out */}
          <div className="flex flex-col sm:flex-row gap-10 items-start bg-black/20 p-4 rounded-xl border border-emerald-900/20">
            <div className="flex-1 space-y-2 w-full">
              <div className="flex items-center justify-between gap-2">
                <label className="text-[10px] uppercase tracking-widest text-emerald-300">Fade-out (ms)</label>
                <span className="text-[12px] text-gray-400 font-mono">{fadeoutMs.toFixed(0)} ms</span>
              </div>
              <input
                type="range"
                min={0}
                max={30}
                step={1}
                value={fadeoutMs}
                onChange={e => setFadeoutMs(Number(e.target.value))}
                className="w-full scale-y-120 accent-emerald-500 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer hover:bg-gray-600 transition-colors"
              />
            </div>
            <div className="flex-1 flex justify-center gap-3 items-start text-[12px] text-gray-400 bg-black/40 p-3 rounded-lg border border-emerald-900/80 h-full">
              <div className="text-emerald-500 mt-0.5">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 scale-150">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM8.94 6.94a.75.75 0 11-1.061-1.061 3 3 0 112.871 5.026v.345a.75.75 0 01-1.5 0v-.5c0-.72.57-1.172 1.081-1.287A1.5 1.5 0 108.94 6.94zM10 15a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
              </div>
              <p>
                Zapobiega nakładaniu się grających sampli na siebie. 0 ms = twarde ucięcie, 10 ms = gładki fade-out.
              </p>
            </div>
          </div>

          {/* 4. Project Name */}
          <div className="flex flex-col items-center gap-2">
            <label className="block text-l uppercase tracking-widest bg-clip-text text-transparent bg-gradient-to-r from-emerald-200 via-green-400 to-emerald-200 animate-pulse font-bold">
              Nazwij swój projekt
            </label>
            <input
              value={projectName}
              onChange={e => setProjectName(e.target.value)}
              placeholder="np. ambient_sunset_v1"
              className="w-full max-w-6xl bg-black/50 border border-emerald-800/40 rounded-2xl px-6 py-6 text-2xl text-center focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:border-emerald-500 transition-all placeholder-gray-700 shadow-inner shadow-black/50"
            />
          </div>

          {/* 5. Render Button */}
          <div>
            <ElectricBorder
              as="button"
              onClick={handleRender}
              disabled={!canRender}
              className={`w-full py-4 text-base font-bold text-white bg-black/50 rounded-xl transition-all duration-300 ${!canRender ? 'opacity-30 cursor-not-allowed scale-[0.98] grayscale' : 'scale-[0.98] hover:scale-100 hover:brightness-125 hover:bg-black/70 hover:shadow-lg hover:shadow-emerald-400/20'}`}
              color="#10b981"
              speed={0.1}
              chaos={0.3}
            >
              {loading ? (
                'Renderowanie…'
              ) : (
                <span className="flex items-center justify-center gap-2">
                  Renderuj mix
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                    <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" />
                    <path fillRule="evenodd" d="M1.323 11.447C2.811 6.976 7.028 3.75 12.001 3.75c4.97 0 9.185 3.223 10.675 7.69.12.362.12.752 0 1.113-1.487 4.471-5.705 7.697-10.677 7.697-4.97 0-9.186-3.223-10.675-7.69a1.762 1.762 0 010-1.113zM17.25 12a5.25 5.25 0 11-10.5 0 5.25 5.25 0 0110.5 0z" clipRule="evenodd" />
                  </svg>
                </span>
              )}
            </ElectricBorder>
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-xs rounded-xl px-4 py-3">
              {error}
            </div>
          )}

          {history.length > 0 && (
            <div className="bg-black/40 border border-emerald-800/40 rounded-2xl p-5 space-y-4 text-xs mt-4">
              <div className="text-emerald-300 text-xs uppercase tracking-widest border-b border-emerald-900/40 pb-2">
                Historia renderów
              </div>
              <div className="space-y-3 text-gray-200 max-h-80 overflow-y-auto pr-2 scroll-container-emerald">
                {[...history].reverse().map((h, idx) => {
                  const versionLabel = `Wersja ${history.length - idx}`;
                  return (
                    <div
                      key={`${h.run_id}-${h.mix_wav_rel}-${idx}`}
                      className="border border-emerald-800/30 rounded-xl px-4 py-3 bg-black/30 space-y-3 hover:bg-black/40 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-3">
                          <div className="font-semibold text-emerald-200 text-sm">
                            {versionLabel}
                          </div>
                          {typeof h.duration_seconds === "number" && h.duration_seconds > 0 && (
                            <div className="text-[10px] text-gray-400 bg-black/40 px-2 py-1 rounded-full border border-gray-800">
                              {h.duration_seconds.toFixed(1)} s
                            </div>
                          )}
                        </div>
                        {/* Download buttons */}
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => downloadFile(resolveRenderUrl(h.mix_wav_rel), `${h.project_name.replace(/[^a-zA-Z0-9_-]/g, '_')}_mix.wav`)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-emerald-300 bg-emerald-900/30 hover:bg-emerald-800/40 border border-emerald-700/40 hover:border-emerald-600/60 rounded-lg transition-all duration-200 hover:scale-105"
                            title="Pobierz tylko mix audio"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                              <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                              <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
                            </svg>
                            Mix
                          </button>
                          <button
                            type="button"
                            onClick={() => downloadAll(h)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-white bg-gradient-to-r from-emerald-600/60 to-green-600/60 hover:from-emerald-500/70 hover:to-green-500/70 border border-emerald-500/40 hover:border-emerald-400/60 rounded-lg transition-all duration-200 hover:scale-105 shadow-sm shadow-emerald-900/20"
                            title="Pobierz wszystko: mix, stems i MIDI"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                              <path fillRule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm0 10.5a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75zM2 10a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5h-7.5A.75.75 0 012 10z" clipRule="evenodd" />
                            </svg>
                            Wszystko
                          </button>
                        </div>
                      </div>
                      <div className="px-2 py-3 bg-emerald-900/20 rounded-lg">
                        <VisualAudioPlayer
                          src={resolveRenderUrl(h.mix_wav_rel)}
                          title={h.project_name || "Mix"}
                          accentColor="#55ff6fff"
                          accentColor2="#005f31ff"
                          className="w-full"
                        />
                      </div>
                      {h.stems.length > 0 && (
                        <details className="group">
                          <summary className="cursor-pointer text-[10px] text-emerald-400/70 hover:text-emerald-300 transition-colors py-1 select-none">
                            Pokaż {h.stems.length} osobnych ścieżek (stems)
                          </summary>
                          <ul className="pl-2 space-y-2 mt-2 border-l border-emerald-900/30 ml-1">
                            {h.stems.map(stem => (
                              <li key={`${stem.instrument}-${stem.audio_rel}`} className="space-y-1">
                                <div className="text-[10px] text-gray-300 font-medium">{stem.instrument}</div>
                                <SimpleAudioPlayer
                                  src={resolveRenderUrl(stem.audio_rel)}
                                  className="w-full"
                                  height={32}
                                  variant="compact"
                                />
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Loading overlay */}
      <LoadingOverlay
        isVisible={loading}
        message="Renderuję Twój utwór... To już akurat potrwa bardzo niedługo!"
      />
    </section>
  );
}
