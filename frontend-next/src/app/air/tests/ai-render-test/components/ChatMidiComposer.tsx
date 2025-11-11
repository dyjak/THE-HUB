"use client";
import { memo, useCallback, useMemo, useState } from 'react';
import type { MidiParameters, ChatProviderInfo } from '../types';

type Props = {
  disabled: boolean;
  midi: MidiParameters;
  providers: ChatProviderInfo[];
  provider: string;
  onProviderChange: (value: string) => void;
  models: string[];
  model: string;
  onModelChange: (value: string) => void;
  apiBase: string;
  apiPrefix: string;
  modulePrefix: string;
  onAfterCompose?: (result: { raw: string | null; parsed: unknown; runId: string | null }) => void;
};

const SYSTEM_PROMPT_PREVIEW = `MIDI planner: Respond ONLY with minified JSON\nSchema: {"pattern":[{"bar":n,"events":[{"step":n,"note":n,"vel":n,"len":n}]}],"layers":{"<instrument>":[{"bar":n,"events":[...] }]},"meta":{"tempo":n,"instruments":[string],"seed":n|null}}\nRules: use exact bars, steps 0..7, vel 1..127, len>=1; layer keys = instruments; merge layers into pattern.`;

function ChatMidiComposerImpl({ disabled, midi, providers, provider, onProviderChange, models, model, onModelChange, apiBase, apiPrefix, modulePrefix, onAfterCompose }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [parsed, setParsed] = useState<unknown | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  // Prefer backend parsed JSON; fallback to parsing raw locally for visualization
  const viz = useMemo(() => {
    if (parsed && typeof parsed === 'object') return parsed as any;
    if (raw) {
      try {
        const obj = JSON.parse(raw);
        if (obj && typeof obj === 'object') return obj;
      } catch {}
    }
    return null as any;
  }, [parsed, raw]);

  const bars = useMemo(() => {
    // Derive bars from plan first
    let derived = Number(midi?.bars ?? 0);
    // If viz has data, compute max bar index seen + 1
    const collectBars = (arr: any[]) => {
      let maxB = -1;
      for (const b of (Array.isArray(arr) ? arr : [])) {
        if (typeof b?.bar === 'number' && b.bar > maxB) maxB = b.bar;
      }
      return maxB + 1;
    };
    const fromPattern = viz?.pattern ? collectBars(viz.pattern) : 0;
    let fromLayers = 0;
    if (viz?.layers && typeof viz.layers === 'object') {
      for (const key of Object.keys(viz.layers)) {
        fromLayers = Math.max(fromLayers, collectBars(viz.layers[key]));
      }
    }
    const best = Math.max(derived || 0, fromPattern || 0, fromLayers || 0);
    return best > 0 ? best : 4;
  }, [midi, viz]);

  // Build a simple [bars][8] boolean grid for pattern visualization
  const buildGrid = useCallback((barObjects: any[], barCount: number) => {
    const grid: boolean[][] = Array.from({ length: barCount }, () => Array(8).fill(false));
    if (!Array.isArray(barObjects)) return grid;
    for (const barObj of barObjects) {
      const barIndex = typeof barObj?.bar === 'number' ? Math.max(0, Math.min(barCount - 1, barObj.bar)) : 0;
      const events = Array.isArray(barObj?.events) ? barObj.events : [];
      for (const ev of events) {
        const step = typeof ev?.step === 'number' ? ev.step : 0;
        const len = typeof ev?.len === 'number' ? Math.max(1, ev.len) : 1;
        for (let s = step; s < step + len; s++) {
          if (s >= 0 && s < 8) grid[barIndex][s] = true;
        }
      }
    }
    return grid;
  }, []);

  const send = useCallback(async () => {
    setLoading(true); setError(null); setRaw(null); setParsed(null); setRunId(null);
    try {
      const body = { midi, provider, model };
      const res = await fetch(`${apiBase}${apiPrefix}${modulePrefix}/chat-smoke/midiify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) throw new Error((payload && (payload.message || payload.detail?.message)) || `HTTP ${res.status}`);
      setRaw(typeof payload?.raw === 'string' ? payload.raw : null);
      setParsed(payload?.parsed ?? null);
      const rid = typeof payload?.run_id === 'string' ? payload.run_id : null;
      setRunId(rid);
      try { onAfterCompose && onAfterCompose({ raw: typeof payload?.raw === 'string' ? payload.raw : null, parsed: payload?.parsed ?? null, runId: rid }); } catch {}
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [apiBase, apiPrefix, modulePrefix, midi, provider, model]);

  return (
    <section className={`border rounded-2xl p-6 space-y-4 ${disabled ? 'bg-gray-900/40 border-gray-800 opacity-60' : 'bg-gray-900/70 border-blue-700/50'}`}>
      <div className="flex flex-col gap-4 md:flex-row md:gap-6 md:items-start">
        <div className="md:w-60 space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-widest text-blue-300 mb-1">Provider</label>
            <select disabled={disabled} value={provider} onChange={e=>onProviderChange(e.target.value)} className="w-full bg-black/60 border border-blue-800/60 rounded-lg px-3 py-2 text-sm">
              {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs uppercase tracking-widest text-blue-300 mb-1">Model</label>
            {models.length>0 ? (
              <select disabled={disabled} value={model} onChange={e=>onModelChange(e.target.value)} className="w-full bg-black/60 border border-blue-800/60 rounded-lg px-3 py-2 text-sm">
                {models.map(id => <option key={id} value={id}>{id}</option>)}
              </select>
            ) : (
              <input disabled={disabled} value={model} onChange={e=>onModelChange(e.target.value)} placeholder="gemini-2.5-flash" className="w-full bg-black/60 border border-blue-800/60 rounded-lg px-3 py-2 text-sm" />
            )}
          </div>
        </div>
        <div className="flex-1 space-y-3">
          <div className="text-[11px] text-gray-400">
            From plan → <span className="text-emerald-200">{midi.style}</span>, <span className="text-emerald-200">{midi.tempo}</span> bpm • instruments: <span className="text-emerald-200">{Array.isArray(midi.instruments)? midi.instruments.join(', ') : ''}</span>
          </div>
          <div className="flex items-center gap-3">
            <button disabled={disabled || loading} onClick={send} className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-500 text-sm font-semibold disabled:opacity-60">{loading ? 'Generuję…' : 'Wygeneruj MIDI (JSON)'}</button>
            {runId && <span className="text-xs text-blue-200">run: {runId}</span>}
          </div>
          <div className="text-[10px] text-gray-400 border border-gray-800 rounded-lg p-2 bg-black/40 whitespace-pre-wrap">
            {SYSTEM_PROMPT_PREVIEW}
          </div>
          {/* Request payload preview */}
          <details className="bg-gray-900/40 rounded-xl px-3 py-2">
            <summary className="cursor-pointer text-blue-300">Request payload (to composer)</summary>
            <pre className="mt-2 whitespace-pre-wrap break-words text-xs">{JSON.stringify({ midi, provider, model }, null, 2)}</pre>
          </details>
          {error && <div className="bg-red-900/30 border border-red-800/60 text-red-200 text-sm rounded px-3 py-2">{error}</div>}
          {raw && (
            <details className="bg-gray-900/40 rounded-xl px-3 py-2" open>
              <summary className="cursor-pointer text-blue-300">Surowa odpowiedź (MIDI JSON)</summary>
              <pre className="mt-2 whitespace-pre-wrap break-words">{raw}</pre>
            </details>
          )}
          {parsed != null && (
            <details className="bg-gray-900/40 rounded-xl px-3 py-2">
              <summary className="cursor-pointer text-blue-300">Parsed (po stronie backendu)</summary>
              <pre className="mt-2 whitespace-pre-wrap break-words">{JSON.stringify(parsed, null, 2)}</pre>
            </details>
          )}
          {viz != null && (
            <div className="space-y-4">
              <div className="text-sm text-emerald-300 font-semibold mt-2">Simple visualizations</div>
              {/* Combined pattern */}
              <div className="bg-black/40 border border-gray-800 rounded p-3">
                <div className="text-xs text-gray-400 mb-2">Combined pattern</div>
                <PatternGrid data={viz as any} kind="pattern" bars={bars} buildGrid={buildGrid} />
              </div>
              {/* Per-layer patterns */}
              <div className="bg-black/40 border border-gray-800 rounded p-3">
                <div className="text-xs text-gray-400 mb-2">Per-layer</div>
                <LayerGrids data={viz as any} bars={bars} buildGrid={buildGrid} />
              </div>
              <VizSummary data={viz as any} />
            </div>
          )}
        </div>
      </div>
      {disabled && (
        <div className="text-xs text-gray-500">Najpierw wygeneruj parametry (plan) w pierwszym czacie — ten moduł będzie aktywny, gdy parametry MIDI będą gotowe.</div>
      )}
    </section>
  );
}

export const ChatMidiComposer = memo(ChatMidiComposerImpl);

// --- Small visualization helpers ---
function PatternGrid({ data, kind, bars, buildGrid }: { data: any; kind: 'pattern'; bars: number; buildGrid: (bars: any[], n: number) => boolean[][] }) {
  const barObjects = Array.isArray(data?.[kind]) ? data[kind] : [];
  const grid = buildGrid(barObjects, bars);
  return (
    <div className="space-y-1">
      {grid.map((steps, idx) => (
        <div key={idx} className="flex items-center gap-2">
          <span className="text-[10px] w-10 text-gray-500">Bar {idx}</span>
          <div className="grid grid-cols-8 gap-1">
            {steps.map((on, sIdx) => (
              <div key={sIdx} className={`w-5 h-5 rounded ${on ? 'bg-emerald-500' : 'bg-gray-800'} border border-gray-700`} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function LayerGrids({ data, bars, buildGrid }: { data: any; bars: number; buildGrid: (bars: any[], n: number) => boolean[][] }) {
  const layers = data?.layers && typeof data.layers === 'object' ? data.layers as Record<string, any[]> : {};
  const keys = Object.keys(layers);
  if (keys.length === 0) return <div className="text-[11px] text-gray-500">No layers</div>;
  return (
    <div className="space-y-3">
      {keys.map((name) => {
        const barObjects = Array.isArray(layers[name]) ? layers[name] : [];
        const grid = buildGrid(barObjects, bars);
        return (
          <div key={name} className="space-y-1">
            <div className="text-[11px] text-emerald-200 uppercase tracking-wide">{name}</div>
            {grid.map((steps, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="text-[10px] w-10 text-gray-500">Bar {idx}</span>
                <div className="grid grid-cols-8 gap-1">
                  {steps.map((on, sIdx) => (
                    <div key={sIdx} className={`w-4 h-4 rounded ${on ? 'bg-cyan-500' : 'bg-gray-800'} border border-gray-700`} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function VizSummary({ data }: { data: any }) {
  const layers = data?.layers && typeof data.layers === 'object' ? (data.layers as Record<string, any[]>) : {};
  const names = Object.keys(layers);
  const patternBars = Array.isArray(data?.pattern) ? data.pattern.length : 0;
  const layerSummaries = names.map((name) => {
    const bars = Array.isArray(layers[name]) ? layers[name] : [];
    let count = 0;
    for (const b of bars) {
      const evs = Array.isArray(b?.events) ? b.events : [];
      count += evs.length;
    }
    return { name, bars: bars.length, events: count };
  });
  return (
    <div className="text-[11px] text-gray-400">
      <div>Bars (pattern): <span className="text-gray-200">{patternBars}</span></div>
      {layerSummaries.length>0 && (
        <div className="mt-1 flex flex-wrap gap-2">
          {layerSummaries.map(s => (
            <span key={s.name} className="px-2 py-0.5 border border-gray-700 rounded">{s.name}: {s.events} ev / {s.bars} bars</span>
          ))}
        </div>
      )}
    </div>
  );
}
