"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ParamPlanMeta } from "../lib/paramTypes";
import MidiPianoroll from "../components/MidiPianoroll";

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
  // Używane wcześniej do snippetowego panelu parametrów – już niepotrzebne
  // const [showFullMeta, setShowFullMeta] = useState(false);

  const pretty = useCallback((v: unknown) => {
    try { return JSON.stringify(v, null, 2); } catch { return String(v); }
  }, []);

  // Fetch providers (tak jak w kroku 1)
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
      } catch {
        // zostaw domyślnego providera
      }
    })();
    return () => { mounted = false; };
  }, []);

  // Fetch models (tak jak w kroku 1)
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
      // backend może zwracać te same pola co w kroku 1:
      // system, user, raw, parsed
      setSystemPrompt(typeof data.system === "string" ? data.system : null);
      setUserPrompt(typeof data.user === "string" ? data.user : null);
      setRawText(typeof data.raw === "string" ? data.raw : null);
      const parsed = data.parsed ?? null;
      // w prostym wariancie jako "normalizowaną" odpowiedź pokazujemy parsed
      setNormalized(parsed ?? null);
      if (onReady) onReady(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-gray-900/30 border border-emerald-700/40 rounded-2xl shadow-lg shadow-emerald-900/20 px-6 pt-6 pb-4 space-y-5">
      <h2 className="text-lg font-semibold bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-400">Krok 2 • Plan MIDI</h2>
      <p className="text-xs text-gray-400 max-w-2xl">
        Ten krok używa wygenerowanych parametrów, aby stworzyć <span className="text-emerald-300">szczegółowy pattern MIDI</span>. Wynik
        służy jako baza do eksportu pliku .mid i dalszego renderu audio.
      </p>

      {/* Provider + model */}
      <div className="grid md:grid-cols-4 gap-4 items-start">
        <div className="space-y-3 md:col-span-1">
          <div>
            <label className="block text-xs uppercase tracking-widest text-emerald-300 mb-1">Provider</label>
            <select
              value={provider}
              onChange={e => setProvider(e.target.value)}
              className="w-full bg-black/60 border border-emerald-800/60 rounded-lg px-3 py-2 text-sm"
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
          </div>
          <div>
            <label className="block text-xs uppercase tracking-widest text-emerald-300 mb-1">Model (opcjonalnie)</label>
            {models.length > 0 ? (
              <div className="relative">
                <select
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  className="appearance-none w-full bg-black/60 border border-emerald-800/60 rounded-lg pr-9 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                >
                  {models.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <svg
                  className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-emerald-300 opacity-70"
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
                className="w-full bg-black/60 border border-emerald-800/60 rounded-lg px-3 py-2 text-sm"
              />
            )}
          </div>
          <button
            onClick={handleRun}
            disabled={!canRun}
            className={`w-full px-3 py-2 rounded-lg text-xs font-semibold mt-2 ${
              canRun
                ? "bg-gradient-to-r from-emerald-500 to-cyan-500 text-black hover:brightness-110"
                : "bg-black/40 text-gray-500 border border-gray-700 cursor-not-allowed"
            }`}
          >
            {loading ? "Generowanie…" : meta ? "Generuj plan MIDI" : "Brak danych z kroku 1"}
          </button>
        </div>

        {/* Podgląd meta (read-only, stały panel ze scrollem) */}
        <div className="md:col-span-3">
          <label className="block text-xs uppercase tracking-widest text-emerald-300 mb-1">Parametry wejściowe (read-only)</label>
          {meta ? (
            <div className="space-y-1">
              <div
                className="relative text-[11px] bg-black/40 border border-emerald-800/30 rounded-xl px-3 pt-2 pb-2 space-y-0.5 max-h-52 overflow-y-auto scroll-container-green"
              >
              <div className="grid sm:grid-cols-2 gap-x-4 gap-y-0.5">
                <div><span className="text-gray-400">Style:</span> <span className="text-gray-100">{meta.style}</span></div>
                <div><span className="text-gray-400">Mood:</span> <span className="text-gray-100">{meta.mood}</span></div>
                <div><span className="text-gray-400">Tempo:</span> <span className="text-gray-100">{meta.tempo}</span></div>
                <div><span className="text-gray-400">Key:</span> <span className="text-gray-100">{meta.key}</span></div>
                <div><span className="text-gray-400">Scale:</span> <span className="text-gray-100">{meta.scale}</span></div>
                <div><span className="text-gray-400">Meter:</span> <span className="text-gray-100">{meta.meter}</span></div>
                <div><span className="text-gray-400">Bars:</span> <span className="text-gray-100">{meta.bars}</span></div>
                <div><span className="text-gray-400">Length seconds:</span> <span className="text-gray-100">{meta.length_seconds}</span></div>
              </div>
              <div><span className="text-gray-400">Dynamic profile:</span> <span className="text-gray-100">{meta.dynamic_profile}</span></div>
              <div><span className="text-gray-400">Arrangement density:</span> <span className="text-gray-100">{meta.arrangement_density}</span></div>
               <div><span className="text-gray-400">Harmonic color:</span> <span className="text-gray-100">{meta.harmonic_color}</span></div>
               <div><span className="text-gray-400">Instruments:</span> <span className="text-gray-100">{meta.instruments.join(", ")}</span></div>
               <div><span className="text-gray-400">Seed:</span> <span className="text-gray-100">{meta.seed ?? "brak"}</span></div>
               <div className="mt-1 pt-1 border-t border-emerald-900/40 text-emerald-300">Instrument configs:</div>
               {meta.instrument_configs.map((cfg, idx) => (
                 <div
                   key={cfg.name || idx}
                   className="pl-2 pr-1 py-1 text-[11px] text-gray-200 border-l border-emerald-900/60 mt-1"
                 >
                   <div className="font-semibold text-emerald-300 mb-0.5">
                     {cfg.name || `Instrument ${idx + 1}`}
                   </div>
                   <div className="pl-2 space-y-0.5 text-[10px] text-gray-300">
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
            <div className="text-[11px] text-gray-500 border border-gray-800 rounded-md p-2">
              Brak meta – wróć do kroku 1 i wygeneruj parametry.
            </div>
          )}
        </div>
      </div>

      {error && <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-xs rounded-xl px-3 py-2">{error}</div>}

      {!meta && (
        <div className="text-xs text-gray-500 border border-gray-800 rounded-md p-3">
          Najpierw ukończ krok parametrów (AI), aby uzyskać meta.
        </div>
      )}

      {result && (
        <div className="space-y-3 border border-gray-800 rounded-xl p-4 bg-black/40">
          <div className="text-xs text-gray-400 flex flex-wrap gap-4">
            <span>run_id: <span className="text-gray-200">{result.run_id}</span></span>
            {result.provider && <span>provider: {result.provider}</span>}
            {result.model && <span>model: {result.model}</span>}
          </div>
          {/* Pianoroll frontendowy na bazie JSON-a z backendu */}
          <div className="relative">
            <MidiPianoroll ref={pianorollScrollRef} midi={result.midi as any} />
            {/* Globalny h-scroll dostępny z każdej wysokości sekcji */}
            <div className="mt-2 border border-emerald-800/80 rounded-md bg-gradient-to-r from-black/90 via-slate-900/90 to-black/90 px-3 py-1 flex items-center gap-2 text-[10px] text-emerald-200 sticky bottom-0 z-10 backdrop-blur-sm">
              <span className="hidden sm:inline">Scroll</span>
              <div
                className="relative flex-1 h-3 overflow-x-auto overflow-y-hidden rounded-full bg-gray-900/80 custom-scroll-h"
                onScroll={e => {
                  const ghost = e.currentTarget;
                  const host = pianorollScrollRef.current;
                  if (host && host.scrollWidth > host.clientWidth) {
                    const ratio = ghost.scrollLeft / (ghost.scrollWidth - ghost.clientWidth || 1);
                    host.scrollLeft = ratio * (host.scrollWidth - host.clientWidth);
                  }
                }}
              >
                <div
                  style={{
                    width: (pianorollScrollRef.current?.scrollWidth || 0) + 32,
                    height: 1,
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
      {result && (
        <div className="bg-gray-900/30 rounded-xl px-3 py-2 border border-emerald-800/30 space-y-2 mt-2">
          <div className="text-emerald-300 text-xs mb-1">Pełny kontekst wymiany z modelem (MIDI)</div>
          {systemPrompt && (
            <div>
              <div className="text-[10px] text-gray-400">System prompt</div>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-emerald-900/40">{systemPrompt}</pre>
            </div>
          )}
          {userPrompt && (
            <div>
              <div className="text-[10px] text-gray-400">User payload (JSON)</div>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-emerald-900/40">{userPrompt}</pre>
            </div>
          )}
          {normalized && (
            <div>
              <div className="text-[10px] text-gray-400">Normalizowana odpowiedź modelu</div>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-emerald-900/40">{pretty(normalized)}</pre>
            </div>
          )}
          {!normalized && rawText && (
            <div>
              <div className="text-[10px] text-gray-400">Surowa odpowiedź modelu</div>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-emerald-900/40">{rawText}</pre>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
