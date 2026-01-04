"use client";

// przeglądarka inventory: lista instrumentów + siatka sampli z odsłuchem.
// robi dwa zapytania do backendu:
// 1) lista dostępnych instrumentów,
// 2) lista sampli dla aktualnie wybranego instrumentu.
import React, { useEffect, useState } from "react";
import { SimpleAudioPlayer } from "@/app/air/step-components/SimpleAudioPlayer";

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
    // pierwszy efekt: pobieramy listę instrumentów.
    // flaga alive chroni przed ustawianiem stanu po unmount.
    let alive = true;
    (async () => {
      setLoading(true); setError(null);
      try {
        const r = await fetch(`${API_BASE}/api/air/inventory/available-instruments`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data: InstrumentListResp = await r.json();
        if (!alive) return;
        setInstruments(data.available || []);
        // jeśli użytkownik jeszcze nic nie wybrał, ustawiamy pierwszy instrument z listy.
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
    // drugi efekt: za każdym razem gdy zmienia się instrument, pobieramy sample.
    let alive = true;
    (async () => {
      setLoading(true); setError(null);
      try {
        const r = await fetch(`${API_BASE}/api/air/inventory/samples/${encodeURIComponent(instrument)}?limit=100`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data: SamplesResp = await r.json();
        if (!alive) return;
        const items = (data.items || []).map((it) => ({
          ...it,
          // backend może zwrócić ścieżkę względną; tu normalizujemy ją do pełnego url.
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
    <div className="space-y-5">
      {/* panel wyboru instrumentu + stany ładowania/błędu */}
      <div className="bg-gray-900/30 border border-purple-700/30 rounded-xl p-4 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3">
            <label className="text-sm text-purple-300/80 font-medium">Instrument</label>
            <select
              className="bg-black/50 border border-purple-600/40 rounded-lg px-4 py-2 text-sm text-white focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50 transition-all cursor-pointer min-w-[200px]"
              value={instrument}
              onChange={e => setInstrument(e.target.value)}
            >
              {instruments.map(i => (
                <option key={i} value={i} className="bg-gray-900">{i}</option>
              ))}
            </select>
          </div>

          {loading && (
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-purple-300/60">Ładowanie...</span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-red-900/30 border border-red-700/40 rounded-lg">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-red-400">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
              <span className="text-xs text-red-300">{error}</span>
            </div>
          )}

          <div className="ml-auto text-xs text-purple-400/60">
            {samples.length > 0 && `${samples.length} próbek`}
          </div>
        </div>
      </div>

      {/* siatka sampli */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {samples.map((s) => (
          <div
            key={s.id}
            className="group border border-purple-800/30 rounded-xl p-4 bg-black/40 hover:bg-purple-900/20 hover:border-purple-700/50 transition-all duration-300"
          >
            {/* nagłówek kafelka */}
            <div className="flex items-start justify-between mb-3">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-purple-100 truncate group-hover:text-white transition-colors">
                  {s.name}
                </div>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {s.category && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-purple-900/40 border border-purple-700/30 rounded text-purple-300/80">
                      {s.category}
                    </span>
                  )}
                  {s.subtype && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-violet-900/40 border border-violet-700/30 rounded text-violet-300/80">
                      {s.subtype}
                    </span>
                  )}
                  {s.family && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-fuchsia-900/40 border border-fuchsia-700/30 rounded text-fuchsia-300/80">
                      {s.family}
                    </span>
                  )}
                  {s.pitch && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-pink-900/40 border border-pink-700/30 rounded text-pink-300/80">
                      {s.pitch}
                    </span>
                  )}
                </div>
              </div>

              {s.url && (
                <a
                  className="shrink-0 ml-2 p-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-500/30 text-purple-400 hover:text-purple-300 transition-all"
                  href={s.url}
                  target="_blank"
                  title="Otwórz w nowej karcie"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                    <path fillRule="evenodd" d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z" clipRule="evenodd" />
                    <path fillRule="evenodd" d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z" clipRule="evenodd" />
                  </svg>
                </a>
              )}
            </div>

            {/* odsłuch audio */}
            {s.url ? (
              <SimpleAudioPlayer src={s.url} variant="compact" height={36} />
            ) : (
              <div className="text-xs text-gray-500 italic py-2 text-center bg-gray-900/30 rounded-lg">
                Brak podglądu audio
              </div>
            )}
          </div>
        ))}

        {/* pusty stan: brak sampli dla instrumentu */}
        {!samples.length && !loading && (
          <div className="col-span-full bg-gray-900/30 border border-purple-800/30 rounded-xl p-8 text-center">
            <div className="text-purple-500/60 mx-auto mb-3">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-12 h-12 mx-auto opacity-40">
                <path fillRule="evenodd" d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V9.017 5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z" clipRule="evenodd" />
              </svg>
            </div>
            <p className="text-sm text-purple-300/60">Brak próbek dla wybranego instrumentu.</p>
            <p className="text-xs text-gray-500 mt-1">Wybierz inny instrument z listy powyżej.</p>
          </div>
        )}
      </div>

      {/* globalne style scrollbara dla tej listy (webkity) */}
      <style jsx global>{`
        .scroll-container-purple::-webkit-scrollbar {
          width: 6px;
        }
        .scroll-container-purple::-webkit-scrollbar-track {
          background: rgba(88, 28, 135, 0.2);
          border-radius: 3px;
        }
        .scroll-container-purple::-webkit-scrollbar-thumb {
          background: rgba(168, 85, 247, 0.4);
          border-radius: 3px;
        }
        .scroll-container-purple::-webkit-scrollbar-thumb:hover {
          background: rgba(168, 85, 247, 0.6);
        }
      `}</style>
    </div>
  );
};
