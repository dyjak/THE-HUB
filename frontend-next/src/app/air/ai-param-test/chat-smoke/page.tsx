"use client";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = "/api";
const MODULE_PREFIX = "/ai-param-test";

export default function ChatSmokePage() {
  const [prompt, setPrompt] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providers, setProviders] = useState<{id:string; name:string; default_model:string}[]>([]);
  const [provider, setProvider] = useState<string>("openai");
  const [model, setModel] = useState<string>("");
  const [availableModels, setAvailableModels] = useState<string[]>([]);

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
    setLoading(true); setError(null); setReply(null);
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt || "Say hello.", provider, model: model || undefined }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const message = data?.detail?.message || data?.message || res.statusText;
        throw new Error(message || "Request failed");
      }
      setReply(String(data.reply ?? ""));
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
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
            <button
              onClick={send}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 disabled:opacity-60"
            >
              {loading ? "Sending..." : "Send"}
            </button>
            {error && <span className="text-red-400 text-sm">{error}</span>}
          </div>
        </div>

        {reply !== null && (
          <div className="bg-black/50 border border-green-700 rounded-xl p-4">
            <div className="text-green-300 text-sm mb-1">Reply</div>
            <div className="whitespace-pre-wrap">{reply || "(empty)"}</div>
          </div>
        )}
      </div>
    </div>
  );
}
