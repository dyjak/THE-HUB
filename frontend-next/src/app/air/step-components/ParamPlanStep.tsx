"use client";
import { useCallback, useEffect, useState } from "react";
import { MidiPanel } from "./MidiPanel";
import type { MidiParameters, InstrumentConfig } from "../lib/midiTypes";
import { ensureInstrumentConfigs, normalizeMidi, cloneMidi } from "../lib/midiUtils";

type ChatProviderInfo = { id: string; name: string; default_model?: string };

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
// Use new param-generation backend module
const MODULE_PREFIX = "/air/param-generation";

export default function ParamPlanStep() {
  const [prompt, setPrompt] = useState("");
  const [providers, setProviders] = useState<ChatProviderInfo[]>([]);
  const [provider, setProvider] = useState<string>("gemini");
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [parsed, setParsed] = useState<any | null>(null);
  const [normalized, setNormalized] = useState<any | null>(null);
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);
  const [userPrompt, setUserPrompt] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  // Editing panel state
  const [midi, setMidi] = useState<MidiParameters | null>(null);
  const [available, setAvailable] = useState<string[]>([]);
  const [selectable, setSelectable] = useState<string[]>([]);
  const [selectedSamples, setSelectedSamples] = useState<Record<string, string | undefined>>({});

  // Fetch providers
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
  const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/providers`);
        if (!res.ok) return;
        const data = await res.json();
        const list = Array.isArray(data?.providers) ? data.providers as ChatProviderInfo[] : [];
        if (!mounted) return;
        setProviders(list);
        // Prefer gemini by default if available
        const gem = list.find(p => (p.id || "").toLowerCase() === "gemini");
        const first = list[0];
        const chosen = gem || first;
        if (chosen) {
          setProvider((prev) => prev || chosen.id);
          setModel((prev) => prev || (chosen.default_model || ""));
        }
      } catch {}
    })();
    return () => { mounted = false; };
  }, []);

  // Fetch models for provider
  useEffect(() => {
    let mounted = true;
    if (!provider) { setModels([]); return; }
    (async () => {
      try {
  const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/models/${provider}`);
        if (!res.ok) { if (mounted) setModels([]); return; }
        const data = await res.json();
        const list = Array.isArray(data?.models) ? data.models as string[] : [];
        if (!mounted) return;
        setModels(list);
        if (list.length > 0) setModel(prev => (prev && list.includes(prev) ? prev : list[0]));
      } catch { if (mounted) setModels([]); }
    })();
    return () => { mounted = false; };
  }, [provider]);

  // Load available instruments (via param-generation proxy backed by inventory)
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}${API_PREFIX}/air/param-generation/available-instruments`);
        if (!res.ok) return;
        const data = await res.json().catch(() => null);
        const list = Array.isArray(data?.available) ? (data.available as string[]) : [];
        if (!mounted) return;
        setAvailable(list);
        // In this view, show only real instruments (no placeholders)
        setSelectable(list);
      } catch {}
    })();
    return () => { mounted = false; };
  }, []);

  const pretty = useCallback((v: unknown) => { try { return JSON.stringify(v, null, 2); } catch { return String(v); } }, []);

  const send = useCallback(async () => {
    if (!prompt.trim()) { setError("Wpisz opis utworu."); return; }
  setLoading(true); setError(null); setRaw(null); setParsed(null); setNormalized(null); setRunId(null); setWarnings([]);
  setSystemPrompt(null); setUserPrompt(null);
    try {
      const body = {
        midi: {
          prompt: prompt,
          style: "ambient",
          mood: "calm",
          tempo: 80,
          key: "C",
          scale: "major",
          meter: "4/4",
          bars: 16,
          length_seconds: 180,
          dynamic_profile: "moderate",
          arrangement_density: "balanced",
          harmonic_color: "diatonic",
          instruments: ["piano","pad","strings"],
          instrument_configs: [],
          seed: null,
        },
        provider,
        model,
      };
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/midi-plan`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) throw new Error(payload?.detail?.message || res.statusText || "Request failed");
      const runVal = typeof payload?.run_id === 'string' ? payload.run_id : null;
      setRunId(runVal);
  const sysStr = typeof payload?.system === 'string' ? payload.system : null;
  const userStr = typeof payload?.user === 'string' ? payload.user : null;
  setSystemPrompt(sysStr);
  setUserPrompt(userStr);
      const rawStr = typeof payload?.raw === 'string' ? payload.raw : null;
      setRaw(rawStr);
  const parsed = payload?.parsed ?? null;
  setParsed(parsed);
  const norm = parsed?.meta ? { midi: parsed.meta } : null;
  setNormalized(norm);
      // Initialize editor state if MIDI meta present
      const midiPart = norm?.midi ?? null;
      if (midiPart && typeof midiPart === 'object') {
        const normalizedMidi = normalizeMidi(midiPart as any);
        setMidi(cloneMidi(normalizedMidi));
      } else {
        setMidi(null);
      }
  const errorsArr = Array.isArray(payload?.errors) ? payload.errors.filter((e: any) => typeof e === 'string') : [];
  const warn: string[] = [];
  const hasMeta = !!(parsed && parsed.meta && typeof parsed.meta === 'object');
  if (!hasMeta) warn.push("Brak pełnych danych z modelu.");
	  if (errorsArr.length) warn.push(...errorsArr.map((e: string) => `parse: ${e}`));
  setWarnings(Array.from(new Set(warn)));
    } catch (e:any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [prompt, provider, model]);

  return (
    <section className="bg-gray-900/30 border border-blue-700/30 rounded-2xl shadow-lg shadow-blue-900/10 px-6 pt-6 pb-4 space-y-5">
      <h2 className="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-indigo-500 animate-pulse">Krok 1 • Generowanie parametrów</h2>
      <p className="text-xs text-gray-400 max-w-2xl">Model generuje <span className="text-sky-300">parametry muzyczne</span> w formacie JSON. Wynik będzie podstawą do późniejszego tworzenia planu MIDI i renderu audio.</p>
      {/* Layout: lewa kolumna 1/4 (provider, model), prawa 3/4 (prompt) */}
      <div className="grid md:grid-cols-4 gap-4 items-start">
        <div className="md:col-span-1 space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-widest text-sky-300 mb-1">Provider</label>
            <div className="relative">
              <select
                value={provider}
                onChange={e=>setProvider(e.target.value)}
                className="appearance-none w-full bg-black/50 border border-blue-800/40 rounded-lg pr-9 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {providers.map(p => (
                  <option key={p.id} value={p.id} disabled={(p.id||'').toLowerCase()==='openai'}>
                    {p.name}{(p.id||'').toLowerCase()==='openai' ? ' (disabled)' : ''}
                  </option>
                ))}
              </select>
              <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-300 opacity-70" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
          <div>
            <label className="block text-xs uppercase tracking-widest text-sky-300 mb-1">Model</label>
            {models.length>0 ? (
              <div className="relative">
                <select value={model} onChange={e=>setModel(e.target.value)} className="appearance-none w-full bg-black/50 border border-blue-800/40 rounded-lg pr-9 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
                <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-300 opacity-70" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              </div>
            ) : (
              <input value={model} onChange={e=>setModel(e.target.value)} placeholder="gemini-2.5-flash" className="w-full bg-black/50 border border-blue-800/40 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            )}
          </div>
        </div>
        <div className="md:col-span-3">
          <label className="block text-xs uppercase tracking-widest text-sky-300 mb-1">Opis utworu (prompt)</label>
          <textarea
            value={prompt}
            onChange={e=>setPrompt(e.target.value)}
            rows={4}
            placeholder="np. 'epicki, kinowy motyw 90 BPM z chórem i perkusją'"
            className="w-full bg-black/50 border border-blue-800/40 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>
      {/* Action button full width */}
      <div>
        <button
          onClick={send}
          disabled={loading}
          className="w-full px-4 py-3 rounded-xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 text-sm font-semibold disabled:opacity-60 transition-all duration-300 ease-out hover:-translate-y-0.5 hover:shadow-lg hover:shadow-blue-500/30 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {loading? 'Generuję…' : 'Generuj parametry'}
        </button>
        {runId && <div className="mt-2 text-[11px] text-gray-500">run: {runId}</div>}
      </div>
      {error && <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-sm rounded-xl px-4 py-3">{error}</div>}
      {warnings.length>0 && (
        <div className="bg-amber-900/20 border border-amber-700/60 text-amber-200 text-xs rounded-xl px-4 py-3 space-y-1">
          {warnings.map((w,i)=><div key={i}>• {w}</div>)}
        </div>
      )}
      {/* Panel dostosowania parametrów - widoczny po wygenerowaniu */}
      {midi && (
        <div className="bg-black/30 border border-blue-800/40 rounded-2xl p-4 space-y-3 text-xs">
          <div className="text-sky-300 text-xs uppercase tracking-widest">Panel dostosowania parametrów</div>
          <MidiPanel
            midi={midi}
            availableInstruments={available}
            selectableInstruments={selectable}
            apiBase={API_BASE}
            apiPrefix={API_PREFIX}
            // Use param-generation proxy endpoints (internally backed by inventory)
            modulePrefix={"/air/param-generation"}
            compact
            columns={4}
            onUpdate={(patch: Partial<MidiParameters>) => setMidi((prev: MidiParameters | null) => prev ? { ...prev, ...patch } : prev)}
            onToggleInstrument={(inst: string) => {
              setMidi((prev: MidiParameters | null) => {
                if (!prev) return prev;
                const exists = prev.instruments.includes(inst);
                const nextInstruments = exists ? prev.instruments.filter((i: string) => i !== inst) : [...prev.instruments, inst];
                // Cleanup sample selection for removed
                if (exists) {
                  setSelectedSamples((ss: Record<string, string | undefined>) => {
                    const copy = { ...ss }; delete copy[inst]; return copy;
                  });
                }
                return {
                  ...prev,
                  instruments: nextInstruments,
                  instrument_configs: ensureInstrumentConfigs(nextInstruments, prev.instrument_configs),
                };
              });
            }}
            onUpdateInstrumentConfig={(name: string, patch: Partial<InstrumentConfig>) => setMidi((prev: MidiParameters | null) => {
              if (!prev) return prev;
              const next = prev.instrument_configs.map((cfg: InstrumentConfig) => cfg.name === name ? { ...cfg, ...patch } as InstrumentConfig : cfg);
              return { ...prev, instrument_configs: ensureInstrumentConfigs(prev.instruments, next) };
            })}
            selectedSamples={selectedSamples}
            onSelectSample={(instrument: string, sampleId: string | null) => setSelectedSamples((prev: Record<string, string | undefined>) => ({ ...prev, [instrument]: sampleId || undefined }))}
          />
        </div>
      )}
      {/* Podgląd promptu i odpowiedzi modelu */}
      {(systemPrompt || userPrompt || normalized || raw) && (
        <div className="bg-gray-900/30 rounded-xl px-3 py-2 border border-blue-800/30 space-y-2">
          <div className="text-sky-300 text-xs mb-1">Pełny kontekst wymiany z modelem</div>
          {systemPrompt && (
            <div>
              <div className="text-[10px] text-gray-400">System prompt</div>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-blue-900/40">{systemPrompt}</pre>
            </div>
          )}
          {userPrompt && (
            <div>
              <div className="text-[10px] text-gray-400">User payload (JSON)</div>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-blue-900/40">{userPrompt}</pre>
            </div>
          )}
          {normalized && (
            <div>
              <div className="text-[10px] text-gray-400">Normalizowana odpowiedź modelu</div>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-blue-900/40">{pretty(normalized)}</pre>
            </div>
          )}
          {raw && (
            <details className="mt-1">
              <summary className="cursor-pointer text-[10px] text-gray-500 hover:text-gray-300">Pokaż surową odpowiedź modelu</summary>
              <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-blue-900/40">{raw}</pre>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
