"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import type { ParamPlanMeta } from "../lib/paramTypes";
import type { MidiPlanResult } from "./MidiPlanStep";
import { SampleSelector } from "./SampleSelector";
import { SimpleAudioPlayer } from "./SimpleAudioPlayer";

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
        midi_per_instrument: midi.midi_per_instrument ?? undefined,
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

      // Zapisz do parameter_plan.json przez PATCH selected-samples,
      // jeśli mamy run_id z kroku parametrów.
      if (meta.run_id) {
        try {
          await fetch(
            `${API_BASE}${API_PREFIX}/air/param-generation/plan/${encodeURIComponent(
              meta.run_id,
            )}/selected-samples`,
            {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ selected_samples: merged }),
            },
          );
        } catch {
          // zapis do param-plan nie jest krytyczny dla UX renderu
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
                type="button"
                onClick={handleRecommendSamples}
                disabled={!meta || !midi || recommending}
                className={`w-full px-3 py-2 rounded-lg text-xs font-semibold mt-3 ${
                  !meta || !midi || recommending
                    ? "bg-black/40 text-gray-500 border border-gray-700 cursor-not-allowed"
                    : "bg-gradient-to-r from-emerald-500 to-teal-500 text-black hover:brightness-110"
                }`}
              >
                {recommending ? "Dobieranie sampli…" : "Dobierz rekomendowane sample"}
              </button>
              <div className="space-y-1 mt-2">
                <div className="flex items-center justify-between gap-2">
                  <label className="text-[10px] uppercase tracking-widest text-purple-300">Fade-out (ms)</label>
                  <span className="text-[10px] text-gray-400">{fadeoutMs.toFixed(0)} ms</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={30}
                  step={1}
                  value={fadeoutMs}
                  onChange={e => setFadeoutMs(Number(e.target.value))}
                  className="w-full"
                />
                <p className="text-[10px] text-gray-500">
                  0 ms = twarde ucięcie, 10 ms (domyślnie) = krótki, gładki fade-out.
                </p>
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

          {history.length > 0 && (
            <div className="bg-black/40 border border-purple-800/50 rounded-2xl p-4 space-y-3 text-xs">
              <div className="text-purple-300 text-[11px] uppercase tracking-widest mb-1">
                Historia renderów
              </div>
              <div className="space-y-3 text-gray-200 max-h-64 overflow-y-auto pr-1">
                {[...history].map((h, idx) => {
                  const versionLabel = `Wersja ${idx + 1}`;
                  return (
                    <div
                      key={`${h.run_id}-${h.mix_wav_rel}-${idx}`}
                      className="border border-purple-800/40 rounded-xl px-3 py-2 bg-black/40 space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-semibold text-purple-200 text-[11px]">
                          {versionLabel}
                        </div>
                        {typeof h.duration_seconds === "number" && h.duration_seconds > 0 && (
                          <div className="text-[10px] text-gray-400">
                            {h.duration_seconds.toFixed(1)} s
                          </div>
                        )}
                      </div>
                      <div className="space-y-1">
                        <div className="text-[11px] text-gray-300 mb-1">Mix</div>
                        <SimpleAudioPlayer
                          src={resolveRenderUrl(h.mix_wav_rel)}
                          className="w-full"
                          height={36}
                          variant="compact"
                        />
                      </div>
                      {h.stems.length > 0 && (
                        <div className="space-y-1">
                          <div className="mt-1 text-gray-400 text-[11px]">Stemy</div>
                          <ul className="pl-3 space-y-1">
                            {h.stems.map(stem => (
                              <li key={`${stem.instrument}-${stem.audio_rel}`} className="space-y-0.5">
                                <div className="text-[11px] text-gray-300">{stem.instrument}</div>
                                <SimpleAudioPlayer
                                  src={resolveRenderUrl(stem.audio_rel)}
                                  className="w-full"
                                  height={32}
                                  variant="compact"
                                />
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
