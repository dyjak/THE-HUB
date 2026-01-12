"use client";
import { useEffect, useState } from "react";
import { ChatMidiComposer } from "../components/ChatMidiComposer";
import { DEFAULT_MIDI, cloneMidi, normalizeMidi, normalizeAudio } from "../utils";
import type { MidiParameters, AudioRenderParameters, ChatProviderInfo, ParamifyNormalizedPlan } from "../types";
import { getApiBaseUrl } from '@/lib/apiBase';

const API_BASE = getApiBaseUrl();
const API_PREFIX = "/api";
const MODULE_PREFIX = "/ai-render-test";

export default function ChatSmokePage() {
  const [prompt, setPrompt] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providers, setProviders] = useState<ChatProviderInfo[]>([]);
  const [provider, setProvider] = useState<string>("gemini");
  const [model, setModel] = useState<string>("");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [structured, setStructured] = useState<boolean>(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [debugData, setDebugData] = useState<any | null>(null);
  const [midi, setMidi] = useState<MidiParameters>(() => cloneMidi(DEFAULT_MIDI));
  const [audio, setAudio] = useState<AudioRenderParameters | null>(null);
  const [hasPlan, setHasPlan] = useState<boolean>(false);
  const [planWarnings, setPlanWarnings] = useState<string[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/providers`);
        const data = await res.json();
        const list = data?.providers || [];
        setProviders(list);
        if (list.length && !provider) {
          setProvider(list[0].id);
          setModel(list[0].default_model);
        }
      } catch {}
    };
    load();
  }, []);

  useEffect(() => {
    const loadModels = async () => {
      if (!provider) return;
      try {
        const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/models/${provider}`);
        const data = await res.json();
        const models = data?.models || [];
        setAvailableModels(models);
        if (!model && models.length) setModel(models[0]);
      } catch {
        setAvailableModels([]);
      }
    };
    loadModels();
  }, [provider]);

  const send = async () => {
    setLoading(true); setError(null); setReply(null); setRunId(null); setDebugData(null);
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt || "Say hello.", provider, model: model || undefined, structured }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const message = data?.detail?.message || data?.message || res.statusText;
        throw new Error(message || "Request failed");
      }
      setReply(String(data.reply ?? ""));
      if (data?.run_id) setRunId(String(data.run_id));
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  const paramify = async () => {
    setLoading(true); setError(null); setRunId(null); setDebugData(null); setPlanWarnings([]);
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/paramify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt || "Chill lofi hip-hop, 90 bpm, A minor.", provider, model: model || undefined }),
      });
      const data: any = await res.json().catch(() => ({}));
      if (!res.ok) {
        const message = data?.detail?.message || data?.message || res.statusText;
        throw new Error(message || "Request failed");
      }
      const normalized = (data?.normalized || {}) as ParamifyNormalizedPlan;
      const midiIn = (normalized?.midi || null) as Partial<MidiParameters> | null;
      const audioIn = (normalized?.audio || null) as Partial<AudioRenderParameters> | null;
      const warns: string[] = [];
      if (midiIn) {
        try {
          const nm = normalizeMidi(midiIn as any);
          setMidi(cloneMidi(nm));
        } catch (e) {
          warns.push(`Nie udało się znormalizować MIDI: ${String(e)}`);
        }
      } else {
        warns.push("Model nie zwrócił bloku MIDI.");
      }
      if (audioIn) {
        try {
          const na = normalizeAudio(audioIn as any);
          setAudio(na);
        } catch (e) {
          warns.push(`Nie udało się znormalizować audio: ${String(e)}`);
        }
      }
      setHasPlan(!!midiIn);
      setPlanWarnings(warns);
      if (data?.run_id) setRunId(String(data.run_id));
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  const loadDebug = async () => {
    if (!runId) return;
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/debug/${runId}`);
      const data = await res.json();
      setDebugData(data);
    } catch (e: any) {
      setError(`Failed to load debug: ${String(e?.message || e)}`);
    }
  };

  const prettyIfJson = (text: string) => {
    try {
      const obj = JSON.parse(text);
      return JSON.stringify(obj, null, 2);
    } catch {
      return text;
    }
  };

  return (
    <div className="min-h-screen bg-black text-white p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">AI Chat Smoke Test</h1>
        <p className="text-sm text-gray-400 mb-6">
          One-shot chat using a selected provider. Configure keys in backend .env (OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY).
        </p>

        <div className="bg-black/50 border border-purple-700 rounded-xl p-4 mb-4">
          <div className="flex gap-3 items-end mb-4">
            <div>
              <label className="block text-blue-300 mb-1">Provider</label>
              <select
                className="p-2 bg-black/70 border border-purple-700 rounded"
                value={provider}
                onChange={(e) => {
                  const id = e.target.value;
                  setProvider(id);
                  const found = providers.find(p => p.id === id);
                  setModel(found?.default_model || "");
                }}
              >
                {providers.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-blue-300 mb-1">Model</label>
              {availableModels.length > 0 ? (
                <select
                  className="w-full p-2 bg-black/70 border border-purple-700 rounded"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {availableModels.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="w-full p-2 bg-black/70 border border-purple-700 rounded"
                  placeholder="Enter model manually"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
              )}
            </div>
          </div>
          <label className="block text-blue-300 mb-2">Prompt</label>
          <textarea
            className="w-full p-3 bg-black/70 border border-purple-700 rounded-lg focus:outline-none"
            rows={4}
            placeholder="Type a short prompt..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <div className="mt-4 flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-blue-300">
              <input type="checkbox" checked={structured} onChange={(e) => setStructured(e.target.checked)} />
              Structured JSON
            </label>
            <button
              onClick={send}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 disabled:opacity-60"
            >
              {loading ? "Sending..." : "Send"}
            </button>
            <button
              onClick={paramify}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 disabled:opacity-60"
            >
              {loading ? "Working..." : "Generate parameters (paramify)"}
            </button>
            {error && <span className="text-red-400 text-sm">{error}</span>}
          </div>
          {planWarnings.length>0 && (
            <ul className="mt-2 text-xs text-yellow-300 list-disc list-inside">
              {planWarnings.map((w,i)=> <li key={i}>{w}</li>)}
            </ul>
          )}
          {hasPlan && (
            <div className="mt-3 text-xs text-gray-300">
              <div className="text-emerald-300">Using normalized parameters:</div>
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                <span>style: <span className="text-emerald-200">{midi.style}</span></span>
                <span>mood: <span className="text-emerald-200">{midi.mood}</span></span>
                <span>tempo: <span className="text-emerald-200">{midi.tempo}</span></span>
                <span>key: <span className="text-emerald-200">{midi.key}</span></span>
                <span>scale: <span className="text-emerald-200">{midi.scale}</span></span>
                <span>bars: <span className="text-emerald-200">{midi.bars}</span></span>
                <span>instruments: <span className="text-emerald-200">{midi.instruments.join(", ")}</span></span>
              </div>
            </div>
          )}
        </div>

        {reply !== null && (
          <div className="bg-black/50 border border-green-700 rounded-xl p-4">
            <div className="text-green-300 text-sm mb-1">Reply</div>
            <div className="whitespace-pre-wrap">{structured ? prettyIfJson(reply || "(empty)") : (reply || "(empty)")}</div>
            {runId && (
              <div className="mt-3 text-xs text-gray-400">
                Run: <span className="font-mono">{runId}</span>
                <button onClick={loadDebug} className="ml-3 px-2 py-1 border border-purple-700 rounded">Load debug</button>
              </div>
            )}
          </div>
        )}

        {debugData && (
          <div className="bg-black/50 border border-yellow-700 rounded-xl p-4 mt-4">
            <div className="text-yellow-300 text-sm mb-1">Debug Events</div>
            <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(debugData, null, 2)}</pre>
          </div>
        )}

  {/* Dry MIDI Composer test area */}
        <div className="mt-8" />
        <h2 className="text-xl font-semibold mb-2">MIDI Composer (dry)</h2>
        <p className="text-xs text-gray-400 mb-3">Generates a strict JSON MIDI pattern from current params (uses chat-smoke backend only).</p>
        <ChatMidiComposer
          disabled={!hasPlan}
          midi={midi}
          providers={providers}
          provider={provider}
          onProviderChange={(value) => {
            setProvider(value);
            const found = providers.find(p => p.id === value);
            setModel(found?.default_model || "");
          }}
          models={availableModels}
          model={model}
          onModelChange={setModel}
          apiBase={API_BASE}
          apiPrefix={API_PREFIX}
          modulePrefix={MODULE_PREFIX}
        />
      </div>
    </div>
  );
}
