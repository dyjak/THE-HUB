"use client";

import { useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { SimpleAudioPlayer } from "../step-components/SimpleAudioPlayer";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
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
  // W API rename/delete operujemy po ID z tabeli projs
  project_id?: number;
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
    const marker = "output\\";
    const idx = rel.indexOf(marker);
    const tail = idx >= 0 ? rel.slice(idx + marker.length) : rel;
    return `${backendAudioBase}${tail}`;
  };
}

export default function UserProjectsPage() {
  const { data: session, status } = useSession();
  const [items, setItems] = useState<UserProjectItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  if (status === "loading") {
    return <div className="p-6 text-sm text-gray-300">Ładowanie sesji…</div>;
  }

  if (status !== "authenticated") {
    return <div className="p-6 text-sm text-gray-300">Zaloguj się, aby zobaczyć swoje projekty.</div>;
  }

  return (
    <section className="p-6 space-y-4">
      <h1 className="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400">
        Moje projekty
      </h1>
      <p className="text-xs text-gray-400 max-w-2xl">
        Lista ostatnich projektów wyrenderowanych w module AIR. Dane pochodzą z bazy (tabela
        projs) i zapisanych stanów renderu.
      </p>

      {loading && <div className="text-xs text-gray-400">Ładowanie projektów…</div>}
      {error && (
        <div className="text-xs text-red-300 bg-red-900/30 border border-red-800/70 rounded-xl px-3 py-2">
          {error}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="text-xs text-gray-400 border border-gray-800 rounded-xl px-4 py-3 bg-black/40">
          Nie masz jeszcze żadnych zapisanych renderów.
        </div>
      )}

      <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1 text-xs">
        {items.map((item, idx) => (
          <div
            key={`${item.run_id}-${idx}`}
            className="border border-purple-800/40 rounded-xl px-3 py-2 bg-black/40 space-y-2"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex flex-col gap-1">
                <div className="font-semibold text-purple-200 text-[11px]">
                  {item.project_name || "Bez nazwy"}
                </div>
                <div className="flex gap-2 text-[10px] text-gray-500">
                  <span>run_id: {item.run_id}</span>
                  {typeof item.project_id === "number" && <span>ID: {item.project_id}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                <button
                  type="button"
                  onClick={() => handleRename(item)}
                  className="px-2 py-1 rounded bg-purple-700/60 hover:bg-purple-600 text-xs"
                >
                  Zmień nazwę
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(item)}
                  className="px-2 py-1 rounded bg-red-700/60 hover:bg-red-600 text-xs"
                >
                  Usuń
                </button>
              </div>
            </div>
            {typeof item.duration_seconds === "number" && item.duration_seconds > 0 && (
              <div className="text-[10px] text-gray-400">{item.duration_seconds.toFixed(1)} s</div>
            )}
            <div className="space-y-1">
              <div className="text-[11px] text-gray-300 mb-1">Mix</div>
              <SimpleAudioPlayer
                src={resolveRenderUrl(item.mix_wav_rel)}
                className="w-full"
                height={36}
                variant="compact"
              />
            </div>
            {item.stems.length > 0 && (
              <div className="space-y-1">
                <div className="mt-1 text-gray-400 text-[11px]">Stemy</div>
                <ul className="pl-3 space-y-1">
                  {item.stems.map(stem => (
                    <li key={`${stem.instrument}-${stem.audio_rel}`} className="space-y-0.5">
                      <div className="text-[11px] text-gray-300">{stem.instrument}</div>
                      <SimpleAudioPlayer
                        src={resolveRenderUrl(stem.audio_rel)}
                        className="w-full"
                        height={32}
                        variant="compact"
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
