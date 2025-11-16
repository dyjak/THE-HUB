"use client";
import React, { useEffect, useMemo, useState } from "react";
import { SimpleAudioPlayer } from "@/app/air/tests/ai-render-test/components/SimpleAudioPlayer";

type InstrumentListResp = { available: string[]; count: number };
type SampleItem = {
  id: string;
  file: string;
  name: string;
  url: string | null;
  subtype?: string | null;
  family?: string | null;
  category?: string | null;
  pitch?: string | null;
};
type SamplesResp = {
  instrument: string;
  count: number;
  offset: number;
  limit: number;
  items: SampleItem[];
  default?: SampleItem | null;
};

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export const InventoryBrowser: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [instruments, setInstruments] = useState<string[]>([]);
  const [instrument, setInstrument] = useState<string>("");
  const [samples, setSamples] = useState<SampleItem[]>([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true); setError(null);
      try {
        const r = await fetch(`${API_BASE}/api/air/inventory/available-instruments`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data: InstrumentListResp = await r.json();
        if (!alive) return;
        setInstruments(data.available || []);
        if (!instrument && data.available?.length) setInstrument(data.available[0]);
      } catch (e: any) {
        setError(e?.message || String(e));
      } finally {
        setLoading(false);
      }
    })();
    return () => { alive = false };
  }, []);

  useEffect(() => {
    if (!instrument) return;
    let alive = true;
    (async () => {
      setLoading(true); setError(null);
      try {
        const r = await fetch(`${API_BASE}/api/air/inventory/samples/${encodeURIComponent(instrument)}?limit=100`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data: SamplesResp = await r.json();
        if (!alive) return;
        // Normalize to absolute URL only; trust backend to provide correctly encoded paths
        const items = (data.items || []).map((it) => ({
          ...it,
          url: it.url ? (it.url.startsWith("http") ? it.url : `${API_BASE}${it.url}`) : null,
        }));
        setSamples(items);
      } catch (e: any) {
        setError(e?.message || String(e));
      } finally {
        setLoading(false);
      }
    })();
    return () => { alive = false };
  }, [instrument]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <label className="text-sm text-gray-400">Instrument</label>
        <select
          className="bg-black/40 border border-gray-700 rounded px-2 py-1"
          value={instrument}
          onChange={e => setInstrument(e.target.value)}
        >
          {instruments.map(i => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
        {loading && <span className="text-xs text-gray-500">loading…</span>}
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {samples.map((s) => (
          <div key={s.id} className="border border-gray-800 rounded p-3 bg-black/40">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-sm font-semibold">{s.name}</div>
                <div className="text-[11px] text-gray-400 space-x-2">
                  {s.category && <span>cat: {s.category}</span>}
                  {s.subtype && <span>sub: {s.subtype}</span>}
                  {s.family && <span>fam: {s.family}</span>}
                  {s.pitch && <span>pitch: {s.pitch}</span>}
                </div>
              </div>
              {s.url ? (
                <a className="text-xs text-emerald-400 hover:underline" href={s.url} target="_blank">open</a>
              ) : (
                <span className="text-xs text-gray-500">no url</span>
              )}
            </div>
              {s.url ? (
              <SimpleAudioPlayer src={s.url} variant="compact" />
            ) : (
              <div className="text-xs text-gray-500">Brak URL podglądu</div>
            )}
          </div>
        ))}
        {!samples.length && !loading && (
          <div className="text-sm text-gray-400">Brak próbek dla wybranego instrumentu.</div>
        )}
      </div>
    </div>
  );
};
