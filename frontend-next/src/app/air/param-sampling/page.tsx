"use client";
import { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = '/api';

interface MidiParameters {
  genre: string; mood: string; tempo: number; key: string; scale: string; instruments: string[]; bars: number; seed?: number | null;
}
interface AudioRenderParameters { sample_rate: number; seconds: number; master_gain_db: number }
interface DebugEvent { ts: number; stage: string; message: string; data?: Record<string, any> | null }
interface DebugRun { run_id: string; events: DebugEvent[] }
interface AvailableInstruments { available: string[]; count: number }
interface InventoryInstrumentInfo { count: number; examples: string[] }
interface InventoryPayload { generated_at: number; root: string; instruments: Record<string, InventoryInstrumentInfo> }

const DEFAULT_MIDI: MidiParameters = { genre: 'ambient', mood: 'calm', tempo: 80, key: 'C', scale: 'major', instruments: ['piano','pad'], bars: 8, seed: null };
const DEFAULT_AUDIO: AudioRenderParameters = { sample_rate: 44100, seconds: 6, master_gain_db: -3 };

const timeFmt = (unix: number) => new Date(unix * 1000).toLocaleTimeString();

export default function ParamSamplingPage() {
  const [midi, setMidi] = useState<MidiParameters>(DEFAULT_MIDI);
  const [audio, setAudio] = useState<AudioRenderParameters>(DEFAULT_AUDIO);
  const [runId, setRunId] = useState<string | null>(null);
  const [debugRun, setDebugRun] = useState<DebugRun | null>(null);
  const [polling, setPolling] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawResponse, setRawResponse] = useState<any>(null);
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [available, setAvailable] = useState<string[]>([]);
  const [audioFile, setAudioFile] = useState<string | null>(null);
  const [midiJsonFile, setMidiJsonFile] = useState<string | null>(null);
  const [midiMidFile, setMidiMidFile] = useState<string | null>(null);
  const [pianoRoll, setPianoRoll] = useState<string | null>(null);
  const [inventory, setInventory] = useState<InventoryPayload | null>(null);

  const loadAvailable = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}/param-sampling/available-instruments`);
      if (!res.ok) return;
      const data: AvailableInstruments = await res.json();
      setAvailable(data.available || []);
      // Remove any instruments not in available (strict backend)
      setMidi(prev => ({ ...prev, instruments: prev.instruments.filter(i => data.available.includes(i)) }));
    } catch (e) {
      console.warn('avail fetch fail', e);
    }
  };
  const loadInventory = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}/param-sampling/inventory`);
      if (!res.ok) return;
      const inv: InventoryPayload = await res.json();
      setInventory(inv);
    } catch (e) {
      console.warn('inventory fetch fail', e);
    }
  };
  useEffect(() => { loadAvailable(); loadInventory(); }, []);

  const pollDebug = useCallback(async (rid: string) => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}/param-sampling/debug/${rid}`);
      const data = await res.json();
      if (data && data.run_id) {
        setDebugRun(data);
        if (data.events.some((e: DebugEvent) => e.stage === 'run' && e.message === 'completed')) {
          setPolling(false); setIsRunning(false);
        }
      }
    } catch (e) { /* silent */ }
  }, []);
  useEffect(() => { if (polling && runId) { const id = setInterval(() => pollDebug(runId), 1000); return () => clearInterval(id); } }, [polling, runId, pollDebug]);

  const updateMidi = (patch: Partial<MidiParameters>) => setMidi(p => ({...p, ...patch}));
  const updateAudio = (patch: Partial<AudioRenderParameters>) => setAudio(p => ({...p, ...patch}));

  const toggleInstrument = (inst: string) => {
    if (!available.includes(inst)) return; // guard
    updateMidi({ instruments: midi.instruments.includes(inst) ? midi.instruments.filter(i=>i!==inst) : [...midi.instruments, inst] });
  };

  const run = async (mode: 'midi' | 'render' | 'full') => {
  setIsRunning(true); setError(null); setRunId(null); setDebugRun(null); setAudioFile(null); setMidiJsonFile(null); setMidiMidFile(null); setPianoRoll(null); setRawResponse(null); setResponseStatus(null);
    const body: any = {};
    let endpoint: string;
    if (mode === 'midi') { endpoint = '/param-sampling/run/midi'; Object.assign(body, midi); }
    else if (mode === 'render') { endpoint = '/param-sampling/run/render'; body.midi = midi; body.audio = audio; }
    else { endpoint = '/param-sampling/run/full'; body.midi = midi; body.audio = audio; }

    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      setResponseStatus(res.status);
      let data: any = null; try { data = await res.json(); } catch { setError('JSON parse error'); setIsRunning(false); return; }
      setRawResponse(data);
      if (!res.ok) { setError(data?.detail || data?.error || `HTTP ${res.status}`); setIsRunning(false); return; }
      if (data.run_id) { setRunId(data.run_id); setPolling(true); }
      // Audio artifact path (new per-run naming)
      if (data.audio?.audio_file_rel) {
        setAudioFile(data.audio.audio_file_rel);
      } else if (data.audio?.audio_file) { // legacy flat
        const name = data.audio.audio_file.split(/\\|\//).slice(-2).join('/');
        setAudioFile(name || null);
      }
      // New keys from backend for MIDI & visualization
      if (data.midi_json_rel) {
        setMidiJsonFile(data.midi_json_rel);
      } else if (data.midi_json) {
        const segs = String(data.midi_json).split(/\\|\//).slice(-2).join('/');
        setMidiJsonFile(segs || null);
      }
      if (data.midi_mid_rel) {
        setMidiMidFile(data.midi_mid_rel);
      } else if (data.midi_mid) {
        const segs = String(data.midi_mid).split(/\\|\//).slice(-2).join('/');
        setMidiMidFile(segs || null);
      }
      if (data.midi_image?.combined_rel) {
        setPianoRoll(data.midi_image.combined_rel);
      } else if (data.midi_image?.combined) {
        const segs = String(data.midi_image.combined).split(/\\|\//).slice(-2).join('/');
        setPianoRoll(segs || null);
      }
    } catch (e: any) {
      setError(String(e)); setIsRunning(false);
    }
  };

  const disableInst = (inst: string) => !available.includes(inst);

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-black via-gray-950 to-black text-white px-6 py-10 space-y-10">
      <h1 className="text-3xl font-bold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-500">Param Sampling (Local)</h1>
      <p className="text-sm text-gray-400 max-w-3xl">Lokalny pipeline: <span className='text-emerald-300'>MIDI → (strict local samples) → Audio</span>. Brak placeholderów. Najpierw wybierz tylko dostępne instrumenty. Lista aktualizowana z backendu.</p>

      <div className="grid md:grid-cols-3 gap-6">
        {/* MIDI Panel */}
        <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 space-y-4 col-span-2">
          <h2 className="font-semibold text-emerald-300">MIDI Parameters</h2>
          <div className="grid sm:grid-cols-2 gap-4 text-sm">
            <div>
              <label className="block mb-1">Genre</label>
              <select value={midi.genre} onChange={e=>updateMidi({genre: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                {['ambient','jazz','rock','techno','classical','orchestral','lofi','hiphop','house','metal'].map(g=> <option key={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block mb-1">Mood</label>
              <select value={midi.mood} onChange={e=>updateMidi({mood: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                {['calm','energetic','melancholic','joyful','mysterious','epic','relaxed','aggressive','dreamy','groovy','romantic'].map(m=> <option key={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="block mb-1">Key</label>
              <select value={midi.key} onChange={e=>updateMidi({key: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                {['C','A','F','D','G'].map(k=> <option key={k}>{k}</option>)}
              </select>
            </div>
            <div>
              <label className="block mb-1">Scale</label>
              <select value={midi.scale} onChange={e=>updateMidi({scale: e.target.value})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                {['major','minor'].map(s=> <option key={s}>{s}</option>)}
              </select>
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
              <label className="block mb-1">Seed (optional)</label>
              <input type="number" value={midi.seed ?? ''} onChange={e=>updateMidi({seed: e.target.value===''? null: parseInt(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
            </div>
            <div>
              <label className="block mb-1">Instruments (only available)</label>
              <div className="flex flex-wrap gap-2">
                {['piano','pad','strings','bass','guitar','lead','choir','flute','trumpet','saxophone','kick','snare','hihat','clap','rim','tom','808','perc','drumkit'].map(inst => {
                  const disabled = disableInst(inst);
                  const active = midi.instruments.includes(inst);
                  return (
                    <button type="button" key={inst} disabled={disabled} onClick={()=>toggleInstrument(inst)} className={`text-xs px-2 py-1 rounded border transition ${disabled? 'opacity-30 cursor-not-allowed border-gray-800':'cursor-pointer'} ${active? 'bg-emerald-600 border-emerald-400':'border-gray-600 hover:border-emerald-400'}`}>{inst}</button>
                  );
                })}
              </div>
              <div className="text-[10px] text-gray-500 mt-1">Niedostępne instrumenty są wyszarzone (brak sample na backendzie).</div>
            </div>
          </div>
        </div>
        {/* Audio panel */}
        <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 space-y-4">
          <h2 className="font-semibold text-cyan-300">Audio</h2>
          <div className="space-y-3 text-sm">
            <div>
              <label className="block mb-1">Sample Rate</label>
              <select value={audio.sample_rate} onChange={e=>updateAudio({sample_rate: parseInt(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700">
                {[44100,48000,96000].map(sr=> <option key={sr}>{sr}</option>)}
              </select>
            </div>
            <div>
              <label className="block mb-1">Seconds</label>
              <input type="number" step={0.5} min={0.5} max={600} value={audio.seconds} onChange={e=>updateAudio({seconds: parseFloat(e.target.value)})} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
            </div>
          </div>
          <div className="text-[10px] text-gray-500">Master gain i inne parametry pominięte w uproszczonej wersji.</div>
        </div>
      </div>

      {/* Run controls */}
      <div className="flex flex-wrap gap-4 border-t border-gray-800 pt-6">
        <button disabled={isRunning} onClick={()=>run('midi')} className="px-4 py-2 rounded bg-emerald-700 hover:bg-emerald-600 disabled:bg-gray-700">Run MIDI</button>
        <button disabled={isRunning} onClick={()=>run('render')} className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700">Run Render</button>
        <button disabled={isRunning} onClick={()=>run('full')} className="px-4 py-2 rounded bg-purple-700 hover:bg-purple-600 disabled:bg-gray-700">Run Full</button>
        {isRunning && <div className="text-sm text-gray-400 flex items-center">⏳ Running...</div>}
      </div>
      {error && <div className="p-3 bg-red-900 text-sm rounded border border-red-600 max-w-xl">{error}</div>}

      {/* Raw response if no run id */}
      {responseStatus !== null && !runId && (
        <div className="p-4 bg-gray-900/60 border border-gray-800 rounded text-xs max-h-60 overflow-auto max-w-2xl">
          <div className="mb-1 text-gray-400">Raw response (status {responseStatus}):</div>
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify(rawResponse, null, 2)}</pre>
        </div>
      )}

      {/* Debug timeline */}
      <div className="bg-black/40 border border-gray-800 rounded-lg p-4 backdrop-blur-sm">
        <h3 className="font-semibold mb-4">Debug Events {runId && <span className="text-xs text-gray-400">(run {runId})</span>}</h3>
        {!debugRun && <div className="text-sm text-gray-500">Brak danych. Uruchom pipeline.</div>}
        {debugRun && (
          <ul className="text-xs space-y-1 max-h-80 overflow-auto font-mono">
            {debugRun.events.map((e, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="text-gray-500">{timeFmt(e.ts)}</span>
                <span className="text-emerald-400">[{e.stage}]</span>
                <span>{e.message}</span>
                {e.data && <span className="text-gray-400 truncate">{JSON.stringify(e.data)}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Artifacts */}
      {(audioFile || midiJsonFile || midiMidFile || pianoRoll) && (
        <div className="grid md:grid-cols-4 gap-6">
          {audioFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-blue-300 mb-2">Audio Preview</h3>
              <audio controls src={`${API_BASE}${API_PREFIX}/param-sampling/output/${audioFile}`} className="w-full" />
              <div className="text-[10px] text-gray-500 mt-1 break-all">{audioFile}</div>
            </div>
          )}
          {midiJsonFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-orange-300 mb-2">MIDI Pattern (JSON)</h3>
              <a className="underline" target="_blank" href={`${API_BASE}${API_PREFIX}/param-sampling/output/${midiJsonFile}`}>{midiJsonFile}</a>
              <div className="text-[10px] text-gray-500 mt-1">Strukturalna reprezentacja wygenerowanego patternu.</div>
            </div>
          )}
          {midiMidFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-fuchsia-300 mb-2">MIDI File (.mid)</h3>
              <a className="underline" target="_blank" href={`${API_BASE}${API_PREFIX}/param-sampling/output/${midiMidFile}`}>{midiMidFile}</a>
              <div className="text-[10px] text-gray-500 mt-1">Pobierz plik MIDI do DAW.</div>
            </div>
          )}
          {pianoRoll && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-cyan-300 mb-2">Piano Roll</h3>
              <img src={`${API_BASE}${API_PREFIX}/param-sampling/output/${pianoRoll}`} alt="pianoroll" className="w-full rounded" />
              <div className="text-[10px] text-gray-500 mt-1 break-all">{pianoRoll}</div>
            </div>
          )}
        </div>
      )}

      {/* Inventory & availability */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-gray-900/40 p-4 rounded-lg border border-gray-800 text-xs">
          <h3 className="font-semibold text-gray-300 mb-2">Available Instruments (quick)</h3>
          {available.length === 0 ? <div className="text-gray-500">None found (umieść WAV w lokalnym katalogu)</div> : (
            <div className="flex flex-wrap gap-2">
              {available.map(a => <span key={a} className="px-2 py-1 rounded bg-gray-800 border border-gray-700">{a}</span>)}
            </div>
          )}
          <div className="flex gap-2 mt-3">
            <button onClick={loadAvailable} className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 border border-gray-600 text-[11px]">Refresh</button>
            <button onClick={loadInventory} className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 border border-gray-600 text-[11px]">Load Inventory</button>
          </div>
          <div className="text-[10px] text-gray-600 mt-2">/available-instruments (lista skrócona)</div>
        </div>
        <div className="bg-gray-900/40 p-4 rounded-lg border border-gray-800 text-xs">
            <h3 className="font-semibold text-gray-300 mb-2">Inventory Details</h3>
            {!inventory && <div className="text-gray-600">Brak danych (kliknij Load Inventory)</div>}
            {inventory && (
              <div className="space-y-2 max-h-48 overflow-auto pr-2">
                {Object.entries(inventory.instruments).map(([inst, info]) => (
                  <div key={inst} className="flex flex-col bg-gray-800/40 rounded p-2 border border-gray-700/50">
                    <div className="flex justify-between">
                      <span className="font-semibold text-emerald-300">{inst}</span>
                      <span className="text-gray-400">{info.count}</span>
                    </div>
                    {info.examples.length > 0 && (
                      <div className="text-[10px] text-gray-500 truncate">{info.examples.join(', ')}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {inventory && (
              <div className="text-[10px] text-gray-600 mt-2">Root: {inventory.root}</div>
            )}
            <div className="text-[10px] text-gray-600 mt-2">Zapisane w inventory.json</div>
        </div>
      </div>

      <div className="mt-12 text-center text-xs text-gray-600">Param Sampling UI • Strict local samples</div>
    </div>
  );
}
