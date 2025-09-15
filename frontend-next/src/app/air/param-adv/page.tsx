"use client";

import { useEffect, useState, useCallback } from "react";
import ReactMarkdown from 'react-markdown';

// Backend base URL – ustaw zmienną NEXT_PUBLIC_BACKEND_URL w .env.local jeśli backend działa pod innym hostem/portem
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = '/api';

// ---- Types (mirroring backend dataclasses) ----
interface MidiParameters {
  genre: string;
  mood: string;
  tempo: number;
  key: string; // single letter
  scale: string; // major/minor
  instruments: string[];
  bars: number;
  seed?: number | null;
}

interface SampleSelectionParameters {
  layers: number;
  prefer_organic: boolean;
  add_percussion: boolean;
}

interface AudioRenderParameters {
  sample_rate: number;
  seconds: number;
  master_gain_db: number;
}

interface DebugEvent {
  ts: number;
  stage: string;
  message: string;
  data?: Record<string, any> | null;
}

interface DebugRun {
  run_id: string;
  events: DebugEvent[];
}

interface FullPresetResponse { /* removed presets support */ }

interface DocsResponse { readme: string }

// Utility formatting
const timeFmt = (unix: number) => new Date(unix * 1000).toLocaleTimeString();

const DEFAULT_MIDI: MidiParameters = {
  genre: 'ambient',
  mood: 'calm',
  tempo: 80,
  key: 'C',
  scale: 'major',
  instruments: ['piano','pad','strings'],
  bars: 8,
  seed: null
};

const DEFAULT_SAMPLES: SampleSelectionParameters = {
  layers: 3,
  prefer_organic: true,
  add_percussion: true
};

const DEFAULT_AUDIO: AudioRenderParameters = {
  sample_rate: 44100,
  seconds: 6.0,
  master_gain_db: -3.0
};

