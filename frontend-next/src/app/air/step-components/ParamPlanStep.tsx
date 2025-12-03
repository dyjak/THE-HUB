"use client";
import { useCallback, useEffect, useState } from "react";
import { ParamPanel } from "./ParamPanel";
import type { ParamPlan, InstrumentConfig, ParamPlanMeta } from "../lib/paramTypes";
import { ensureInstrumentConfigs, normalizeParamPlan, cloneParamPlan } from "../lib/paramUtils";
import ElectricBorder from "@/components/ui/ElectricBorder";
import LoadingOverlay from "@/components/ui/LoadingOverlay";

type ChatProviderInfo = { id: string; name: string; default_model?: string };

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
// Use new param-generation backend module
const MODULE_PREFIX = "/air/param-generation";

type Props = {
  onMetaReady?: (meta: ParamPlanMeta | null) => void;
  onNavigateNext?: () => void;
  // pełny plan + wybrane sample (instrument -> sampleId) przekazywane do AirPanel
  onPlanChange?: (plan: ParamPlan | null, selectedSamples: Record<string, string | undefined>) => void;
  // Obsługa run_id z backendu, żeby można było odtworzyć stan kroku 1
  initialRunId?: string | null;
  onRunIdChange?: (runId: string | null) => void;
};


export default function ParamPlanStep({ onMetaReady, onNavigateNext, onPlanChange, initialRunId, onRunIdChange }: Props) {
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
  const [midi, setMidi] = useState<ParamPlan | null>(null);
  const [available, setAvailable] = useState<string[]>([]);
  const [selectable, setSelectable] = useState<string[]>([]);
  const [selectedSamples, setSelectedSamples] = useState<Record<string, string | undefined>>({});
  const [showResetWarning, setShowResetWarning] = useState(false);

  // Synchronize local plan + selected samples to parent AirPanel
  useEffect(() => {
    if (!onPlanChange) return;
    onPlanChange(midi, selectedSamples);
  }, [midi, selectedSamples, onPlanChange]);

  // Jeśli mamy initialRunId, spróbujmy wczytać istniejący parameter_plan.json z backendu
  useEffect(() => {
    if (!initialRunId) return;
    let active = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(initialRunId)}`);
        if (!res.ok) return;
        const payload = await res.json().catch(() => null);
        if (!active || !payload?.plan) return;

        // Preferuj payload.plan.meta, ale jeśli jej nie ma, spróbuj użyć całego planu jako ParamPlan
        const rawMeta = (payload.plan.meta || payload.plan) as any;
        if (!rawMeta || typeof rawMeta !== "object") return;

        let cloned: ParamPlan;
        try {
          const normalizedMidi = normalizeParamPlan(rawMeta);
          cloned = cloneParamPlan(normalizedMidi);
        } catch {
          // Fallback: zbuduj minimalny ParamPlan na podstawie dostępnych pól,
          // tak aby ParamPanel zawsze mógł się pojawić, jeśli dane istnieją.
          cloned = {
            style: rawMeta.style ?? "ambient",
            genre: rawMeta.genre ?? "generic",
            mood: rawMeta.mood ?? "calm",
            tempo: typeof rawMeta.tempo === "number" ? rawMeta.tempo : 80,
            key: rawMeta.key ?? "C",
            scale: rawMeta.scale ?? "major",
            meter: rawMeta.meter ?? "4/4",
            bars: typeof rawMeta.bars === "number" ? rawMeta.bars : 16,
            length_seconds: typeof rawMeta.length_seconds === "number" ? rawMeta.length_seconds : 180,
            dynamic_profile: rawMeta.dynamic_profile ?? "moderate",
            arrangement_density: rawMeta.arrangement_density ?? "balanced",
            harmonic_color: rawMeta.harmonic_color ?? "diatonic",
            instruments: Array.isArray(rawMeta.instruments) && rawMeta.instruments.length > 0 ? rawMeta.instruments : ["piano"],
            instrument_configs: Array.isArray(rawMeta.instrument_configs) ? rawMeta.instrument_configs : [],
            seed: typeof rawMeta.seed === "number" ? rawMeta.seed : null,
          };
        }
        setMidi(cloned);
        setRunId(initialRunId);
        if (onMetaReady) onMetaReady(cloned);
        const sel = (payload.plan.meta?.selected_samples || payload.plan.selected_samples || {}) as Record<string, string>;
        setSelectedSamples(sel);
        if (onPlanChange) onPlanChange(cloned, sel);
      } catch {
        // brak stanu nie jest błędem krytycznym
      }
    })();
    return () => { active = false; };
  }, [initialRunId]);

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
      } catch { }
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
        // De-duplicate and sanitize model names to avoid React key collisions
        const uniq = Array.from(new Set(list.filter(m => typeof m === "string" && m.trim())));
        if (!mounted) return;
        setModels(uniq);
        if (uniq.length > 0) setModel(prev => (prev && uniq.includes(prev) ? prev : uniq[0]));
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
      } catch { }
    })();
    return () => { mounted = false; };
  }, []);

  const pretty = useCallback((v: unknown) => { try { return JSON.stringify(v, null, 2); } catch { return String(v); } }, []);

  // Sync selectedSamples to parent and persist to backend parameter_plan.json when runId is known
  const updateSelectedSamples = useCallback(
    async (next: Record<string, string | undefined>) => {
      setSelectedSamples(next);
      if (!runId) return;
      try {
        const cleaned: Record<string, string> = {};
        for (const [k, v] of Object.entries(next)) {
          if (!k || !v) continue;
          cleaned[k] = v;
        }
        await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(runId)}/selected-samples`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ selected_samples: cleaned }),
        });
      } catch {
        // silently ignore PATCH errors; UI state remains source of truth
      }
    },
    [runId],
  );

  // Persist full meta (ParamPlan) to backend parameter_plan.json when runId is known
  const persistMeta = useCallback(
    async (nextMeta: ParamPlan) => {
      if (!runId) return;
      try {
        await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan/${encodeURIComponent(runId)}/meta`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ meta: nextMeta }),
        });
      } catch {
        // backend sync failure nie powinien blokować UX; frontend pozostaje źródłem prawdy
      }
    },
    [runId],
  );

  const send = useCallback(async () => {
    if (!prompt.trim()) { setError("Wpisz opis utworu."); return; }
    setLoading(true); setError(null); setRaw(null); setParsed(null); setNormalized(null); setRunId(null); setWarnings([]);
    setSystemPrompt(null); setUserPrompt(null);
    if (onMetaReady) onMetaReady(null);
    try {
      const parameters = {
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
        instruments: ["piano", "pad", "strings"],
        instrument_configs: [],
        seed: null,
      };
      const body = {
        parameters,
        provider,
        model,
      };
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/plan`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) throw new Error(payload?.detail?.message || res.statusText || "Request failed");
      const runVal = typeof payload?.run_id === 'string' ? payload.run_id : null;
      setRunId(runVal);
      if (onRunIdChange) onRunIdChange(runVal);
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
        const normalizedMidi = normalizeParamPlan(midiPart as any);
        const cloned = cloneParamPlan(normalizedMidi);
        setMidi(cloned);
        if (onMetaReady) onMetaReady(cloned);
        // reset selected samples for a fresh plan; PATCH is handled inside helper
        await updateSelectedSamples({});
      } else {
        setMidi(null);
        if (onMetaReady) onMetaReady(null);
      }
      const errorsArr = Array.isArray(payload?.errors) ? payload.errors.filter((e: any) => typeof e === 'string') : [];
      const warn: string[] = [];
      const hasMeta = !!(parsed && parsed.meta && typeof parsed.meta === 'object');
      if (!hasMeta) warn.push("Brak pełnych danych z modelu.");
      if (errorsArr.length) warn.push(...errorsArr.map((e: string) => `parse: ${e}`));
      setWarnings(Array.from(new Set(warn)));
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [prompt, provider, model, updateSelectedSamples]);

  return (

    <section className="bg-gray-900/30 border border-purple-700/30 rounded-2xl shadow-lg shadow-purple-900/10 px-6 pt-6 pb-4 space-y-5">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-3xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-purple-100 to-fuchsia-500 animate-pulse">Krok 1 • Generowanie parametrów</h2>
        {midi && !loading && (
          <ElectricBorder
            as="button"
            type="button"
            onClick={() => onNavigateNext && onNavigateNext()}
            className="w-auto px-12 py-3 font-bold text-white bg-black/50 rounded-2xl transition-all duration-300 hover:scale-105 hover:brightness-125 hover:bg-black/70 text-xs"
            color="#ec48ecff"
            speed={0.6}
            chaos={0.4}
          >
            Przejdź do kroku 2
          </ElectricBorder>
        )}
      </div>
      <p className="text-xs text-gray-400 max-w-2xl">Model generuje <span className="text-purple-300">parametry muzyczne</span> w formacie JSON. Wynik będzie podstawą do późniejszego tworzenia planu MIDI i renderu audio.</p>
      {/* Layout: lewa kolumna 1/4 (provider, model), prawa 3/4 (prompt) */}
      <div className="grid md:grid-cols-4 gap-4 items-start">
        <div className="md:col-span-1 space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-widest text-purple-300 mb-1">Provider</label>
            <div className="relative">
              <select
                value={provider}
                onChange={e => setProvider(e.target.value)}
                className="appearance-none w-full bg-black/50 border border-purple-800/40 rounded-lg pr-9 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-500"
              >
                {providers.map(p => (
                  <option key={p.id} value={p.id} disabled={(p.id || '').toLowerCase() === 'openai'}>
                    {p.name}{(p.id || '').toLowerCase() === 'openai' ? ' (disabled)' : ''}
                  </option>
                ))}
              </select>
              <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-purple-300 opacity-70" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
          <div>
            <label className="block text-xs uppercase tracking-widest text-purple-300 mb-1">Model</label>
            {models.length > 0 ? (
              <div className="relative">
                <select value={model} onChange={e => setModel(e.target.value)} className="appearance-none w-full bg-black/50 border border-purple-800/40 rounded-lg pr-9 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-500">
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
                <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-purple-300 opacity-70" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              </div>
            ) : (
              <input value={model} onChange={e => setModel(e.target.value)} placeholder="gemini-2.5-flash" className="w-full bg-black/50 border border-purple-800/40 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-500" />
            )}
          </div>
        </div>
        <div className="md:col-span-3">
          <label className="block text-xs uppercase tracking-widest text-purple-300 mb-1">Opis utworu (prompt)</label>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            rows={4}
            placeholder="np. 'epicki, kinowy motyw 90 BPM z chórem i perkusją'"
            className="w-full bg-black/50 border border-purple-800/40 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300 resize-none"
          />
        </div>
      </div>
      {/* Action button full width */}
      <div>
        <ElectricBorder
          as="button"
          onClick={send}
          disabled={loading || prompt.trim().length <= 3}
          className={`w-full py-3.5 text-base font-semibold text-white bg-black/50 rounded-xl transition-all duration-300 ${loading || prompt.trim().length <= 3 ? 'opacity-30 cursor-not-allowed scale-[0.98] grayscale' : 'scale-[0.98] hover:scale-100 hover:brightness-125 hover:bg-black/70 hover:shadow-lg hover:shadow-purple-400/20'}`}
          color="#d946ef"
          speed={0.1}
          chaos={0.3}
        >
          {loading ? (
            'Generuję…'
          ) : (
            <span className="flex items-center justify-center gap-2">
              Generuj parametry
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
                <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm4.28 10.28a.75.75 0 000-1.06l-3-3a.75.75 0 10-1.06 1.06l1.72 1.72H8.25a.75.75 0 000 1.5h5.69l-1.72 1.72a.75.75 0 101.06 1.06l3-3z" clipRule="evenodd" />
              </svg>
            </span>
          )}
        </ElectricBorder>
        {runId && <div className="mt-2 text-[11px] text-gray-500">run: {runId}</div>}
      </div>

      {error && <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-sm rounded-xl px-4 py-3">{error}</div>}
      {warnings.length > 0 && (
        <div className="flex items-start gap-2 text-xs bg-amber-900/40 border border-amber-600/70 text-amber-100 px-3 py-2 rounded-lg">
          <span className="mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-black text-[10px] font-bold">!</span>
          <div>
            <div className="font-semibold uppercase tracking-widest text-[10px] text-amber-200">Ostrzeżenie</div>
            <div className="mt-0.5 text-[11px]">
              {warnings.map((w, i) => <div key={i}>{w}</div>)}
              <br />
              To się zdarza, gdy model nie trzyma się narzuconej struktury JSON.
              <br />
              Spróbuj ponownie.
            </div>
          </div>
        </div>
      )}
      {/* Panel dostosowania parametrów - widoczny po wygenerowaniu */}
      {midi && (
        <div className="bg-black/30 border border-purple-800/40 rounded-2xl p-4 space-y-3 text-xs">
          <div className="text-purple-300 text-xs uppercase tracking-widest">Panel dostosowania parametrów</div>
          <ParamPanel
            midi={midi}
            availableInstruments={available}
            selectableInstruments={selectable}
            apiBase={API_BASE}
            apiPrefix={API_PREFIX}
            // Use param-generation proxy endpoints (internally backed by inventory)
            modulePrefix={"/air/param-generation"}
            compact
            columns={4}
            onUpdate={(patch: Partial<ParamPlan>) => setMidi((prev: ParamPlan | null) => {
              if (!prev) return prev;
              const next = { ...prev, ...patch };
              void persistMeta(next);
              return next;
            })}
            onToggleInstrument={(inst: string) => {
              setMidi((prev: ParamPlan | null) => {
                if (!prev) return prev;
                const exists = prev.instruments.includes(inst);
                const nextInstruments = exists ? prev.instruments.filter((i: string) => i !== inst) : [...prev.instruments, inst];
                // Cleanup sample selection for removed
                if (exists) {
                  setSelectedSamples((ss: Record<string, string | undefined>) => {
                    const copy = { ...ss }; delete copy[inst]; return copy;
                  });
                }
                const nextPlan: ParamPlan = {
                  ...prev,
                  instruments: nextInstruments,
                  instrument_configs: ensureInstrumentConfigs(nextInstruments, prev.instrument_configs),
                };
                void persistMeta(nextPlan);
                return nextPlan;
              });
            }}
            onUpdateInstrumentConfig={(name: string, patch: Partial<InstrumentConfig>) => setMidi((prev: ParamPlan | null) => {
              if (!prev) return prev;
              const nextConfigs = prev.instrument_configs.map((cfg: InstrumentConfig) => cfg.name === name ? { ...cfg, ...patch } as InstrumentConfig : cfg);
              const nextPlan: ParamPlan = { ...prev, instrument_configs: ensureInstrumentConfigs(prev.instruments, nextConfigs) };
              void persistMeta(nextPlan);
              return nextPlan;
            })}
            selectedSamples={selectedSamples}
            onSelectSample={(instrument: string, sampleId: string | null) => {
              const next = { ...selectedSamples } as Record<string, string | undefined>;
              if (!sampleId) {
                delete next[instrument];
              } else {
                next[instrument] = sampleId;
              }
              void updateSelectedSamples(next);
            }}
          />
        </div>
      )}
      {showResetWarning && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60">
          <div className="bg-gray-900 border border-purple-700 rounded-2xl p-5 max-w-sm w-full space-y-3 shadow-xl">
            <div className="text-sm font-semibold text-purple-300">Uwaga: zresetować aktualne ustawienia?</div>
            <p className="text-xs text-gray-300">
              Powrót do kroku 1 i ponowne generowanie parametrów wyzeruje bieżący plan MIDI oraz wybór sampli.
            </p>
            <div className="flex justify-end gap-2 mt-2 text-xs">
              <button
                type="button"
                onClick={() => setShowResetWarning(false)}
                className="px-3 py-1.5 rounded-lg border border-gray-600 text-gray-200 hover:bg-gray-800/60"
              >
                Anuluj
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowResetWarning(false);
                  // pełny reset lokalnego stanu kroku 1
                  setMidi(null);
                  setSelectedSamples({});
                  setRaw(null);
                  setParsed(null);
                  setNormalized(null);
                  setRunId(null);
                  setWarnings([]);
                  setSystemPrompt(null);
                  setUserPrompt(null);
                  setError(null);
                  if (onMetaReady) onMetaReady(null);
                }}
                className="px-3 py-1.5 rounded-lg bg-purple-700 text-white hover:bg-purple-600"
              >
                Wyzeruj ustawienia
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Podgląd promptu i odpowiedzi modelu */}
      {(systemPrompt || userPrompt || normalized || raw) && (
        <details className="bg-gray-900/30 rounded-xl px-3 py-2 border border-purple-800/30">
          <summary className="cursor-pointer text-purple-300 text-xs mb-1 hover:text-purple-200 transition-colors">Pełny kontekst wymiany z modelem</summary>
          <div className="space-y-2 mt-2">
            {systemPrompt && (
              <div>
                <div className="text-[10px] text-gray-400">System prompt</div>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-purple-900/40">{systemPrompt}</pre>
              </div>
            )}
            {userPrompt && (
              <div>
                <div className="text-[10px] text-gray-400">User payload (JSON)</div>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-purple-900/40">{userPrompt}</pre>
              </div>
            )}
            {normalized && (
              <div>
                <div className="text-[10px] text-gray-400">Normalizowana odpowiedź modelu</div>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-purple-900/40">{pretty(normalized)}</pre>
              </div>
            )}
            {raw && (
              <details className="mt-1">
                <summary className="cursor-pointer text-[10px] text-gray-500 hover:text-gray-300">Pokaż surową odpowiedź modelu</summary>
                <pre className="mt-0.5 whitespace-pre-wrap break-words text-[11px] max-h-40 overflow-auto bg-black/40 rounded-lg px-2 py-1 border border-purple-900/40">{raw}</pre>
              </details>
            )}
          </div>
        </details>
      )}

      {/* Loading overlay */}
      <LoadingOverlay
        isVisible={loading}
        message="Generuję zestaw parametrów dla Twojego utworu. To potrwa parę chwil... Serio."
      />
    </section>
  );
}
