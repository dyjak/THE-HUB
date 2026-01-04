"use client";
import { useEffect, useMemo, useState } from 'react';
import { SimpleAudioPlayer } from './SimpleAudioPlayer';
import type { SampleListItem, SampleListResponse } from '../types';

type Props = {
  apiBase: string;
  apiPrefix: string;
  modulePrefix: string;
  instrument: string;
  selectedId?: string | null;
  onChange: (instrument: string, sampleId: string | null) => void;
};

export function SampleSelector({ apiBase, apiPrefix, modulePrefix, instrument, selectedId, onChange }: Props) {
  const [items, setItems] = useState<SampleListItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true); setError(null);
      try {
        const res = await fetch(`${apiBase}${apiPrefix}${modulePrefix}/samples/${encodeURIComponent(instrument)}?limit=200`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: SampleListResponse = await res.json();
        if (!mounted) return;
        const list = Array.isArray(data.items) ? data.items : [];
        setItems(list);
        // Auto-pick a random sample if none selected yet
        if (!selectedId && list.length > 0) {
          const rand = list[Math.floor(Math.random() * list.length)];
          if (rand?.id) {
            onChange(instrument, rand.id);
          }
        }
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, [apiBase, apiPrefix, modulePrefix, instrument]);

  const current = useMemo(() => (items || []).find(x => x.id === selectedId) || null, [items, selectedId]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <label className="text-[11px] text-gray-400">Sample</label>
        {loading && <span className="text-[11px] text-gray-500">loading…</span>}
        {error && <span className="text-[11px] text-red-400">{error}</span>}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <select
          className="bg-black/60 p-2 rounded border border-gray-700 text-xs min-w-[200px]"
          value={selectedId ?? ''}
          onChange={e => onChange(instrument, e.target.value || null)}
        >
          {(!items || items.length === 0) && <option value="">(no local samples)</option>}
          {(items || []).map(item => (
            <option key={item.id} value={item.id}>
              {item.name} {item.pitch ? `• ${item.pitch}` : ''} {item.subtype ? `• ${item.subtype}` : ''}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          {current?.url ? (
            <SimpleAudioPlayer src={`${apiBase}${current.url}`} className="w-full" height={40} />
          ) : (
            <span className="text-[11px] text-gray-500">no preview</span>
          )}
        </div>
      </div>
    </div>
  );
}
