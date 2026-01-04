"use client";

/*
  uniwersalny dialog do pokazywania problemów/ostrzeżeń w krokach air.

  co robi:
  - pokazuje tytuł, opis i listę szczegółów (np. błędy parsowania, braki plików eksportu)
  - opcjonalnie pozwala zmienić provider/model, gdy komponent rodzica przekaże listy oraz callbacki
  - ma dwa wyjścia: "kontynuuj" (zamknij) oraz "ponów generowanie" (wywołaj akcję w rodzicu)

  uwaga:
  - to jest komponent prezentacyjny; logika generowania jest w krokach (np. ParamPlanStep, MidiPlanStep)
*/

import type { ReactNode } from "react";

type Props = {
  open: boolean;
  title: string;
  description?: string | null;
  details?: string[] | null;
  accentClassName?: string;
  retryClassName?: string;
  provider?: string | null;
  model?: string | null;
  availableProviders?: { id: string; name?: string }[] | null;
  onProviderChange?: (nextProvider: string) => void;
  availableModels?: string[] | null;
  onModelChange?: (nextModel: string) => void;
  onContinue: () => void;
  onRetry: () => void;
};

export default function ProblemDialog({
  open,
  title,
  description,
  details,
  accentClassName,
  retryClassName,
  provider,
  model,
  availableProviders,
  onProviderChange,
  availableModels,
  onModelChange,
  onContinue,
  onRetry,
}: Props) {
  if (!open) return null;

  // filtrujemy wejściowe dane defensywnie, bo czasem backend/model może zwrócić nieoczekiwany typ.
  const items = Array.isArray(details) ? details.filter((x) => typeof x === "string" && x.trim()) : [];

  // normalizacja providerów i modeli jest po to, żeby:
  // - nie mieć duplikatów w selectach
  // - nie wywalić reacta przez niepoprawne key lub puste wartości
  const providers = Array.isArray(availableProviders)
    ? Array.from(
        new Map(
          availableProviders
            .filter((p) => p && typeof p.id === "string" && p.id.trim())
            .map((p) => [p.id, { id: p.id, name: p.name }]),
        ).values(),
      )
    : [];
  const models = Array.isArray(availableModels)
    ? Array.from(new Set(availableModels.filter((m) => typeof m === "string" && m.trim())))
    : [];
  const canChangeProvider = typeof onProviderChange === "function";
  const canChangeModel = typeof onModelChange === "function";
  const canChangeAny = canChangeProvider || canChangeModel;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className={`bg-gray-900 border rounded-2xl p-5 max-w-lg w-[92vw] shadow-xl ${accentClassName || "border-gray-600"}`}>
        <div className="flex items-start gap-3">
          <span className="mt-0.5 inline-flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-black text-xs font-extrabold">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l6.518 11.59c.75 1.334-.213 2.99-1.742 2.99H3.48c-1.53 0-2.492-1.656-1.743-2.99l6.52-11.59zM11 14a1 1 0 10-2 0 1 1 0 002 0zm-1-8a1 1 0 00-1 1v4a1 1 0 102 0V7a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </span>
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-widest text-red-200/90">Błąd</div>
            <div className="text-sm font-semibold text-gray-100 animate-pulse leading-snug break-words">{title}</div>
          </div>
        </div>
        {description ? (
          <p className="text-xs text-gray-300 mt-2 leading-relaxed">{description}</p>
        ) : null}

        {(provider || model) && (
          <div className="mt-3 bg-black/30 border border-gray-800/70 rounded-xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-gray-400 mb-2">Model</div>
            <div className="text-[11px] text-gray-200 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
              <div>
                <span className="text-gray-400">Provider:</span> <span className="text-gray-100">{provider || "(brak)"}</span>
              </div>
              <div>
                <span className="text-gray-400">Model:</span> <span className="text-gray-100">{model || "(brak)"}</span>
              </div>
            </div>
            <div className="mt-2 text-[11px] text-gray-300 leading-relaxed">
              Czasem model nie trzyma się narzuconej struktury JSON. Problem może występować częściej w przypadku słabszych modeli.
              Więcej informacji znajdziesz w dokumentacji.
            </div>

            {canChangeAny && (
              <details className="mt-3 pt-3 border-t border-gray-800/70">
                <summary className="cursor-pointer text-[11px] text-gray-200 hover:text-gray-100 transition-colors">
                  Zaawansowane: zmień provider/model
                </summary>
                <div className="mt-3 space-y-3">
                  {canChangeProvider && (
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-gray-400 mb-2">Provider</div>
                      {providers.length > 0 ? (
                        <div className="relative">
                          <select
                            value={provider || ""}
                            onChange={(e) => onProviderChange(e.target.value)}
                            className="appearance-none w-full bg-black/40 border border-gray-700/60 rounded-lg pr-9 px-3 py-2 text-[11px] text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300/30 focus:border-gray-400"
                          >
                            {providers.map((p) => {
                              const isOpenAI = (p.id || "").toLowerCase() === "openai";
                              return (
                                <option key={p.id} value={p.id} disabled={isOpenAI}>
                                  {p.name || p.id}{isOpenAI ? " (disabled)" : ""}
                                </option>
                              );
                            })}
                          </select>
                          <svg
                            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-300 opacity-70"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path
                              fillRule="evenodd"
                              d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </div>
                      ) : (
                        <input
                          value={provider || ""}
                          onChange={(e) => onProviderChange(e.target.value)}
                          placeholder="np. gemini"
                          className="w-full bg-black/40 border border-gray-700/60 rounded-lg px-3 py-2 text-[11px] text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300/30 focus:border-gray-400"
                        />
                      )}
                    </div>
                  )}

                  {canChangeModel && (
                    <div>
                      <div className="text-[10px] uppercase tracking-widest text-gray-400 mb-2">Model</div>
                      {models.length > 0 ? (
                        <div className="relative">
                          <select
                            value={model || ""}
                            onChange={(e) => onModelChange(e.target.value)}
                            className="appearance-none w-full bg-black/40 border border-gray-700/60 rounded-lg pr-9 px-3 py-2 text-[11px] text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300/30 focus:border-gray-400"
                          >
                            {models.map((m) => (
                              <option key={m} value={m}>
                                {m}
                              </option>
                            ))}
                          </select>
                          <svg
                            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-300 opacity-70"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path
                              fillRule="evenodd"
                              d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.08 1.04l-4.25 4.25a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </div>
                      ) : (
                        <input
                          value={model || ""}
                          onChange={(e) => onModelChange(e.target.value)}
                          placeholder="np. gemini-2.5-flash"
                          className="w-full bg-black/40 border border-gray-700/60 rounded-lg px-3 py-2 text-[11px] text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300/30 focus:border-gray-400"
                        />
                      )}
                    </div>
                  )}

                  <div className="text-[11px] text-gray-400">Po zmianie kliknij „Ponów generowanie”.</div>
                </div>
              </details>
            )}
          </div>
        )}

        {items.length > 0 && (
          <div className="mt-3 bg-black/30 border border-gray-800/70 rounded-xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-gray-400 mb-2">Szczegóły</div>
            <div className="space-y-1 text-[11px] text-gray-200 max-h-40 overflow-auto">
              {items.map((d, i) => (
                <div key={`${i}-${d}`} className="leading-relaxed">
                  • {d}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2 mt-4 text-xs">
          <button
            type="button"
            onClick={onContinue}
            className="px-3 py-1.5 rounded-lg border border-gray-600 text-gray-200 hover:bg-gray-800/60"
          >
            Kontynuuj
          </button>
          <button
            type="button"
            onClick={onRetry}
            className={`px-3 py-1.5 rounded-lg text-white font-semibold ${retryClassName || "bg-red-700 hover:bg-red-600"}`}
          >
            Ponów generowanie
          </button>
        </div>
      </div>
    </div>
  );
}
