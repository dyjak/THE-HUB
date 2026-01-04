"use client";

/*
  komponent do wyboru sampla dla konkretnego instrumentu.

  odpowiedzialności:
  - pobiera z backendu listę dostępnych sampli dla podanego instrumentu
  - renderuje select z listą oraz prosty podgląd audio wybranego sampla
  - gdy użytkownik nie wybrał jeszcze sampla, ustawia sensowny wybór startowy

  ważne uwagi:
  - pobieranie listy sampli zależy od instrumentu; zmiana instrumentu wywołuje nowe pobranie
  - wybór startowy jest robiony w osobnym efekcie, żeby nie mieszać go z logiką pobierania
*/
import { useEffect, useMemo, useState } from "react";
import { SimpleAudioPlayer } from "./SimpleAudioPlayer";
import type { SampleListItem, SampleListResponse } from "../lib/paramTypes";

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

  // pobiera listę sampli z backendu.
  // używamy flagi "mounted", żeby nie wywołać setState po odmontowaniu komponentu
  // (np. gdy użytkownik szybko przełączy instrument albo przejdzie do innego kroku).
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

  // jeśli nie ma jeszcze wybranego sampla, a lista już przyszła z backendu,
  // ustawiamy wybór startowy.
  //
  // mechanizm:
  // - jeśli backend (opcjonalnie) przekaże podpowiedź domyślnego sampla (items._default), próbujemy go użyć
  // - w przeciwnym razie losujemy element z listy (żeby nie zawsze brać pierwszy)
  //
  // ten efekt jest osobno względem pobierania danych, żeby zmiana selectedId
  // nie powodowała ponownego pobierania listy z serwera.
  useEffect(() => {
    if (!items || items.length === 0) return;
    if (selectedId) return;
    const dataDefault = (items as any)._default as SampleListItem | undefined; // opcjonalna podpowiedź z backendu (zwykle brak)
    const preferred = dataDefault && items.find(x => x.id === dataDefault.id);
    const fallback = preferred || (items.length > 0 ? items[Math.floor(Math.random() * items.length)] : undefined); // losowy wybór startowy
    if (fallback?.id) {
      onChange(instrument, fallback.id);
    }
  }, [items, selectedId, instrument, onChange]);

  // wyszukuje aktualnie wybrany obiekt sampla na podstawie selectedId.
  const current = useMemo(() => (items || []).find(x => x.id === selectedId) || null, [items, selectedId]);

  // wykorzystywane do podświetlenia sytuacji, gdy backend nie ma żadnych sampli dla instrumentu.
  const hasNoLocalSamples = !items || items.length === 0;

  return (
    <div className={`space-y-2 ${hasNoLocalSamples ? "border border-red-500/60 rounded-md p-2 bg-red-950/20" : ""}`}>
      <div className="flex items-center gap-2">
        <label className="text-[11px] text-gray-400">Sample</label>
        {loading && <span className="text-[11px] text-gray-500">loading…</span>}
        {error && <span className="text-[11px] text-red-400">{error}</span>}
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <select
          className={`bg-black/60 p-2 rounded border text-xs min-w-[200px] ${hasNoLocalSamples ? "border-red-500 text-red-300" : "border-gray-700"}`}
          value={selectedId ?? ""}
          onChange={e => onChange(instrument, e.target.value || null)}
        >
          {hasNoLocalSamples && (
            <option value="" className="text-red-400">(no local samples)</option>
          )}
          {(items || []).map(item => (
            <option key={item.id} value={item.id}>
              {item.name} {item.pitch ? `• ${item.pitch}` : ""} {item.subtype ? `• ${item.subtype}` : ""}
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
