"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import type { ParamPlanMeta } from "../lib/paramTypes";
import type { MidiPlanResult } from "./MidiPlanStep";
import { SampleSelector } from "./SampleSelector";

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
  const [projectName, setProjectName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RenderResult | null>(null);

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
    // Backend exposes audio files under /api/audio/{run_id}/...
    return `${API_BASE}/api/`;
  }, []);

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
        midi: midi.midi,
        tracks,
        selected_samples: selectedSamples,
      };
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/render-audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail?.message || `HTTP ${res.status}`);
      }
      setResult(data as RenderResult);
      if (onRunIdChange && typeof data.run_id === "string") {
        onRunIdChange(data.run_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
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
        setResult(data as RenderResult);
        if (onRunIdChange) onRunIdChange(initialRunId);
      } catch {
        // brak stanu renderu jest akceptowalny
      }
    })();
    return () => { active = false; };
  }, [initialRunId, result, onRunIdChange]);

  return (
    <section className="bg-gray-900/30 border border-purple-700/40 rounded-2xl shadow-lg shadow-purple-900/20 px-6 pt-6 pb-4 space-y-5">
      <h2 className="text-lg font-semibold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400">
        Export MIDI & Render Audio
      </h2>
      <p className="text-xs text-gray-400 max-w-2xl">
        Nazwij projekt, dopasuj poziomy instrumentów i wygeneruj miks razem z osobnymi ścieżkami audio.
      </p>

      {!meta || !midi ? (
        <div className="text-xs text-gray-500 border border-gray-800 rounded-xl p-4">
          Ten krok wymaga ukończonych kroków 1 i 2 (parametry + MIDI).
        </div>
      ) : (
        <>
          <div className="grid md:grid-cols-4 gap-4 items-start">
            <div className="space-y-3 md:col-span-1">
              <div>
                <label className="block text-xs uppercase tracking-widest text-purple-300 mb-1">Nazwa projektu</label>
                <input
                  value={projectName}
                  onChange={e => setProjectName(e.target.value)}
                  placeholder="np. ambient_sunset_v1"
                  className="w-full bg-black/60 border border-purple-800/60 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <button
                onClick={handleRender}
                disabled={!canRender}
                className={`w-full px-3 py-2 rounded-lg text-xs font-semibold mt-2 ${
                  canRender
                    ? "bg-gradient-to-r from-purple-500 to-pink-500 text-black hover:brightness-110"
                    : "bg-black/40 text-gray-500 border border-gray-700 cursor-not-allowed"
                }`}
              >
                {loading ? "Renderowanie…" : "Renderuj mix + ścieżki"}
              </button>
            </div>

            <div className="md:col-span-3 space-y-3 max-h-64 overflow-y-auto scroll-container-purple text-[11px]">
              {tracks.map((t, idx) => (
                <div
                  key={t.instrument || idx}
                  className="border border-purple-800/40 rounded-xl px-3 py-2 bg-black/40 space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-semibold text-purple-200 text-xs">{t.instrument}</div>
                    <label className="flex items-center gap-1 text-[10px] text-gray-300">
                      <input
                        type="checkbox"
                        checked={t.enabled}
                        onChange={e => handleTrackChange(idx, { enabled: e.target.checked })}
                        className="rounded border-purple-700 bg-black"
                      />
                      Włączona
                    </label>
                  </div>
                  <div className="grid grid-cols-3 gap-2 items-center mt-1">
                    <div>
                      <div className="text-[10px] text-gray-400">Głośność (dB)</div>
                      <input
                        type="range"
                        min={-24}
                        max={6}
                        step={1}
                        value={t.volume_db}
                        onChange={e => handleTrackChange(idx, { volume_db: Number(e.target.value) })}
                        className="w-full"
                      />
                      <div className="text-[10px] text-gray-300">{t.volume_db.toFixed(0)} dB</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-gray-400">Pan</div>
                      <input
                        type="range"
                        min={-1}
                        max={1}
                        step={0.1}
                        value={t.pan}
                        onChange={e => handleTrackChange(idx, { pan: Number(e.target.value) })}
                        className="w-full"
                      />
                      <div className="text-[10px] text-gray-300">
                        {t.pan < 0 ? `L ${Math.abs(t.pan).toFixed(1)}` : t.pan > 0 ? `R ${t.pan.toFixed(1)}` : "Center"}
                      </div>
                    </div>
                    <div>
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
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-xs rounded-xl px-3 py-2">
              {error}
            </div>
          )}

          {result && (
            <div className="bg-black/40 border border-purple-800/50 rounded-2xl p-4 space-y-3 text-xs">
              <div className="text-purple-300 text-[11px] uppercase tracking-widest mb-1">
                Wynik renderu
              </div>
              <div className="space-y-1 text-gray-200">
                <div>
                  <span className="text-gray-400">Mix:</span>{" "}
                  <a
                    href={`${backendAudioBase}${result.mix_wav_rel}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-purple-300 underline"
                  >
                    pobierz / odsłuchaj
                  </a>
                </div>
                <div className="mt-1 text-gray-400">Stemy:</div>
                <ul className="pl-4 list-disc space-y-0.5">
                  {result.stems.map(stem => (
                    <li key={stem.instrument}>
                      <span className="text-gray-300 mr-1">{stem.instrument}:</span>
                      <a
                        href={`${backendAudioBase}${stem.audio_rel}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-purple-300 underline"
                      >
                        audio
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
