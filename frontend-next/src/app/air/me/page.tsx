"use client";

// „twoje audio”: lista projektów użytkownika zapisanych w backendzie.
// użytkownik może:
// - odsłuchać mix i stemsy,
// - podejrzeć prompt i parametry,
// - zmienić nazwę / usunąć,
// - pobrać pliki (mix albo cały eksport).

import { useEffect, useMemo, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { SimpleAudioPlayer } from "../step-components/SimpleAudioPlayer";
import { VisualAudioPlayer } from "../step-components/VisualAudioPlayer";
import ParticleText from "@/components/ui/ParticleText";
import ElectricBorder from "@/components/ui/ElectricBorder";
import { getApiBaseUrl } from "@/lib/apiBase";

const API_BASE = getApiBaseUrl();
const API_PREFIX = "/api";

type RenderResult = {
  project_name: string;
  run_id: string;
  mix_wav_rel: string;
  stems: { instrument: string; audio_rel: string }[];
  sample_rate: number;
  duration_seconds?: number | null;
};

type UserProjectItem = RenderResult & {
  project_id?: number;
  created_at?: string | null;
  param_run_id?: string | null;
  prompt?: string | null;
  param_meta?: any | null;
  midi_meta?: any | null;
  selected_samples?: Record<string, string> | null;
  selected_samples_info?: Record<
    string,
    {
      id: string;
      name: string;
      url?: string | null;
      pitch?: string | null;
      subtype?: string | null;
      family?: string | null;
      category?: string | null;
    }
  > | null;
};

type ExportManifest = {
  render_run_id: string;
  midi_run_id?: string | null;
  param_run_id?: string | null;
  files: { step: string; rel_path: string; url: string; bytes?: number | null }[];
  missing: string[];
};

function useBackendAudioBase(): string {
  return useMemo(() => {
    return `${API_BASE}/api/audio/`;
  }, []);
}

function useResolveRenderUrl() {
  const backendAudioBase = useBackendAudioBase();
  return (rel: string) => {
    if (!rel) return backendAudioBase;
    // backend w niektórych miejscach zwraca ścieżki „windowsowe” typu output\....
    // tu odcinamy prefix do folderu output i budujemy url do /api/audio/.
    const markerBack = "output\\";
    const markerFwd = "output/";
    let idx = rel.indexOf(markerBack);
    let marker = markerBack;
    if (idx < 0) {
      idx = rel.indexOf(markerFwd);
      marker = markerFwd;
    }
    const tailRaw = idx >= 0 ? rel.slice(idx + marker.length) : rel;
    const tail = String(tailRaw).replace(/\\/g, "/").replace(/^\//, "");
    return `${backendAudioBase}${tail}`;
  };
}

function formatCreatedAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return new Intl.DateTimeFormat("pl-PL", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return String(iso);
  }
}

function extractPrompt(item: any): string | null {
  try {
    const direct = item?.prompt;
    if (typeof direct === "string" && direct.trim()) return direct.trim();
    const pm = item?.param_meta;
    const fromParam = pm?.user_prompt ?? pm?.prompt;
    if (typeof fromParam === "string" && fromParam.trim()) return fromParam.trim();
  } catch {
    // ignorujemy: tu tylko „best effort” wydobycia prompta z różnych struktur.
  }
  return null;
}

export default function UserProjectsPage() {
  const { data: session, status } = useSession();
  const [items, setItems] = useState<UserProjectItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingAllRunId, setDownloadingAllRunId] = useState<string | null>(null);
  const resolveRenderUrl = useResolveRenderUrl();

  const refresh = async (userId: number | string) => {
    setLoading(true);
    setError(null);
    try {
      const url = `${API_BASE}${API_PREFIX}/air/user-projects/by-user?user_id=${encodeURIComponent(
        String(userId),
      )}`;
      const res = await fetch(url);
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      setItems(Array.isArray(data) ? (data as UserProjectItem[]) : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (status !== "authenticated") return;
    const id = (session?.user as any)?.id;
    if (!id) return;

    let cancelled = false;
    (async () => {
      try {
        await refresh(id);
      } catch {
        // błędy już obsługiwane w refresh
      }
      if (cancelled) return;
    })();

    return () => {
      cancelled = true;
    };
  }, [session, status]);

  const handleRename = async (item: UserProjectItem) => {
    const projectId = item.project_id;
    if (!projectId) return;
    const next = window.prompt("Nowa nazwa projektu", item.project_name || "");
    if (!next || !next.trim()) return;
    try {
      const url = `${API_BASE}${API_PREFIX}/air/user-projects/rename?project_id=${projectId}&name=${encodeURIComponent(
        next.trim(),
      )}`;
      const res = await fetch(url, { method: "PATCH" });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      setItems(prev =>
        prev.map(p => (p.run_id === item.run_id && p.project_id === item.project_id ? { ...p, project_name: next.trim() } : p)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDelete = async (item: UserProjectItem) => {
    const projectId = item.project_id;
    if (!projectId) return;
    if (!window.confirm("Na pewno usunąć ten projekt?")) return;
    try {
      const url = `${API_BASE}${API_PREFIX}/air/user-projects/delete?project_id=${projectId}`;
      const res = await fetch(url, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      setItems(prev => prev.filter(p => !(p.run_id === item.run_id && p.project_id === item.project_id)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // helper do pobierania pojedynczego pliku.
  // używamy blob + tymczasowego linka, żeby wymusić download (a nie nawigację).
  const downloadFile = useCallback(async (url: string, filename: string): Promise<boolean> => {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
      return true;
    } catch (e) {
      console.error('Download failed:', e);
      setError(`Błąd pobierania ${filename}: ${e instanceof Error ? e.message : String(e)}`);
      return false;
    }
  }, []);

  // pobieranie „wszystkiego” dla projektu:
  // - preferujemy 1 plik zip,
  // - jeśli zip jest niedostępny, bierzemy manifest i ściągamy pliki po kolei.
  const downloadAll = useCallback(async (item: UserProjectItem) => {
    const projectNameClean = (item.project_name || 'projekt').replace(/[^a-zA-Z0-9_-]/g, '_');
    setError(null);

    try {
      setDownloadingAllRunId(item.run_id);

      // 1) preferujemy zip (jedno pobranie)
      const zipUrl = `${API_BASE}${API_PREFIX}/air/export/zip/${encodeURIComponent(item.run_id)}`;
      const zipRes = await fetch(zipUrl);
      if (zipRes.ok) {
        const blob = await zipRes.blob();
        const blobUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = `${projectNameClean}__export.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);
        return;
      }

      // 2) wariant awaryjny: pobieranie na podstawie manifestu
      const url = `${API_BASE}${API_PREFIX}/air/export/list/${encodeURIComponent(item.run_id)}`;
      const res = await fetch(url);
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail?.message || data?.detail || `HTTP ${res.status}`);
      }

      const manifest = data as ExportManifest;
      const files = Array.isArray(manifest?.files) ? manifest.files : [];
      if (!files.length) {
        throw new Error('Brak plików do pobrania (manifest pusty).');
      }

      for (const f of files) {
        if (!f?.url) continue;
        const basename = String(f.rel_path || '').split('/').pop() || 'file';
        const step = String(f.step || 'step').replace(/[^a-zA-Z0-9_-]/g, '_');
        const filename = `${projectNameClean}__${step}__${basename}`;
        const fileUrl = String(f.url).startsWith('http') ? String(f.url) : `${API_BASE}${f.url}`;
        await downloadFile(fileUrl, filename);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloadingAllRunId(prev => (prev === item.run_id ? null : prev));
    }
  }, [downloadFile]);

  if (status === "loading") {
    return (
      <section className="min-h-screen bg-black/90 flex items-center justify-center">
        <div className="text-sm text-cyan-300 animate-pulse">Ładowanie sesji…</div>
      </section>
    );
  }

  if (status !== "authenticated") {
    return (
      <section className="min-h-screen bg-black/90 flex items-center justify-center">
        <div className="bg-gray-900/40 border border-cyan-700/40 rounded-2xl shadow-lg shadow-cyan-900/10 p-8 text-center space-y-4">
          <div className="text-cyan-400 text-lg font-semibold">Brak dostępu</div>
          <p className="text-sm text-gray-400">Zaloguj się, aby zobaczyć swoje projekty.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="min-h-screen bg-black/0 p-6 md:p-10">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* nagłówek z particletext */}
        <div className="bg-gray-900/10 border border-cyan-700/30 rounded-2xl shadow-lg shadow-cyan-900/10 p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-cyan-900/5 to-transparent pointer-events-none" />

          <div className="relative z-10 space-y-4">
            {/* ParticleText Header */}
            <div className="h-24 md:h-32 w-full">
              <ParticleText
                text="TWOJE AUDIO"
                colors={["#ffffff"]}
                font="bold 66px system-ui"
                particleSize={2}
                mouseRadius={20}
                mouseStrength={25}
              />
            </div>

            <p className="text-sm text-gray-400 max-w-2xl text-center mx-auto">
              Lista Twoich projektów wyrenderowanych w <span className="text-cyan-100/70"> aplikacji AIR 4.2</span>.
              Możesz sobie nimi tu zarządzać. Możesz je edytować, usuwać i pobierać. Możesz też kompletnie nic z nimi nie robić.
            </p>
          </div>
        </div>

        {/* stan ładowania */}
        {loading && (
          <div className="bg-black/40 border border-cyan-800/30 rounded-xl p-6 text-center">
            <div className="flex items-center justify-center gap-3">
              <div className="w-5 h-5 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-cyan-300">Ładowanie projektów…</span>
            </div>
          </div>
        )}

        {/* stan błędu */}
        {error && (
          <div className="bg-cyan-900/30 border border-cyan-800/70 text-cyan-200 text-sm rounded-xl px-4 py-3 flex items-center gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-cyan-400 shrink-0">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        )}

        {/* pusty stan */}
        {!loading && !error && items.length === 0 && (
          <div className="bg-gray-900/40 border border-cyan-800/30 rounded-2xl p-8 text-center space-y-4">
            <div className="text-cyan-500 mx-auto">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-16 h-16 mx-auto opacity-50">
                <path fillRule="evenodd" d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V9.017 5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="text-gray-400 text-sm">
              Nie masz jeszcze żadnych zapisanych renderów.
            </div>
            <p className="text-xs text-gray-500">
              Stwórz swój pierwszy utwór w module AIR, aby zobaczyć go tutaj.
            </p>
          </div>
        )}

        {/* lista projektów */}
        {!loading && items.length > 0 && (
          <div className="bg-gray-900/40 border border-cyan-700/40 rounded-2xl shadow-lg shadow-cyan-900/10 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-cyan-900/40 pb-3">
              <div className="text-cyan-300 text-xs uppercase tracking-widest font-semibold">
                Twoje projekty ({items.length})
              </div>
              <div className="text-[10px] text-gray-500">
                Kliknij na projekt, aby rozwinąć szczegóły
              </div>
            </div>

            <div className="space-y-3 max-h-[65vh] overflow-y-auto pr-2 scroll-container-red">
              {items.map((item, idx) => (
                <div
                  key={`${item.run_id}-${idx}`}
                  className="border border-cyan-800/30 rounded-xl bg-black/40 hover:bg-black/50 transition-all duration-300 overflow-hidden group"
                >
                  {/* nagłówek kafelka projektu */}
                  <div className="px-4 py-3 flex items-center justify-between gap-4 border-b border-cyan-900/20">
                    <div className="flex items-center gap-3 min-w-0">
                      {/* <div className="w-3 h-3 rounded-full bg-blue-500 shadow-lg shadow-cyan-500/50 animate-pulse shrink-0" /> */}
                      <div className="min-w-0">
                        <div className="font-semibold text-cyan-200 text-sm truncate">
                          {item.project_name || "Bez nazwy"}
                        </div>
                        <div className="flex gap-3 text-[10px] text-gray-500">
                          <span className="font-mono">ID: {item.project_id}</span>
                          {formatCreatedAt(item.created_at) && (
                            <span className="bg-cyan-900/30 px-1.5 py-0.5 rounded text-cyan-300">
                              {formatCreatedAt(item.created_at)}
                            </span>
                          )}
                          {typeof item.duration_seconds === "number" && item.duration_seconds > 0 && (
                            <span className="bg-cyan-900/30 px-1.5 py-0.5 rounded text-cyan-400">
                              {item.duration_seconds.toFixed(1)}s
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* przyciski akcji */}
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => downloadFile(resolveRenderUrl(item.mix_wav_rel), `${(item.project_name || 'projekt').replace(/[^a-zA-Z0-9_-]/g, '_')}_mix.wav`)}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-medium text-cyan-300 bg-cyan-900/30 hover:bg-cyan-800/40 border border-cyan-700/40 hover:border-cyan-600/60 rounded-lg transition-all duration-200 hover:scale-105"
                        title="Pobierz mix"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                          <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                          <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
                        </svg>
                        Mix
                      </button>
                      <button
                        type="button"
                        onClick={() => downloadAll(item)}
                        disabled={downloadingAllRunId === item.run_id}
                        className={`flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-medium text-white bg-gradient-to-r from-cyan-600/60 to-sky-600/60 hover:from-cyan-500/70 hover:to-sky-500/70 border border-cyan-500/40 hover:border-cyan-400/60 rounded-lg transition-all duration-200 shadow-sm shadow-cyan-900/20 ${downloadingAllRunId === item.run_id ? 'opacity-60 cursor-not-allowed' : 'hover:scale-105'}`}
                        title="Pobierz wszystko"
                      >
                        {downloadingAllRunId === item.run_id ? (
                          <>
                            <div className="w-3.5 h-3.5 border-2 border-white/70 border-t-transparent rounded-full animate-spin" />
                            Pobieranie…
                          </>
                        ) : (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                              <path fillRule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm0 10.5a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75zM2 10a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5h-7.5A.75.75 0 012 10z" clipRule="evenodd" />
                            </svg>
                            Wszystko
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRename(item)}
                        className="px-2.5 py-1.5 rounded-lg bg-gray-800/60 hover:bg-gray-700/60 text-[10px] text-gray-300 hover:text-white transition-all duration-200 border border-gray-700/40 hover:border-gray-600/60"
                        title="Zmień nazwę"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                          <path d="M2.695 14.763l-1.262 3.154a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.343z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(item)}
                        className="px-2.5 py-1.5 rounded-lg bg-cyan-900/40 hover:bg-cyan-800/60 text-[10px] text-cyan-300 hover:text-cyan-100 transition-all duration-200 border border-cyan-800/40 hover:border-cyan-700/60"
                        title="Usuń projekt"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                          <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* odsłuch mixu */}
                  <div className="px-4 py-4 bg-blue-900/20">
                    <VisualAudioPlayer
                      src={resolveRenderUrl(item.mix_wav_rel)}
                      title={item.project_name || "Mix"}
                      accentColor="#a9f8ffff"
                      accentColor2="#0800ffff"
                      className="w-full"
                    />
                  </div>

                  {/* prompt (jeśli da się go wydobyć z meta) */}
                  <details className="group border-t border-cyan-900/20">
                    <summary className="cursor-pointer px-4 py-2.5 text-[11px] text-cyan-400/70 hover:text-cyan-300 transition-colors select-none flex items-center gap-2">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 transition-transform group-open:rotate-90">
                        <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                      </svg>
                      Prompt
                    </summary>
                    <div className="px-4 pb-4 pt-1 border-l-2 border-cyan-900/30 ml-4">
                      {extractPrompt(item) ? (
                        <div className="text-[11px] text-gray-200 whitespace-pre-wrap break-words">
                          {extractPrompt(item)}
                        </div>
                      ) : (
                        <div className="text-[11px] text-gray-500">
                          Brak zapisanego prompta dla tego projektu.
                        </div>
                      )}
                    </div>
                  </details>

                  {/* parametry (skrót + pełny json) */}
                  <details className="group border-t border-cyan-900/20">
                    <summary className="cursor-pointer px-4 py-2.5 text-[11px] text-cyan-400/70 hover:text-cyan-300 transition-colors select-none flex items-center gap-2">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 transition-transform group-open:rotate-90">
                        <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                      </svg>
                      Parametry
                    </summary>
                    <div className="px-4 pb-4 pt-1 border-l-2 border-cyan-900/30 ml-4 space-y-3">
                      {item.param_run_id && (
                        <div className="text-[10px] text-gray-500">param_run_id: <span className="font-mono text-gray-300">{item.param_run_id}</span></div>
                      )}

                      {/* skrót meta: preferujemy param_meta, a jeśli brak to midi_meta */}
                      {(() => {
                        const meta = item.param_meta || item.midi_meta;
                        if (!meta) return null;
                        return (
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1 text-[11px] text-gray-300">
                            {typeof meta.style === 'string' && <div><span className="text-gray-500">Style:</span> {meta.style}</div>}
                            {typeof meta.mood === 'string' && <div><span className="text-gray-500">Mood:</span> {meta.mood}</div>}
                            {typeof meta.tempo === 'number' && <div><span className="text-gray-500">Tempo:</span> {meta.tempo}</div>}
                            {typeof meta.key === 'string' && <div><span className="text-gray-500">Key:</span> {meta.key}</div>}
                            {typeof meta.scale === 'string' && <div><span className="text-gray-500">Scale:</span> {meta.scale}</div>}
                            {typeof meta.meter === 'string' && <div><span className="text-gray-500">Meter:</span> {meta.meter}</div>}
                            {typeof meta.bars === 'number' && <div><span className="text-gray-500">Bars:</span> {meta.bars}</div>}
                            {typeof meta.length_seconds === 'number' && <div><span className="text-gray-500">Len:</span> {meta.length_seconds}s</div>}
                          </div>
                        );
                      })()}

                      {/* instrumenty */}
                      {(() => {
                        const meta = item.param_meta || item.midi_meta;
                        const instruments = meta?.instruments;
                        if (!Array.isArray(instruments) || instruments.length === 0) return null;
                        return (
                          <div className="text-[11px] text-gray-300">
                            <div className="text-[10px] uppercase tracking-widest text-cyan-300/80 mb-1">Instrumenty</div>
                            <div className="text-gray-200">{instruments.join(", ")}</div>
                          </div>
                        );
                      })()}

                      {/* wybrane sample (nazwy) */}
                      {item.selected_samples_info && Object.keys(item.selected_samples_info).length > 0 && (
                        <div className="text-[11px] text-gray-300">
                          <div className="text-[10px] uppercase tracking-widest text-cyan-300/80 mb-1">Wybrane sample</div>
                          <div className="space-y-1">
                            {Object.entries(item.selected_samples_info).map(([inst, info]) => (
                              <div key={inst} className="flex flex-wrap gap-2 items-center">
                                <span className="text-gray-200 font-semibold">{inst}:</span>
                                <span className="text-gray-100">{info?.name || info?.id}</span>
                                {info?.pitch && <span className="text-[10px] text-gray-500">• {info.pitch}</span>}
                                {info?.subtype && <span className="text-[10px] text-gray-500">• {info.subtype}</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* pełny json (zawsze widoczny w panelu) */}
                      <div className="bg-black/20 border border-cyan-900/30 rounded-lg px-3 py-2">
                        <div className="text-[10px] text-cyan-300/70">Pełna lista parametrów (JSON)</div>
                        <pre className="mt-2 whitespace-pre-wrap break-words text-[10px] max-h-72 overflow-auto bg-black/40 rounded-lg px-2 py-2 border border-cyan-900/40 text-gray-200">{JSON.stringify(item.param_meta || item.midi_meta || {}, null, 2)}</pre>
                      </div>
                    </div>
                  </details>

                  {/* stemsy: osobne ścieżki per instrument */}
                  {item.stems.length > 0 && (
                    <details className="group border-t border-cyan-900/20">
                      <summary className="cursor-pointer px-4 py-2.5 text-[11px] text-cyan-400/70 hover:text-cyan-300 transition-colors select-none flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 transition-transform group-open:rotate-90">
                          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                        </svg>
                        Pokaż {item.stems.length} osobnych ścieżek (stems)
                      </summary>
                      <div className="px-4 pb-4 space-y-2 border-l-2 border-cyan-900/30 ml-4">
                        {item.stems.map(stem => (
                          <div key={`${stem.instrument}-${stem.audio_rel}`} className="space-y-1 pt-2">
                            <div className="text-[10px] text-gray-300 font-medium flex items-center gap-2">
                              {/* <span className="w-1.5 h-1.5 bg-cyan-500/60 rounded-full" /> */}
                              {stem.instrument}
                            </div>
                            <SimpleAudioPlayer
                              src={resolveRenderUrl(stem.audio_rel)}
                              className="w-full"
                              height={32}
                              variant="compact"
                            />
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      </div>

      {/* globalne style scrollbara dla tej listy (webkity) */}
      <style jsx global>{`
        .scroll-container-red::-webkit-scrollbar {
          width: 6px;
        }
        .scroll-container-red::-webkit-scrollbar-track {
          background: rgba(0, 0, 0, 0.3);
          border-radius: 3px;
        }
        .scroll-container-red::-webkit-scrollbar-thumb {
          background: rgba(239, 68, 68, 0.4);
          border-radius: 3px;
        }
        .scroll-container-red::-webkit-scrollbar-thumb:hover {
          background: rgba(239, 68, 68, 0.6);
        }
      `}</style>
    </section>
  );
}
