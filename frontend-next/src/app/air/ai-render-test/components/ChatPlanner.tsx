import { memo, useCallback, type ChangeEventHandler } from 'react';
import type { ChatProviderInfo, DebugRun, ParamifyResultView } from '../types';

interface ChatPlannerProps {
  prompt: string;
  onPromptChange: (value: string) => void;
  providers: ChatProviderInfo[];
  provider: string;
  onProviderChange: (value: string) => void;
  models: string[];
  model: string;
  onModelChange: (value: string) => void;
  structured: boolean;
  onStructuredChange: (value: boolean) => void;
  onSend: () => void;
  onClear: () => void;
  loading: boolean;
  error: string | null;
  warnings: string[];
  reply: string | null;
  paramResult: ParamifyResultView | null;
  runId: string | null;
  onLoadDebug: () => void;
  debugData: DebugRun | null;
  prettyJson: (value: unknown) => string;
}

const ChatPlannerComponent = ({
  prompt,
  onPromptChange,
  providers,
  provider,
  onProviderChange,
  models,
  model,
  onModelChange,
  structured,
  onStructuredChange,
  onSend,
  onClear,
  loading,
  error,
  warnings,
  reply,
  paramResult,
  runId,
  onLoadDebug,
  debugData,
  prettyJson,
}: ChatPlannerProps) => {
  const handlePromptChange = useCallback<ChangeEventHandler<HTMLTextAreaElement>>(
    event => onPromptChange(event.target.value),
    [onPromptChange],
  );

  const handleModelInputChange = useCallback<ChangeEventHandler<HTMLInputElement>>(
    event => onModelChange(event.target.value),
    [onModelChange],
  );

  const handleModelSelectChange = useCallback<ChangeEventHandler<HTMLSelectElement>>(
    event => onModelChange(event.target.value),
    [onModelChange],
  );

  const handleProviderChange = useCallback<ChangeEventHandler<HTMLSelectElement>>(
    event => onProviderChange(event.target.value),
    [onProviderChange],
  );

  const handleStructuredChange = useCallback<ChangeEventHandler<HTMLInputElement>>(
    event => onStructuredChange(event.target.checked),
    [onStructuredChange],
  );

  return (
    <section className="bg-gray-900/70 border border-emerald-700/50 rounded-2xl shadow-lg shadow-emerald-900/20 p-6 space-y-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:gap-6">
        <div className="md:w-60 space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-widest text-emerald-300 mb-1">Provider</label>
            <select
              value={provider}
              onChange={handleProviderChange}
              className="w-full bg-black/60 border border-emerald-800/60 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {providers.map(item => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs uppercase tracking-widest text-emerald-300 mb-1">Model</label>
            {models.length > 0 ? (
              <select
                value={model}
                onChange={handleModelSelectChange}
                className="w-full bg-black/60 border border-emerald-800/60 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                {models.map(id => (
                  <option key={id} value={id}>{id}</option>
                ))}
              </select>
            ) : (
              <input
                value={model}
                onChange={handleModelInputChange}
                placeholder="np. gemini-2.5-flash"
                className="w-full bg-black/60 border border-emerald-800/60 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            )}
          </div>
          <label className="flex items-center gap-2 text-xs text-emerald-200 pt-1">
            <input
              type="checkbox"
              className="accent-emerald-500"
              checked={structured}
              onChange={handleStructuredChange}
            />
            Generuj parametry (JSON)
          </label>
        </div>
        <div className="flex-1 space-y-3">
          <div>
            <label className="block text-xs uppercase tracking-widest text-emerald-300 mb-1">Prompt</label>
            <textarea
              value={prompt}
              onChange={handlePromptChange}
              rows={structured ? 4 : 3}
              placeholder="Opisz docelowy utwór, np. 'kinowy, epicki motyw 90 BPM z chórem i perkusją'."
              className="w-full bg-black/60 border border-emerald-800/60 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onSend}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-sm font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? 'Ładowanie…' : structured ? 'Wygeneruj plan' : 'Wyślij wiadomość'}
            </button>
            <button
              type="button"
              onClick={onClear}
              className="px-3 py-2 rounded-lg border border-emerald-800/60 text-xs uppercase tracking-widest text-emerald-200"
            >
              Wyczyść
            </button>
            {runId && (
              <button
                type="button"
                onClick={onLoadDebug}
                className="px-3 py-2 rounded-lg border border-purple-700/60 text-xs uppercase tracking-widest text-purple-200 hover:bg-purple-900/40"
              >
                Debug run
              </button>
            )}
            {reply && !structured && (
              <span className="text-xs text-emerald-300">Odpowiedź dostępna poniżej</span>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-800/70 text-red-200 text-sm rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      {warnings.length > 0 && (
        <div className="bg-amber-900/20 border border-amber-700/60 text-amber-200 text-xs rounded-xl px-4 py-3 space-y-1">
          {warnings.map((warning, idx) => (
            <div key={idx}>• {warning}</div>
          ))}
        </div>
      )}

      {paramResult && (
        <div className="bg-black/50 border border-emerald-800/60 rounded-2xl px-4 py-4 space-y-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2 text-emerald-200">
            <span>
              Źródło: {paramResult.provider ?? provider} / {paramResult.model ?? (model || 'domyślny')}
            </span>
            {runId && <span className="font-mono text-emerald-300">run: {runId}</span>}
          </div>
          {paramResult.errors && paramResult.errors.length > 0 && (
            <div className="bg-red-900/20 border border-red-800/70 text-red-200 rounded-xl px-3 py-2 space-y-1">
              {paramResult.errors.map((err, idx) => (
                <div key={idx}>⚠ {err}</div>
              ))}
            </div>
          )}
          {paramResult.raw && (
            <details className="bg-gray-900/40 rounded-xl px-3 py-2" open>
              <summary className="cursor-pointer text-emerald-300">Surowa odpowiedź modelu</summary>
              <pre className="mt-2 whitespace-pre-wrap break-words">{paramResult.raw}</pre>
            </details>
          )}
          {paramResult.parsed && (
            <details className="bg-gray-900/40 rounded-xl px-3 py-2">
              <summary className="cursor-pointer text-emerald-300">Parsed JSON (po stronie backendu)</summary>
              <pre className="mt-2 whitespace-pre-wrap break-words">{prettyJson(paramResult.parsed)}</pre>
            </details>
          )}
          {paramResult.normalized && (paramResult.normalized.midi || paramResult.normalized.audio) && (
            <details className="bg-gray-900/40 rounded-xl px-3 py-2">
              <summary className="cursor-pointer text-emerald-300">Znormalizowane dane (backend)</summary>
              <pre className="mt-2 whitespace-pre-wrap break-words">{prettyJson(paramResult.normalized)}</pre>
            </details>
          )}
          {paramResult.applied && (paramResult.applied.midi || paramResult.applied.audio) && (
            <details className="bg-gray-900/40 rounded-xl px-3 py-2" open>
              <summary className="cursor-pointer text-emerald-300">Zastosowane w formularzu</summary>
              {paramResult.applied.midi && (
                <div className="mt-2">
                  <div className="text-emerald-200 mb-1">MIDI</div>
                  <pre className="whitespace-pre-wrap break-words">{prettyJson(paramResult.applied.midi)}</pre>
                </div>
              )}
              {paramResult.applied.audio && (
                <div className="mt-3">
                  <div className="text-emerald-200 mb-1">Audio</div>
                  <pre className="whitespace-pre-wrap break-words">{prettyJson(paramResult.applied.audio)}</pre>
                </div>
              )}
            </details>
          )}
        </div>
      )}

      {reply && !structured && (
        <div className="bg-black/50 border border-blue-800/70 rounded-2xl px-4 py-4 text-sm whitespace-pre-wrap">
          {reply}
        </div>
      )}

      {debugData && (
        <details className="bg-black/40 border border-purple-800/70 rounded-2xl px-4 py-3 text-xs">
          <summary className="cursor-pointer text-purple-200">Debug timeline ({runId})</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words">{prettyJson(debugData)}</pre>
        </details>
      )}
    </section>
  );
};

export const ChatPlanner = memo(ChatPlannerComponent);