export default function ParamAdvPage() {
  const [midi, setMidi] = useState<MidiParameters>(DEFAULT_MIDI);
  const [samples, setSamples] = useState<SampleSelectionParameters>(DEFAULT_SAMPLES);
  const [audio, setAudio] = useState<AudioRenderParameters>(DEFAULT_AUDIO);

  const [runId, setRunId] = useState<string | null>(null);
  const [debugRun, setDebugRun] = useState<DebugRun | null>(null);
  const [polling, setPolling] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  // Usunięto szczegółowy panel lastResult – skupiamy się tylko na debug timeline
  const [error, setError] = useState<string | null>(null);
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [rawResponse, setRawResponse] = useState<any>(null);
  const [midiImage, setMidiImage] = useState<string | null>(null);
  const [readme, setReadme] = useState<string | null>(null);
  const [showDocs, setShowDocs] = useState(false);

  // Poll debug endpoint – prosty polling REST (upgrade: SSE / WebSocket). Zatrzymuje się gdy pojawi się event run.completed.
  const pollDebug = useCallback(async (rid: string) => {
    try {
  const res = await fetch(`${API_BASE}${API_PREFIX}/param-adv/debug/${rid}`);
      const data = await res.json();
      if (data && data.run_id) {
        setDebugRun(data);
        // Stop polling if we see a 'run.completed' event
        if (data.events.some((e: DebugEvent) => e.stage === 'run' && e.message === 'completed')) {
          setPolling(false);
          setIsRunning(false);
        }
      } else {
        // If not found yet keep polling for short time
      }
    } catch (e) {
      console.error('poll debug error', e);
    }
  }, []);

  useEffect(() => {
    if (polling && runId) {
      const id = setInterval(() => pollDebug(runId), 1000);
      return () => clearInterval(id);
    }
  }, [polling, runId, pollDebug]);

  // Run actions – wywołujemy odpowiedni endpoint; dla prostoty tryb 'render' nie przesyła pełnych struktur (ograniczenie FastAPI wielokrotnych body) – zalecane użycie full.
  const execute = async (mode: 'midi' | 'render' | 'full') => {
  // wszystkie stany zawsze istnieją
    setIsRunning(true);
    setError(null);
    setRunId(null);
  setDebugRun(null);
  setResponseStatus(null);
  setRawResponse(null);

    const body: any = {};
    // Backend expects params depending on route signature
    let endpoint = '';
    if (mode === 'midi') {
      endpoint = '/param-adv/run/midi';
      Object.assign(body, midi);
    } else if (mode === 'render') {
      endpoint = '/param-adv/run/render';
      body.midi = midi;
      body.samples = samples;
      body.audio = audio;
    } else {
      endpoint = '/param-adv/run/full';
      body.midi = midi;
      body.samples = samples;
      body.audio = audio;
    }

    try {
  const res = await fetch(`${API_BASE}${API_PREFIX}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      setResponseStatus(res.status);
      let data: any = null;
      try {
        data = await res.json();
      } catch (ejson) {
        setError(`Nie udało się sparsować JSON (status ${res.status})`);
        setIsRunning(false);
        return;
      }
      setRawResponse(data);
      if (res.ok && data && data.run_id) {
        setRunId(data.run_id);
        setPolling(true);
        if (data.midi_image?.base64) {
          setMidiImage(`data:image/png;base64,${data.midi_image.base64}`);
        } else {
          setMidiImage(null);
        }
      } else {
        console.log('Brak run_id – surowa odpowiedź:', data);
        setError(`Brak run_id w odpowiedzi (status ${res.status})`);
        setIsRunning(false);
      }
    } catch (e: any) {
      setError(`Błąd uruchamiania: ${e}`);
      setIsRunning(false);
    }
  };

  const midiInstruments = midi.instruments;
  const toggleInstrument = (inst: string) => {
    if (midiInstruments.includes(inst)) {
      updateMidi({ instruments: midiInstruments.filter(i => i !== inst) });
    } else {
      updateMidi({ instruments: [...midiInstruments, inst] });
    }
  };

  const loadDocs = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}/param-adv/docs`);
      const data: DocsResponse = await res.json();
      if ((data as any).readme) setReadme(data.readme);
    } catch (e) {
      console.error('docs load failed', e);
    }
  };
  useEffect(() => { loadDocs(); }, []);

  const updateMidi = (patch: Partial<MidiParameters>) => setMidi(prev => ({ ...prev, ...patch }));
  const updateSamples = (patch: Partial<SampleSelectionParameters>) => setSamples(prev => ({ ...prev, ...patch }));
  const updateAudio = (patch: Partial<AudioRenderParameters>) => setAudio(prev => ({ ...prev, ...patch }));

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-black via-gray-950 to-black text-white px-6 py-10 space-y-10">
      <h1 className="text-3xl font-bold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-pink-500">Parametrized Advanced Pipeline</h1>
      <p className="text-sm text-gray-400 mb-8 max-w-3xl">Formularz do testowania pipeline'u <span className='text-blue-300'>MIDI → Samples → Audio</span> z podglądem zdarzeń debug. Polling (1s) pobiera stan aż do zdarzenia <code className='px-1 bg-gray-800 rounded'>completed</code>. Docelowo można to podmienić na SSE/WebSocket.</p>

      <div className="space-y-8">
        {/* Panel MIDI */}
        <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
          <h2 className="font-semibold mb-3 text-blue-300 text-lg">MIDI Parameters</h2>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block mb-1">Genre</label>
                <select value={midi.genre} onChange={e=>updateMidi({genre: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                  {['ambient','jazz','rock','techno','classical'].map(g=> <option key={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className="block mb-1">Mood</label>
                <select value={midi.mood} onChange={e=>updateMidi({mood: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                  {['calm','energetic','melancholic','joyful','mysterious'].map(m=> <option key={m}>{m}</option>)}
                </select>
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block mb-1">Key</label>
                  <select value={midi.key} onChange={e=>updateMidi({key: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                    {['C','A','F','D','G'].map(k=> <option key={k}>{k}</option>)}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block mb-1">Scale</label>
                  <select value={midi.scale} onChange={e=>updateMidi({scale: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                    {['major','minor'].map(s=> <option key={s}>{s}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block mb-1">Tempo: {midi.tempo} BPM</label>
                <input type="range" min={40} max={240} value={midi.tempo} onChange={e=>updateMidi({tempo: parseInt(e.target.value)})} className="w-full" />
              </div>
              <div>
                <label className="block mb-1">Bars</label>
                <input type="number" min={1} max={128} value={midi.bars} onChange={e=>updateMidi({bars: parseInt(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
              </div>
              <div>
                <label className="block mb-1">Seed (opcjonalny)</label>
                <input type="number" value={midi.seed ?? ''} onChange={e=>updateMidi({seed: e.target.value===''? null: parseInt(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
              </div>
              <div>
                <label className="block mb-1">Instruments</label>
                <div className="flex flex-wrap gap-2">
                  {['piano','pad','strings','bass','drums','guitar'].map(inst => (
                    <button type="button" key={inst} onClick={()=>toggleInstrument(inst)} className={`text-xs px-2 py-1 rounded border ${midiInstruments.includes(inst)?'bg-blue-600 border-blue-400':'border-gray-600'}`}>{inst}</button>
                  ))}
                </div>
              </div>
            </div>
        </div>

        {/* Panel Samples */}
        <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
          <h2 className="font-semibold mb-3 text-green-300 text-lg">Sample Selection</h2>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block mb-1">Layers</label>
                <input type="number" min={1} max={16} value={samples.layers} onChange={e=>updateSamples({layers: parseInt(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={samples.prefer_organic} onChange={e=>updateSamples({prefer_organic: e.target.checked})} />
                <label>Prefer organic</label>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={samples.add_percussion} onChange={e=>updateSamples({add_percussion: e.target.checked})} />
                <label>Add percussion</label>
              </div>
            </div>
        </div>

        {/* Panel Audio */}
        <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
          <h2 className="font-semibold mb-3 text-purple-300 text-lg">Audio Render</h2>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block mb-1">Sample Rate</label>
                <select value={audio.sample_rate} onChange={e=>updateAudio({sample_rate: parseInt(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                  {[44100,48000,96000].map(sr=> <option key={sr} value={sr}>{sr}</option>)}
                </select>
              </div>
              <div>
                <label className="block mb-1">Seconds</label>
                <input type="number" step={0.5} min={0.5} max={600} value={audio.seconds} onChange={e=>updateAudio({seconds: parseFloat(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
              </div>
              <div>
                <label className="block mb-1">Master Gain (dB)</label>
                <input type="number" step={0.5} min={-48} max={6} value={audio.master_gain_db} onChange={e=>updateAudio({master_gain_db: parseFloat(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
              </div>
            </div>
        </div>

        {/* Run controls */}
        <div className="flex flex-wrap gap-4 border-t border-gray-800 pt-6">
          <button disabled={isRunning} onClick={()=>execute('midi')} className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700">Run MIDI</button>
          <button disabled={isRunning} onClick={()=>execute('render')} className="px-4 py-2 rounded bg-green-700 hover:bg-green-600 disabled:bg-gray-700">Run Render</button>
          <button disabled={isRunning} onClick={()=>execute('full')} className="px-4 py-2 rounded bg-purple-700 hover:bg-purple-600 disabled:bg-gray-700">Run Full Pipeline</button>
          {isRunning && <div className="text-sm text-gray-400 flex items-center">⏳ Running...</div>}
        </div>

        {error && <div className="mb-6 p-4 bg-red-900 text-sm rounded">{error}</div>}
        {responseStatus !== null && !runId && (
          <div className="mb-6 p-4 bg-gray-900 border border-gray-700 rounded text-xs max-h-60 overflow-auto">
            <div className="mb-1 text-gray-400">Debug raw response (status {responseStatus}):</div>
            <pre className="whitespace-pre-wrap break-all">{JSON.stringify(rawResponse, null, 2)}</pre>
          </div>
        )}

        {/* Debug timeline */}
        <div className="bg-black/40 border border-gray-800 rounded-lg p-4 backdrop-blur-sm">
          <h3 className="font-semibold mb-4">Debug Events {runId && <span className="text-xs text-gray-400">(run {runId})</span>}</h3>
          {!debugRun && <div className="text-sm text-gray-500">Brak danych. Uruchom pipeline.</div>}
          {debugRun && (
            <ul className="text-xs space-y-1 max-h-96 overflow-auto font-mono">
              {debugRun.events.map((e, idx) => (
                <li key={idx} className="flex gap-2">
                  <span className="text-gray-500">{timeFmt(e.ts)}</span>
                  <span className="text-blue-400">[{e.stage}]</span>
                  <span>{e.message}</span>
                  {e.data && <span className="text-gray-400 truncate">{JSON.stringify(e.data)}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>

        {midiImage && (
          <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
            <h3 className="font-semibold mb-3 text-orange-300">MIDI Piano Roll</h3>
            <img src={midiImage} alt="MIDI Piano Roll" className="max-w-full border border-gray-800 rounded" />
          </div>
        )}

        {readme && (
          <div className="border-t border-gray-800 pt-8">
            <button onClick={()=>setShowDocs(s=>!s)} className="text-sm px-3 py-2 rounded bg-gray-800/60 border border-gray-700 hover:border-gray-500">
              {showDocs ? 'Ukryj opis pipeline' : 'Pokaż szczegółowy opis pipeline (README)'}
            </button>
            {showDocs && (
              <div className="mt-4 bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-sm prose prose-invert max-w-none overflow-x-auto">
                <ReactMarkdown>{readme}</ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="mt-12 text-center text-xs text-gray-600">Param Adv UI • Polling REST (upgradeable to SSE/WebSocket)</div>
    </div>
  );
}
