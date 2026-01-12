"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getApiBaseUrl } from '@/lib/apiBase';

type ProviderInfo = { id: string; name: string; default_model?: string };

const API_BASE = getApiBaseUrl();

const DEFAULT_PLAN = {
  style: "ambient",
  mood: "calm",
  tempo: 80,
  key: "C",
  scale: "major",
  meter: "4/4",
  bars: 16,
  length_seconds: 180,
  form: ["intro","verse","chorus","verse","chorus","bridge","chorus","outro"],
  dynamic_profile: "moderate",
  arrangement_density: "balanced",
  harmonic_color: "diatonic",
  instruments: ["piano","pad","strings"],
  instrument_configs: [],
  seed: null,
};

export default function ParameterPlanPage() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [provider, setProvider] = useState<string>("");
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState<string>("");
  const [planText, setPlanText] = useState<string>(() => JSON.stringify(DEFAULT_PLAN, null, 2));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [parsed, setParsed] = useState<any | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [savedJson, setSavedJson] = useState<string | null>(null);
  const [savedRaw, setSavedRaw] = useState<string | null>(null);

  const PROVIDERS_URL = `${API_BASE}/api/air/param-generation/providers`;
  const MODELS_URL = (p: string) => `${API_BASE}/api/air/param-generation/models/${encodeURIComponent(p)}`;
  const PLAN_URL = `${API_BASE}/api/air/param-generation/plan`;
  const OUTPUT_PREFIX = `${API_BASE}/api/param-generation/output`;

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await fetch(PROVIDERS_URL);
        if (!res.ok) return;
        const data = await res.json();
        const list = Array.isArray(data?.providers) ? data.providers as ProviderInfo[] : [];
        if (!mounted) return;
        setProviders(list);
        if (list.length > 0) {
          const p = list[0];
          setProvider(prev => prev || p.id);
          setModel(prev => prev || (p.default_model || ""));
        }
      } catch {}
    })();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!provider) { setModels([]); return; }
    (async () => {
      try {
        const res = await fetch(MODELS_URL(provider));
        if (!res.ok) { if (mounted) setModels([]); return; }
        const data = await res.json();
        const list = Array.isArray(data?.models) ? data.models as string[] : [];
        if (!mounted) return;
        setModels(list);
        if (list.length > 0) setModel(prev => (prev && list.includes(prev) ? prev : list[0]));
      } catch {
        if (mounted) setModels([]);
      }
    })();
    return () => { mounted = false; };
  }, [provider]);

  const pretty = useCallback((v: unknown) => {
    try { return JSON.stringify(v, null, 2); } catch { return String(v); }
  }, []);

  const onGenerate = useCallback(async () => {
    setLoading(true); setError(null); setRaw(null); setParsed(null); setRunId(null); setSavedJson(null); setSavedRaw(null);
    let parameters: any = null;
    try {
      parameters = JSON.parse(planText);
    } catch (e) {
      setError("Błąd JSON w polu parametrów"); setLoading(false); return;
    }
    try {
      const res = await fetch(PLAN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ parameters, provider, model }),
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) throw new Error(payload?.detail?.message || res.statusText || "Request failed");
      setRaw(typeof payload?.raw === 'string' ? payload.raw : null);
      setParsed(payload?.parsed ?? null);
      setRunId(typeof payload?.run_id === 'string' ? payload.run_id : null);
      setSavedJson(typeof payload?.saved_json_rel === 'string' ? payload.saved_json_rel : null);
      setSavedRaw(typeof payload?.saved_raw_rel === 'string' ? payload.saved_raw_rel : null);
    } catch (e:any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [PLAN_URL, planText, provider, model]);

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-black via-gray-950 to-black text-white px-6 py-10 space-y-8">
  <h1 className="text-3xl font-bold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-cyan-400 to-emerald-400">AI Parameter Plan • Step 2</h1>
  <p className="text-sm text-gray-400 max-w-3xl">Ten panel generuje <span className="text-emerald-300">plan parametrów muzycznych</span> (meta + instrumenty + konfiguracje) na podstawie prompta. Wynik zapisywany jest do pliku, aby kolejne moduły mogły z niego skorzystać niezależnie od sesji.</p>

      <section className="bg-gray-900/70 border border-blue-800/40 rounded-2xl p-6 space-y-4">
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs uppercase tracking-widest text-blue-300 mb-1">Provider</label>
            <select value={provider} onChange={e=>setProvider(e.target.value)} className="w-full bg-black/60 border border-blue-900/60 rounded-lg px-3 py-2 text-sm">
              {providers.map(p=> <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs uppercase tracking-widest text-blue-300 mb-1">Model</label>
            {models.length>0 ? (
              <select value={model} onChange={e=>setModel(e.target.value)} className="w-full bg-black/60 border border-blue-900/60 rounded-lg px-3 py-2 text-sm">
                {models.map(m=> <option key={m} value={m}>{m}</option>)}
              </select>
            ) : (
              <input value={model} onChange={e=>setModel(e.target.value)} placeholder="np. gemini-2.5-flash" className="w-full bg-black/60 border border-blue-900/60 rounded-lg px-3 py-2 text-sm" />
            )}
          </div>
        </div>
        <div>
          <label className="block text-xs uppercase tracking-widest text-blue-300 mb-1">Music parameters (JSON)</label>
          <textarea value={planText} onChange={e=>setPlanText(e.target.value)} rows={14} className="w-full bg-black/60 border border-gray-800 rounded-xl px-4 py-3 text-sm font-mono" />
          <div className="text-[10px] text-gray-500 mt-1">Wprowadź parametry wymagane przez model (tempo, bars, instruments, itd.).</div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={onGenerate} disabled={loading} className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-500 text-sm font-semibold disabled:opacity-60">{loading ? 'Generuję…' : 'Generuj plan parametrów'}</button>
          {runId && <span className="text-xs text-blue-200">run: {runId}</span>}
        </div>
        {error && <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-sm rounded-xl px-4 py-3">{error}</div>}
        {(savedJson || savedRaw) && (
          <div className="bg-black/40 border border-gray-800 rounded-xl p-3 text-xs">
            <div className="text-gray-300 font-semibold mb-1">Zapisane pliki</div>
            <ul className="space-y-1">
              {savedJson && (
                <li>
                  <a className="underline" target="_blank" href={`${OUTPUT_PREFIX}/${savedJson}`}>{savedJson}</a>
                </li>
              )}
              {savedRaw && (
                <li>
                  <a className="underline" target="_blank" href={`${OUTPUT_PREFIX}/${savedRaw}`}>{savedRaw}</a>
                </li>
              )}
            </ul>
          </div>
        )}
        {raw && (
          <details className="bg-gray-900/40 rounded-xl px-3 py-2" open>
            <summary className="cursor-pointer text-blue-300">Surowa odpowiedź modelu</summary>
            <pre className="mt-2 whitespace-pre-wrap break-words">{raw}</pre>
          </details>
        )}
        {parsed && (
          <details className="bg-gray-900/40 rounded-xl px-3 py-2">
            <summary className="cursor-pointer text-blue-300">Parsed (JSON)</summary>
            <pre className="mt-2 whitespace-pre-wrap break-words">{pretty(parsed)}</pre>
          </details>
        )}
      </section>

  <div className="mt-8 text-center text-xs text-gray-600">Step 2 • AI Parameter Plan • outputs persisted for the next modules</div>
    </div>
  );
}
