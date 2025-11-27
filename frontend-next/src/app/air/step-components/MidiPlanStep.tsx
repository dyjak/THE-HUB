"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ParamPlanMeta } from "../lib/paramTypes";
import MidiPianoroll from "./MidiPianoroll";
import ElectricBorder from "@/components/ui/ElectricBorder";
import LoadingOverlay from "@/components/ui/LoadingOverlay";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
const MODULE_PREFIX = "/air/midi-generation";
const PROVIDERS_URL = `${API_BASE}/api/air/param-generation/providers`;
const MODELS_URL = (p: string) => `${API_BASE}/api/air/param-generation/models/${encodeURIComponent(p)}`;

export type MidiPlanResult = {
  run_id: string;
  midi: any;
  artifacts: {
    midi_json_rel?: string | null;
    midi_mid_rel?: string | null;
    midi_image_rel?: string | null;
  };
  provider?: string | null;
  model?: string | null;
  errors?: string[] | null;
};

type Props = {
  meta: ParamPlanMeta | null;
  onReady?: (result: MidiPlanResult) => void;
};

export default function MidiPlanStep({ meta, onReady }: Props) {
  const pianorollScrollRef = useRef<HTMLDivElement | null>(null);
  const [providers, setProviders] = useState<{ id: string; name: string; default_model?: string }[]>([]);
  const [provider, setProvider] = useState<string>("gemini");
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MidiPlanResult | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);
  const [userPrompt, setUserPrompt] = useState<string | null>(null);
  const [normalized, setNormalized] = useState<any | null>(null);
  const [rawText, setRawText] = useState<string | null>(null);

  const pretty = useCallback((v: unknown) => {
    try { return JSON.stringify(v, null, 2); } catch { return String(v); }
  }, []);

  // Fetch providers
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await fetch(PROVIDERS_URL);
        if (!res.ok) return;
        const data = await res.json();
        const list = Array.isArray(data?.providers) ? (data.providers as { id: string; name: string; default_model?: string }[]) : [];
        if (!mounted) return;
        setProviders(list);
        const gem = list.find(p => (p.id || "").toLowerCase() === "gemini");
        const first = list[0];
        const chosen = gem || first;
        if (chosen) {
          setProvider(prev => prev || chosen.id);
          setModel(prev => prev || (chosen.default_model || ""));
        }
      } catch { }
    })();
    return () => { mounted = false; };
  }, []);

  // Fetch models
  useEffect(() => {
    let mounted = true;
    if (!provider) { setModels([]); return; }
    (async () => {
      try {
        const res = await fetch(MODELS_URL(provider));
        if (!res.ok) { if (mounted) setModels([]); return; }
        const data = await res.json();
        const list = Array.isArray(data?.models) ? (data.models as string[]) : [];
        const uniq = Array.from(new Set(list.filter(m => typeof m === "string" && m.trim())));
        if (!mounted) return;
        setModels(uniq);
        if (uniq.length > 0) setModel(prev => (prev && uniq.includes(prev) ? prev : uniq[0]));
      } catch {
        if (mounted) setModels([]);
      }
    })();
    return () => { mounted = false; };
  }, [provider]);

  const canRun = !!meta && !loading;

  const handleRun = async () => {
    if (!meta || loading) return;
    setLoading(true);
    setError(null);
    try {
      const body: any = { meta, provider, model: model || null };
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/compose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data: any = await res.json();
      setResult(data as MidiPlanResult);
      setSystemPrompt(typeof data.system === "string" ? data.system : null);
      setUserPrompt(typeof data.user === "string" ? data.user : null);
      setRawText(typeof data.raw === "string" ? data.raw : null);
      const parsed = data.parsed ?? null;
      setNormalized(parsed ?? null);
      if (onReady) onReady(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-gray-900/30 border border-orange-700/30 rounded-2xl shadow-lg shadow-orange-900/10 px-6 pt-6 pb-4 space-y-5">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-3xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-orange-100 to-amber-600 animate-pulse">Krok 2 • Plan MIDI</h2>
      </div>
      <p className="text-xs text-gray-400 max-w-2xl">
        Ten krok używa wygenerowanych parametrów, aby stworzyć <span className="text-orange-300">szczegółowy pattern MIDI</span>. Wynik
        służy jako baza do eksportu pliku .mid i dalszego renderu audio.
      </p>

      {/* Provider + model */}
      <div className="grid md:grid-cols-4 gap-4 items-start">
        <div className="space-y-3 md:col-span-1">
          <div>
            <label className="block text-xs uppercase tracking-widest text-orange-300 mb-1">Provider</label>
            <div className="relative">
              <select
                value={provider}
                onChange={e => setProvider(e.target.value)}
                className="appearance-none w-full bg-black/50 border border-orange-800/40 rounded-lg pr-9 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-orange-500"
              >
                {providers.map(p => (
                  <option
                    key={p.id}
                    value={p.id}
                    disabled={(p.id || "").toLowerCase() === "openai"}
                  >
                    {p.name}{(p.id || "").toLowerCase() === "openai" ? " (disabled)" : ""}
                  </option>
                ))}
              </select>
              <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orange-300 opacity-70" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
          <div>
            <label className="block text-xs uppercase tracking-widest text-orange-300 mb-1">Model</label>
            {models.length > 0 ? (
              <div className="relative">
                <select
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  className="appearance-none w-full bg-black/50 border border-orange-800/40 rounded-lg pr-9 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-orange-500"
                >
                  {models.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <svg
                  className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orange-300 opacity-70"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            ) : (
              <input
                value={model}
                onChange={e => setModel(e.target.value)}
                placeholder="np. gemini-2.5-flash"
                className="w-full bg-black/50 border border-orange-800/40 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-orange-500"
              />
            )}
          </div>
        </div>

        {/* Podgląd meta (read-only, stały panel ze scrollem) */}
        <div className="md:col-span-3 ">
          <label className="block text-xs uppercase tracking-widest text-orange-300 mb-1">Parametry wejściowe (read-only)</label>
          {meta ? (
            <div className="space-y-1">
              <div
                className="relative text-[11px] bg-black/40 border border-orange-800/30 rounded-xl px-4 py-3 space-y-0.5 max-h-52 overflow-y-auto scroll-container-orange"
              >
                <div className="grid sm:grid-cols-3 gap-x-4 gap-y-1">
                  <div><span className="text-gray-400">Style:</span> <span className="text-gray-100">{meta.style}</span></div>
                  <div><span className="text-gray-400">Mood:</span> <span className="text-gray-100">{meta.mood}</span></div>
                  <div><span className="text-gray-400">Tempo:</span> <span className="text-gray-100">{meta.tempo}</span></div>
                  <div><span className="text-gray-400">Key:</span> <span className="text-gray-100">{meta.key}</span></div>
                  <div><span className="text-gray-400">Scale:</span> <span className="text-gray-100">{meta.scale}</span></div>
                  <div><span className="text-gray-400">Meter:</span> <span className="text-gray-100">{meta.meter}</span></div>
                  <div><span className="text-gray-400">Bars:</span> <span className="text-gray-100">{meta.bars}</span></div>
                  <div><span className="text-gray-400">Length seconds:</span> <span className="text-gray-100">{meta.length_seconds}</span></div>
                </div>
                <div className="mt-1"><span className="text-gray-400">Dynamic profile:</span> <span className="text-gray-100">{meta.dynamic_profile}</span></div>
                <div><span className="text-gray-400">Arrangement density:</span> <span className="text-gray-100">{meta.arrangement_density}</span></div>
                <div><span className="text-gray-400">Harmonic color:</span> <span className="text-gray-100">{meta.harmonic_color}</span></div>
                <div><span className="text-gray-400">Instruments:</span> <span className="text-gray-100">{meta.instruments.join(", ")}</span></div>
                <div><span className="text-gray-400">Seed:</span> <span className="text-gray-100">{meta.seed ?? "brak"}</span></div>
                <div className="mt-2 pt-2 border-t border-orange-900/40 text-orange-300 font-semibold">Instrument configs:</div>
                {meta.instrument_configs.map((cfg, idx) => (
                  <div
                    key={cfg.name || idx}
                    className="pl-3 pr-1 py-1 text-[11px] text-gray-200 border-l-2 border-orange-900/60 mt-1 hover:bg-orange-900/10 transition-colors rounded-r"
                  >
                    <div className="font-semibold text-orange-300 mb-0.5">
                      {cfg.name || `Instrument ${idx + 1}`}
                    </div>
                    <div className="pl-2 space-y-0.5 text-[10px] text-gray-300 grid grid-cols-2 gap-x-2">
                      <div><span className="text-gray-400">Rola:</span> {cfg.role}</div>
                      <div><span className="text-gray-400">Rejestr:</span> {cfg.register}</div>
                      <div><span className="text-gray-400">Artykulacja:</span> {cfg.articulation}</div>
                      <div><span className="text-gray-400">Dynamic range:</span> {cfg.dynamic_range}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-[11px] text-gray-500 border border-gray-800/50 rounded-xl p-4 bg-black/30 text-center">
              Brak meta – wróć do kroku 1 i wygeneruj parametry.
            </div>
          )}
        </div>
      </div>

      {/* Action button full width */}
      <div>
        <ElectricBorder
          as="button"
          onClick={handleRun}
          disabled={!canRun}
          className={`w-full py-3.5 text-base font-semibold text-white bg-black/50 rounded-xl transition-all duration-300 ${!canRun ? 'opacity-30 cursor-not-allowed scale-[0.98] grayscale' : 'scale-[0.98] hover:scale-100 hover:brightness-125 hover:bg-black/70 hover:shadow-lg hover:shadow-orange-400/20'}`}
          color="#f97316"
          speed={0.1}
          chaos={0.3}
        >
          {loading ? (
            'Generuję…'
          ) : (
            <span className="flex items-center justify-center gap-2">
              {meta ? "Generuj plan MIDI" : "Brak danych"}
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
                <path fillRule="evenodd" d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V9.017 5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z" clipRule="evenodd" />
              </svg>
            </span>
          )}
        </ElectricBorder>
      </div>

      {error && <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-sm rounded-xl px-4 py-3">{error}</div>}

      {!meta && (
        <div className="text-xs text-gray-500 border border-gray-800/50 rounded-xl p-4 bg-black/30 text-center">
          Najpierw ukończ krok parametrów (AI), aby uzyskać meta.
        </div>
      )}

      {result && (
        <div className="space-y-3 border border-orange-800/30 rounded-2xl p-5 bg-black/30 shadow-inner shadow-black/50">
          <div className="text-xs text-gray-400 flex flex-wrap gap-4 items-center justify-between border-b border-orange-900/30 pb-2 mb-2">
            <div className="flex gap-4">
              <span>run_id: <span className="text-gray-200 font-mono">{result.run_id}</span></span>
              {result.provider && <span>provider: <span className="text-orange-300">{result.provider}</span></span>}
              {result.model && <span>model: <span className="text-orange-300">{result.model}</span></span>}
            </div>
            <div className="text-[10px] uppercase tracking-widest text-orange-500/70 font-bold">Midi Preview</div>
          </div>
          {/* Pianoroll frontendowy na bazie JSON-a z backendu */}
          <div className="relative">
            <MidiPianoroll ref={pianorollScrollRef} midi={result.midi as any} />
            {/* Info o przewijaniu zostawiamy, ale używamy natywnego scrolla kontenera */}
            <div className="mt-2 text-[10px] text-orange-400/60 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-11.25a.75.75 0 00-1.5 0v2.5h-2.5a.75.75 0 000 1.5h2.5v2.5a.75.75 0 001.5 0v-2.5h2.5a.75.75 0 000-1.5h-2.5v-2.5z" clipRule="evenodd" />
              </svg>
              <span className="hidden sm:inline">Użyj suwaków zoom, aby dostosować widok. Przewijaj w poziomie, aby zobaczyć całość.</span>
            </div>
          </div>
        </div>
      )}
      {result && (
        <details className="bg-gray-900/30 rounded-xl px-3 py-2 border border-orange-800/30 mt-2">
          <summary className="cursor-pointer text-orange-300 text-xs mb-1 hover:text-orange-200 transition-colors">Pełny kontekst wymiany z modelem (MIDI)</summary>
          <div className="space-y-2 mt-2">
            {systemPrompt && (
              <div>
                <div className="text-[10px] text-gray-400">System prompt</div>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-orange-900/40">{systemPrompt}</pre>
              </div>
            )}
            {userPrompt && (
              <div>
                <div className="text-[10px] text-gray-400">User payload (JSON)</div>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-orange-900/40">{userPrompt}</pre>
              </div>
            )}
            {normalized && (
              <div>
                <div className="text-[10px] text-gray-400">Normalizowana odpowiedź modelu</div>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-orange-900/40">{pretty(normalized)}</pre>
              </div>
            )}
            {!normalized && rawText && (
              <div>
                <div className="text-[10px] text-gray-400">Surowa odpowiedź modelu</div>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-orange-900/40">{rawText}</pre>
              </div>
            )}
          </div>
        </details>
      )}

      <LoadingOverlay
        isVisible={loading}
        message="Komponowanie sekwencji MIDI..."
      />
    </section>
  );
}
