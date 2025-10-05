"use client";
import { useState, useEffect, useCallback } from 'react';
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = '/api';
const MODULE_PREFIX = '/ai-param-test';
const OUTPUT_PREFIX = `${MODULE_PREFIX}/output`;

const STYLE_OPTIONS = [
  'ambient','jazz','rock','techno','classical','orchestral','lofi','hiphop','house','metal','trap','pop','cinematic','folk','world','experimental'
] as const;
const MOOD_OPTIONS = [
  'calm','energetic','melancholic','joyful','mysterious','epic','relaxed','aggressive','dreamy','groovy','romantic','dark','uplifting','serene','tense'
] as const;
const KEY_OPTIONS = ['C','C#','Db','D','D#','Eb','E','F','F#','Gb','G','G#','Ab','A','A#','Bb','B'] as const;
const SCALE_OPTIONS = ['major','minor','harmonic_minor','melodic_minor','dorian','phrygian','lydian','mixolydian','locrian','pentatonic_major','pentatonic_minor','blues','whole_tone','phrygian_dominant','hungarian_minor'] as const;
const METER_OPTIONS = ['4/4','3/4','6/8','5/4','7/8','12/8'] as const;
const DYNAMIC_PROFILE_OPTIONS = ['gentle','moderate','energetic'] as const;
const ARRANGEMENT_DENSITY_OPTIONS = ['minimal','balanced','dense'] as const;
const HARMONIC_COLOR_OPTIONS = ['diatonic','modal','chromatic','modulating','experimental'] as const;
const REGISTER_OPTIONS = ['low','mid','high','full'] as const;
const ROLE_OPTIONS = ['lead','accompaniment','rhythm','pad','bass','percussion','fx'] as const;
const ARTICULATION_OPTIONS = ['sustain','staccato','legato','pizzicato','accented','slurred','percussive','glide','arpeggiated'] as const;
const DYNAMIC_RANGE_OPTIONS = ['delicate','moderate','intense'] as const;
const EFFECT_OPTIONS = ['reverb','delay','chorus','distortion','filter','compression','phaser','flanger','shimmer','lofi'] as const;
const DEFAULT_FORM = ['intro','verse','chorus','verse','chorus','bridge','chorus','outro'] as const;
const DEFAULT_INSTRUMENTS = ['piano','pad','strings'] as const;
const INSTRUMENT_CHOICES = ['piano','pad','strings','bass','guitar','lead','choir','flute','trumpet','saxophone','kick','snare','hihat','clap','rim','tom','808','perc','drumkit','fx'] as const;
const FORM_SECTION_OPTIONS = ['intro','verse','chorus','pre-chorus','bridge','build','drop','solo','breakdown','outro'] as const;

type StyleOption = typeof STYLE_OPTIONS[number];
type MoodOption = typeof MOOD_OPTIONS[number];
type KeyOption = typeof KEY_OPTIONS[number];
type ScaleOption = typeof SCALE_OPTIONS[number];
type MeterOption = typeof METER_OPTIONS[number];
type DynamicProfileOption = typeof DYNAMIC_PROFILE_OPTIONS[number];
type ArrangementDensityOption = typeof ARRANGEMENT_DENSITY_OPTIONS[number];
type HarmonicColorOption = typeof HARMONIC_COLOR_OPTIONS[number];
type RegisterOption = typeof REGISTER_OPTIONS[number];
type RoleOption = typeof ROLE_OPTIONS[number];
type ArticulationOption = typeof ARTICULATION_OPTIONS[number];
type DynamicRangeOption = typeof DYNAMIC_RANGE_OPTIONS[number];

interface InstrumentConfig {
  name: string;
  register: RegisterOption;
  role: RoleOption;
  volume: number;
  pan: number;
  articulation: ArticulationOption;
  dynamic_range: DynamicRangeOption;
  effects: string[];
}

interface MidiParameters {
  style: StyleOption;
  genre: string;
  mood: MoodOption;
  tempo: number;
  key: KeyOption;
  scale: ScaleOption;
  meter: MeterOption;
  bars: number;
  length_seconds: number;
  form: string[];
  dynamic_profile: DynamicProfileOption;
  arrangement_density: ArrangementDensityOption;
  harmonic_color: HarmonicColorOption;
  instruments: string[];
  instrument_configs: InstrumentConfig[];
  seed: number | null;
}

interface AudioRenderParameters {
  sample_rate: number;
  seconds: number;
  master_gain_db: number;
}
interface DebugEvent { ts: number; stage: string; message: string; data?: Record<string, any> | null }
interface DebugRun { run_id: string; events: DebugEvent[] }
interface AvailableInstruments { available: string[]; count: number }
interface InventoryInstrumentInfo { count: number; examples: string[] }
interface InventorySampleMeta {
  instrument: string;
  id: string;
  file_rel: string;
  file_abs?: string;
  bytes?: number;
  source?: string;
  pitch?: string | null;
  category?: string | null;
  family?: string | null;
  subtype?: string | null;
  is_loop?: boolean;
  sample_rate?: number | null;
  length_sec?: number | null;
}
interface InventoryPayload {
  schema_version?: string;
  deep?: boolean;
  generated_at: number;
  root: string;
  instruments: Record<string, InventoryInstrumentInfo>;
  samples?: InventorySampleMeta[];
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
const toNumber = (value: unknown, fallback: number): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const pickFrom = <T extends readonly string[]>(value: unknown, options: T, fallback: T[number]): T[number] => {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return fallback;
    const direct = (options as readonly string[]).find(opt => opt === trimmed);
    if (direct) return direct as T[number];
    const lower = trimmed.toLowerCase();
    const match = (options as readonly string[]).find(opt => opt.toLowerCase() === lower);
    if (match) return match as T[number];
  }
  return fallback;
};

const uniqueStrings = (items: string[]): string[] => {
  const seen = new Set<string>();
  const result: string[] = [];
  items.forEach(item => {
    const key = item.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      result.push(item);
    }
  });
  return result;
};

const parseEffects = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return uniqueStrings(value.map(v => String(v).trim()).filter(Boolean));
  }
  if (typeof value === 'string') {
    return uniqueStrings(value.split(',').map(v => v.trim()).filter(Boolean));
  }
  return [];
};

const createDefaultInstrumentConfig = (name: string, index = 0): InstrumentConfig => {
  const lower = name.toLowerCase();
  let register: RegisterOption = 'mid';
  let role: RoleOption = index === 0 ? 'lead' : 'accompaniment';
  let articulation: ArticulationOption = 'sustain';
  let dynamic_range: DynamicRangeOption = 'moderate';
  let effects: string[] = ['reverb'];
  let volume = 0.8;
  let pan = clamp(-0.2 + index * 0.3, -0.6, 0.6);

  if (['bass','bass_synth','bass_guitar','808','reese'].includes(lower)) {
    register = 'low';
    role = 'bass';
    dynamic_range = 'intense';
    articulation = 'legato';
    effects = ['compression','filter'];
    volume = 0.9;
    pan = 0;
  } else if (['kick','snare','hihat','clap','rim','tom','perc','drumkit'].includes(lower)) {
    register = 'low';
    role = 'percussion';
    dynamic_range = 'intense';
    articulation = 'percussive';
    effects = ['compression'];
    volume = 0.95;
    pan = 0;
  } else if (['pad','strings','choir'].includes(lower)) {
    register = 'full';
    role = 'pad';
    articulation = 'sustain';
    effects = ['reverb','chorus'];
    volume = 0.85;
  } else if (['lead','synth','guitar','piano','flute','trumpet','saxophone'].includes(lower)) {
    role = index === 0 ? 'lead' : 'accompaniment';
    register = lower === 'flute' ? 'high' : 'mid';
    articulation = ['synth','flute'].includes(lower) ? 'legato' : 'sustain';
    effects = ['reverb','delay'];
    volume = role === 'lead' ? 0.9 : 0.8;
  }

  return {
    name,
    register,
    role,
    volume: clamp(volume, 0, 1),
    pan: clamp(pan, -1, 1),
    articulation,
    dynamic_range,
    effects,
  };
};

const toInstrumentConfig = (raw: unknown): InstrumentConfig | null => {
  if (!raw || typeof raw !== 'object') return null;
  const source = raw as Record<string, unknown>;
  const name = String(source.name ?? '').trim();
  if (!name) return null;
  const register = pickFrom(source.register, REGISTER_OPTIONS, 'mid');
  const role = pickFrom(source.role, ROLE_OPTIONS, 'accompaniment');
  const articulation = pickFrom(source.articulation, ARTICULATION_OPTIONS, 'sustain');
  const dynamic_range = pickFrom(source.dynamic_range, DYNAMIC_RANGE_OPTIONS, 'moderate');
  const volume = clamp(toNumber(source.volume, 0.8), 0, 1);
  const pan = clamp(toNumber(source.pan, 0), -1, 1);
  const effects = parseEffects(source.effects);
  return { name, register, role, articulation, dynamic_range, volume, pan, effects };
};

const ensureInstrumentConfigs = (instruments: string[], existing: InstrumentConfig[]): InstrumentConfig[] => {
  const byName = new Map(existing.map(cfg => [cfg.name, cfg] as const));
  return instruments.map((inst, index) => {
    const prev = byName.get(inst);
    if (!prev) return createDefaultInstrumentConfig(inst, index);
    return {
      ...prev,
      name: inst,
      effects: [...prev.effects],
    };
  });
};

const normalizeMidi = (input: Partial<MidiParameters> | Record<string, unknown>): MidiParameters => {
  const style = pickFrom(input.style ?? input.genre, STYLE_OPTIONS, 'ambient');
  const mood = pickFrom(input.mood, MOOD_OPTIONS, 'calm');
  const key = pickFrom(input.key, KEY_OPTIONS, 'C');
  const scale = pickFrom(input.scale, SCALE_OPTIONS, 'major');
  const meter = pickFrom(input.meter, METER_OPTIONS, '4/4');
  const dynamic_profile = pickFrom(input.dynamic_profile, DYNAMIC_PROFILE_OPTIONS, 'moderate');
  const arrangement_density = pickFrom(input.arrangement_density, ARRANGEMENT_DENSITY_OPTIONS, 'balanced');
  const harmonic_color = pickFrom(input.harmonic_color, HARMONIC_COLOR_OPTIONS, 'diatonic');
  const tempo = clamp(Math.round(toNumber(input.tempo, 80)), 20, 300);
  const bars = clamp(Math.round(toNumber(input.bars, 16)), 1, 512);
  const length_seconds = clamp(toNumber(input.length_seconds, 180), 30, 3600);

  const formArray = Array.isArray(input.form)
    ? input.form.map(section => String(section).trim()).filter(Boolean)
    : typeof input.form === 'string'
      ? input.form.split(/[,\n]/).map(section => section.trim()).filter(Boolean)
      : [];
  const form = formArray.length ? formArray : Array.from(DEFAULT_FORM);

  const instrumentsRaw = Array.isArray(input.instruments)
    ? input.instruments
    : typeof input.instruments === 'string'
      ? input.instruments.split(',')
      : Array.from(DEFAULT_INSTRUMENTS);
  const instruments = uniqueStrings(instrumentsRaw.map(item => String(item).trim()).filter(Boolean));
  const safeInstruments = instruments.length ? instruments : Array.from(DEFAULT_INSTRUMENTS);

  const configsRaw = Array.isArray(input.instrument_configs) ? input.instrument_configs : [];
  const parsedConfigs = configsRaw.map(toInstrumentConfig).filter(Boolean) as InstrumentConfig[];
  const instrument_configs = ensureInstrumentConfigs(safeInstruments, parsedConfigs);

  let seed: number | null = null;
  if (input.seed !== undefined && input.seed !== null && input.seed !== '') {
    const seedNum = Number(input.seed);
    seed = Number.isFinite(seedNum) ? Math.trunc(seedNum) : null;
  }

  return {
    style,
    genre: style,
    mood,
    tempo,
    key,
    scale,
    meter,
    bars,
    length_seconds,
    form,
    dynamic_profile,
    arrangement_density,
    harmonic_color,
    instruments: safeInstruments,
    instrument_configs,
    seed,
  };
};

const normalizeAudio = (input: Partial<AudioRenderParameters> | Record<string, unknown>): AudioRenderParameters => {
  const sample_rate = clamp(Math.round(toNumber(input.sample_rate, 44100)), 8000, 192000);
  const seconds = clamp(toNumber(input.seconds, 6), 0.5, 600);
  const master_gain_db = toNumber(input.master_gain_db, -3);
  return { sample_rate, seconds, master_gain_db };
};

const cloneMidi = (params: MidiParameters): MidiParameters => ({
  ...params,
  form: [...params.form],
  instruments: [...params.instruments],
  instrument_configs: params.instrument_configs.map(cfg => ({ ...cfg, effects: [...cfg.effects] })),
});

const cloneAudio = (params: AudioRenderParameters): AudioRenderParameters => ({ ...params });

const DEFAULT_MIDI = cloneMidi(normalizeMidi({}));
const DEFAULT_AUDIO = cloneAudio(normalizeAudio({}));

const timeFmt = (unix: number) => new Date(unix * 1000).toLocaleTimeString();

export default function AIParamTestPage() {
  const [midi, setMidi] = useState<MidiParameters>(() => cloneMidi(DEFAULT_MIDI));
  const [audio, setAudio] = useState<AudioRenderParameters>(() => cloneAudio(DEFAULT_AUDIO));
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
  const [sampleFilterInst, setSampleFilterInst] = useState<string>("");
  const [sampleFilterText, setSampleFilterText] = useState<string>("");
  const [blueprint, setBlueprint] = useState<{ midi: any; audio: any } | null>(null);

  const loadAvailable = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/available-instruments`);
      if (!res.ok) return;
      const data: AvailableInstruments = await res.json();
      const list = data.available || [];
      setAvailable(list);
      // Remove any instruments not in available (strict backend) and keep configs aligned
      setMidi(prev => {
        const filtered = prev.instruments.filter(i => list.includes(i));
        return {
          ...prev,
          instruments: filtered,
          instrument_configs: ensureInstrumentConfigs(filtered, prev.instrument_configs),
        };
      });
    } catch (e) {
      console.warn('avail fetch fail', e);
    }
  };
  const loadInventory = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/inventory`);
      if (!res.ok) return;
      const inv: InventoryPayload = await res.json();
      setInventory(inv);
    } catch (e) {
      console.warn('inventory fetch fail', e);
    }
  };
  const rebuildInventory = async (mode?: 'deep' | 'quick') => {
    try {
      const url = `${API_BASE}${API_PREFIX}${MODULE_PREFIX}/inventory/rebuild${mode==='deep' ? '?mode=deep':''}`;
      const res = await fetch(url, { method: 'POST' });
      if (!res.ok) return;
      await loadInventory();
    } catch (e) { console.warn('inventory rebuild fail', e); }
  };

  const loadPresets = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/presets`);
      if (!res.ok) return;
      const data: Record<string, { midi?: MidiParameters; audio?: AudioRenderParameters }> = await res.json();
      const full = data?.full;
      if (full?.midi) {
        const normalized = normalizeMidi(full.midi);
        setMidi(cloneMidi(normalized));
      }
      if (full?.audio) {
        setAudio(cloneAudio(normalizeAudio(full.audio)));
      }
    } catch (e) {
      console.warn('preset fetch fail', e);
    }
  };

  useEffect(() => {
    loadAvailable();
    loadInventory();
    loadPresets();
  }, []);

  const pollDebug = useCallback(async (rid: string) => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/debug/${rid}`);
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

  const updateMidi = (patch: Partial<MidiParameters>) => setMidi(p => ({ ...p, ...patch }));
  const updateAudio = (patch: Partial<AudioRenderParameters>) => setAudio(p => ({...p, ...patch}));

  const toggleInstrument = (inst: string) => {
    if (!available.includes(inst)) return; // guard
    setMidi(prev => {
      const exists = prev.instruments.includes(inst);
      const nextInstruments = exists ? prev.instruments.filter(i => i !== inst) : [...prev.instruments, inst];
      return {
        ...prev,
        instruments: nextInstruments,
        instrument_configs: ensureInstrumentConfigs(nextInstruments, prev.instrument_configs),
      };
    });
  };

  const updateInstrumentConfig = (name: string, patch: Partial<InstrumentConfig>) => {
    setMidi(prev => {
      const nextConfigs = prev.instrument_configs.map(cfg => {
        if (cfg.name !== name) return cfg;
        const next: InstrumentConfig = {
          ...cfg,
          ...patch,
        };
        if (patch.volume !== undefined) {
          const vol = Number(patch.volume);
          next.volume = clamp(Number.isFinite(vol) ? vol : cfg.volume, 0, 1);
        }
        if (patch.pan !== undefined) {
          const panValue = Number(patch.pan);
          next.pan = clamp(Number.isFinite(panValue) ? panValue : cfg.pan, -1, 1);
        }
        if (patch.effects !== undefined) {
          next.effects = uniqueStrings(patch.effects);
        }
        return { ...next, effects: [...next.effects] };
      });
      return {
        ...prev,
        instrument_configs: ensureInstrumentConfigs(prev.instruments, nextConfigs),
      };
    });
  };
  const addFormSection = (section: string) => {
    setMidi(prev => ({
      ...prev,
      form: [...prev.form, section],
    }));
  };

  const removeFormSection = (index: number) => {
    setMidi(prev => ({
      ...prev,
      form: prev.form.filter((_, idx) => idx !== index),
    }));
  };

  const resetForm = () => {
    setMidi(prev => ({
      ...prev,
      form: Array.from(DEFAULT_FORM),
    }));
  };

  const clearForm = () => {
    setMidi(prev => ({
      ...prev,
      form: [],
    }));
  };

  const toggleInstrumentEffect = (name: string, effect: string) => {
    setMidi(prev => {
      const nextConfigs = prev.instrument_configs.map(cfg => {
        if (cfg.name !== name) return cfg;
        const has = cfg.effects.includes(effect);
        const nextEffects = has
          ? cfg.effects.filter(e => e !== effect)
          : uniqueStrings([...cfg.effects, effect]);
        return { ...cfg, effects: nextEffects };
      });
      return {
        ...prev,
        instrument_configs: ensureInstrumentConfigs(prev.instruments, nextConfigs),
      };
    });
  };

  const resetInstrumentEffects = (name: string) => {
    setMidi(prev => {
      const instrumentIndex = prev.instruments.indexOf(name);
      const defaultConfig = createDefaultInstrumentConfig(name, instrumentIndex >= 0 ? instrumentIndex : 0);
      const nextConfigs = prev.instrument_configs.map(cfg => (
        cfg.name === name ? { ...cfg, effects: [...defaultConfig.effects] } : cfg
      ));
      return {
        ...prev,
        instrument_configs: ensureInstrumentConfigs(prev.instruments, nextConfigs),
      };
    });
  };

  const run = async (mode: 'midi' | 'render' | 'full') => {
    setIsRunning(true); setError(null); setRunId(null); setDebugRun(null); setAudioFile(null); setMidiJsonFile(null); setMidiMidFile(null); setPianoRoll(null); setRawResponse(null); setResponseStatus(null); setBlueprint(null);
    const buildMidiRequest = (params: MidiParameters) => ({
      ...params,
      genre: params.style,
      form: params.form.filter(Boolean),
      instrument_configs: params.instrument_configs.map(cfg => ({
        ...cfg,
        effects: cfg.effects.filter(Boolean),
      })),
    });
    const buildAudioRequest = (params: AudioRenderParameters) => ({
      ...params,
      sample_rate: Number(params.sample_rate),
      seconds: Number(params.seconds),
      master_gain_db: Number(params.master_gain_db),
    });

    const body: any = {};
    let endpoint: string;
    const midiPayload = buildMidiRequest(midi);
    const audioPayload = buildAudioRequest(audio);
    if (mode === 'midi') { endpoint = `${MODULE_PREFIX}/run/midi`; Object.assign(body, midiPayload); }
    else if (mode === 'render') { endpoint = `${MODULE_PREFIX}/run/render`; body.midi = midiPayload; body.audio = audioPayload; }
    else { endpoint = `${MODULE_PREFIX}/run/full`; body.midi = midiPayload; body.audio = audioPayload; }

    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      setResponseStatus(res.status);
      let data: any = null; try { data = await res.json(); } catch { setError('JSON parse error'); setIsRunning(false); return; }
      setRawResponse(data);
      if (!res.ok) { setError(data?.detail || data?.error || `HTTP ${res.status}`); setIsRunning(false); return; }
  setBlueprint(data?.blueprint ?? null);
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
  const selectableInstruments = [
    ...(INSTRUMENT_CHOICES as readonly string[]),
    ...available.filter(inst => !(INSTRUMENT_CHOICES as readonly string[]).includes(inst)),
  ];

  const formatBytes = (n?: number) => {
    if (!n || n <= 0) return '-';
    const units = ['B','KB','MB','GB'];
    let i=0; let v=n;
    while (v>=1024 && i<units.length-1) { v/=1024; i++; }
    return `${v.toFixed(1)} ${units[i]}`;
  };
  const formatSec = (s?: number | null) => (s==null? '-' : `${s.toFixed(2)}s`);
  const formatSummaryValue = (value: unknown, separator = ', '): string | undefined => {
    if (value === undefined || value === null) return undefined;
    if (Array.isArray(value)) {
      const parts = value
        .map(item => {
          if (item === undefined || item === null) return '';
          if (typeof item === 'object') {
            try {
              return JSON.stringify(item);
            } catch {
              return '';
            }
          }
          return String(item);
        })
        .filter(Boolean);
      if (parts.length === 0) return undefined;
      return parts.join(separator);
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return undefined;
      }
    }
    const text = String(value);
    if (text.trim() === '') return undefined;
    return text;
  };

  const blueprintMidi = blueprint?.midi as Record<string, any> | undefined;
  const blueprintAudio = blueprint?.audio as Record<string, any> | undefined;
  const blueprintInstrumentConfigs = Array.isArray(blueprintMidi?.instrument_configs)
    ? ((blueprintMidi!.instrument_configs as Record<string, any>[])
        .map(item => {
          const name = String(item?.name ?? '').trim();
          if (!name) return null;
          return {
            name,
            role: formatSummaryValue(item?.role) ?? '-',
            register: formatSummaryValue(item?.register) ?? '-',
            articulation: formatSummaryValue(item?.articulation) ?? '-',
            dynamic_range: formatSummaryValue(item?.dynamic_range) ?? '-',
            volume: typeof item?.volume === 'number' ? item.volume : undefined,
            pan: typeof item?.pan === 'number' ? item.pan : undefined,
            effects: Array.isArray(item?.effects) ? item.effects.map((eff: any) => String(eff)).filter(Boolean) : [],
          };
        })
        .filter((item): item is {
          name: string;
          role: string;
          register: string;
          articulation: string;
          dynamic_range: string;
          volume: number | undefined;
          pan: number | undefined;
          effects: string[];
        } => item !== null))
    : [];

  const blueprintMidiSummary: Array<[string, string]> = blueprintMidi
    ? ([
        ['style', formatSummaryValue(blueprintMidi.style)],
        ['mood', formatSummaryValue(blueprintMidi.mood)],
        ['tempo', blueprintMidi.tempo !== undefined ? `${blueprintMidi.tempo} bpm` : undefined],
        ['key', formatSummaryValue(blueprintMidi.key)],
        ['scale', formatSummaryValue(blueprintMidi.scale)],
        ['meter', formatSummaryValue(blueprintMidi.meter)],
        ['length', blueprintMidi.length_seconds !== undefined ? `${blueprintMidi.length_seconds}s` : undefined],
        ['bars', blueprintMidi.bars !== undefined ? String(blueprintMidi.bars) : undefined],
        ['dynamic_profile', formatSummaryValue(blueprintMidi.dynamic_profile)],
        ['arrangement_density', formatSummaryValue(blueprintMidi.arrangement_density)],
        ['harmonic_color', formatSummaryValue(blueprintMidi.harmonic_color)],
        ['form', formatSummaryValue(blueprintMidi.form, ' → ')],
        ['instruments', formatSummaryValue(blueprintMidi.instruments)],
      ].filter(([, value]) => value !== undefined) as Array<[string, string]>)
    : [];

  const blueprintAudioSummary: Array<[string, string]> = blueprintAudio
    ? ([
        ['sample_rate', blueprintAudio.sample_rate !== undefined ? `${blueprintAudio.sample_rate} Hz` : undefined],
        ['seconds', blueprintAudio.seconds !== undefined ? `${blueprintAudio.seconds}s` : undefined],
        ['master_gain_db', blueprintAudio.master_gain_db !== undefined ? `${blueprintAudio.master_gain_db} dB` : undefined],
      ].filter(([, value]) => value !== undefined) as Array<[string, string]>)
    : [];

  const blueprintHasData = blueprintMidiSummary.length > 0 || blueprintAudioSummary.length > 0 || blueprintInstrumentConfigs.length > 0;

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-black via-gray-950 to-black text-white px-6 py-10 space-y-10">
  <h1 className="text-3xl font-bold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-500">AI Param Test (Local Hybrid)</h1>
  <p className="text-sm text-gray-400 max-w-3xl">Eksperymentalny pipeline AI budowany na bazie lokalnych sampli: <span className='text-emerald-300'>MIDI → selekcja próbek → Audio</span>. Ta wersja zachowuje wszystkie restrykcje lokalne, ale będzie rozszerzana o generatywne modele. Wybieraj tylko instrumenty wykryte na backendzie.</p>

      <div className="grid md:grid-cols-3 gap-6">
        {/* MIDI Panel */}
        <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 space-y-4 col-span-2">
          <h2 className="font-semibold text-emerald-300">MIDI Parameters</h2>
          <div className="grid sm:grid-cols-2 gap-4 text-sm">
            <div>
              <label className="block mb-1">Style</label>
              <select
                value={midi.style}
                onChange={e => {
                  const value = e.target.value as StyleOption;
                  updateMidi({ style: value, genre: value });
                }}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {STYLE_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Mood</label>
              <select
                value={midi.mood}
                onChange={e => updateMidi({ mood: e.target.value as MoodOption })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {MOOD_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Key</label>
              <select
                value={midi.key}
                onChange={e => updateMidi({ key: e.target.value as KeyOption })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {KEY_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Scale</label>
              <select
                value={midi.scale}
                onChange={e => updateMidi({ scale: e.target.value as ScaleOption })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {SCALE_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Meter</label>
              <select
                value={midi.meter}
                onChange={e => updateMidi({ meter: e.target.value as MeterOption })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {METER_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Tempo: {midi.tempo} BPM</label>
              <input
                type="range"
                min={40}
                max={240}
                value={midi.tempo}
                onChange={e => updateMidi({ tempo: parseInt(e.target.value, 10) })}
                className="w-full"
              />
            </div>
            <div>
              <label className="block mb-1">Bars</label>
              <input
                type="number"
                min={1}
                max={512}
                value={midi.bars}
                onChange={e => updateMidi({ bars: parseInt(e.target.value, 10) || 1 })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              />
            </div>
            <div>
              <label className="block mb-1">Length (seconds)</label>
              <input
                type="number"
                min={30}
                max={3600}
                step={5}
                value={midi.length_seconds}
                onChange={e => updateMidi({ length_seconds: parseFloat(e.target.value) || 30 })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              />
            </div>
            <div>
              <label className="block mb-1">Dynamic Profile</label>
              <select
                value={midi.dynamic_profile}
                onChange={e => updateMidi({ dynamic_profile: e.target.value as DynamicProfileOption })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {DYNAMIC_PROFILE_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Arrangement Density</label>
              <select
                value={midi.arrangement_density}
                onChange={e => updateMidi({ arrangement_density: e.target.value as ArrangementDensityOption })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {ARRANGEMENT_DENSITY_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Harmonic Color</label>
              <select
                value={midi.harmonic_color}
                onChange={e => updateMidi({ harmonic_color: e.target.value as HarmonicColorOption })}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              >
                {HARMONIC_COLOR_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block mb-1">Seed (optional)</label>
              <input
                type="number"
                value={midi.seed ?? ''}
                onChange={e => {
                  const raw = e.target.value;
                  updateMidi({ seed: raw === '' ? null : parseInt(raw, 10) });
                }}
                className="w-full bg-black/60 p-2 rounded border border-gray-700"
              />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <label className="block mb-1">Form Blueprint</label>
              <div className="flex gap-2 text-[10px]">
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-2 py-1 rounded border border-gray-600 hover:border-emerald-400"
                >
                  Reset
                </button>
                <button
                  type="button"
                  onClick={clearForm}
                  className="px-2 py-1 rounded border border-gray-600 hover:border-red-400"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {midi.form.length === 0 && (
                <span className="text-[11px] text-gray-500">Brak sekcji — dodaj z presetów poniżej.</span>
              )}
              {midi.form.map((section, idx) => (
                <span key={`${section}-${idx}`} className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-700/30 border border-emerald-500/60 text-xs uppercase tracking-wide">
                  {section}
                  <button
                    type="button"
                    onClick={() => removeFormSection(idx)}
                    className="text-[10px] text-emerald-200 hover:text-emerald-100"
                    aria-label={`Remove ${section}`}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {FORM_SECTION_OPTIONS.map(option => (
                <button
                  key={option}
                  type="button"
                  onClick={() => addFormSection(option)}
                  className="text-xs px-3 py-1 rounded border border-gray-600 hover:border-emerald-400"
                >
                  {option}
                </button>
              ))}
            </div>
            <div className="text-[10px] text-gray-500">Dodawaj sekcje klikając preset. Reset przywraca domyślny układ, Clear usuwa wszystkie.</div>
          </div>
          <div>
            <label className="block mb-2">Instruments (only available)</label>
            <div className="flex flex-wrap gap-2">
              {selectableInstruments.map(inst => {
                const disabled = disableInst(inst);
                const active = midi.instruments.includes(inst);
                return (
                  <button
                    type="button"
                    key={inst}
                    disabled={disabled}
                    onClick={() => toggleInstrument(inst)}
                    className={`text-xs px-2 py-1 rounded border transition ${disabled ? 'opacity-30 cursor-not-allowed border-gray-800' : 'cursor-pointer'} ${active ? 'bg-emerald-600 border-emerald-400' : 'border-gray-600 hover:border-emerald-400'}`}
                  >
                    {inst}
                  </button>
                );
              })}
            </div>
            <div className="text-[10px] text-gray-500 mt-1">Niedostępne instrumenty są wyszarzone (brak sample na backendzie).</div>
          </div>
          {midi.instrument_configs.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-semibold text-emerald-200 text-sm">Instrument Profiles</h3>
              <div className="space-y-3">
                {midi.instrument_configs.map(cfg => (
                  <div key={cfg.name} className="bg-black/40 border border-gray-800 rounded-lg p-3 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="uppercase tracking-wide text-xs text-emerald-300">{cfg.name}</span>
                      <span className="text-[11px] text-gray-500">role: {cfg.role}</span>
                    </div>
                    <div className="grid sm:grid-cols-2 gap-3 text-xs">
                      <div>
                        <label className="block mb-1">Register</label>
                        <select
                          value={cfg.register}
                          onChange={e => updateInstrumentConfig(cfg.name, { register: e.target.value as RegisterOption })}
                          className="w-full bg-black/60 p-2 rounded border border-gray-700"
                        >
                          {REGISTER_OPTIONS.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block mb-1">Role</label>
                        <select
                          value={cfg.role}
                          onChange={e => updateInstrumentConfig(cfg.name, { role: e.target.value as RoleOption })}
                          className="w-full bg-black/60 p-2 rounded border border-gray-700"
                        >
                          {ROLE_OPTIONS.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block mb-1">Articulation</label>
                        <select
                          value={cfg.articulation}
                          onChange={e => updateInstrumentConfig(cfg.name, { articulation: e.target.value as ArticulationOption })}
                          className="w-full bg-black/60 p-2 rounded border border-gray-700"
                        >
                          {ARTICULATION_OPTIONS.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block mb-1">Dynamic Range</label>
                        <select
                          value={cfg.dynamic_range}
                          onChange={e => updateInstrumentConfig(cfg.name, { dynamic_range: e.target.value as DynamicRangeOption })}
                          className="w-full bg-black/60 p-2 rounded border border-gray-700"
                        >
                          {DYNAMIC_RANGE_OPTIONS.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block mb-1">Volume {cfg.volume.toFixed(2)}</label>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={cfg.volume}
                          onChange={e => updateInstrumentConfig(cfg.name, { volume: parseFloat(e.target.value) })}
                          className="w-full"
                        />
                      </div>
                      <div>
                        <label className="block mb-1">Pan {cfg.pan.toFixed(2)}</label>
                        <input
                          type="range"
                          min={-1}
                          max={1}
                          step={0.1}
                          value={cfg.pan}
                          onChange={e => updateInstrumentConfig(cfg.name, { pan: parseFloat(e.target.value) })}
                          className="w-full"
                        />
                      </div>
                    </div>
                    <div className="text-xs space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="block">Effects</label>
                        <button
                          type="button"
                          onClick={() => resetInstrumentEffects(cfg.name)}
                          className="px-2 py-1 rounded border border-gray-600 hover:border-emerald-400"
                        >
                          Reset
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {EFFECT_OPTIONS.map(effect => {
                          const active = cfg.effects.includes(effect);
                          return (
                            <button
                              key={effect}
                              type="button"
                              onClick={() => toggleInstrumentEffect(cfg.name, effect)}
                              className={`px-3 py-1 rounded border text-[11px] uppercase tracking-wide transition ${active ? 'bg-fuchsia-700/40 border-fuchsia-400 text-fuchsia-200' : 'border-gray-600 hover:border-fuchsia-300 text-gray-300'}`}
                            >
                              {effect}
                            </button>
                          );
                        })}
                      </div>
                      <div className="text-[10px] text-gray-500 flex flex-wrap gap-1">
                        {cfg.effects.length === 0 && <span>no effects</span>}
                        {cfg.effects.map(effect => (
                          <span key={effect} className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 uppercase tracking-wide">{effect}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
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

      {blueprintHasData && (
        <div className="bg-gray-900/50 border border-emerald-800/50 rounded-lg p-4 space-y-4">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold text-emerald-300 text-sm uppercase tracking-wide">Blueprint snapshot</h3>
            {runId && <span className="text-[11px] text-gray-500">run {runId}</span>}
          </div>
          <div className="grid md:grid-cols-3 gap-4 text-xs">
            <div className="space-y-2">
              <div className="text-emerald-200 font-semibold">Composition</div>
              {blueprintMidiSummary.length === 0 && <div className="text-gray-500">Brak danych MIDI.</div>}
              {blueprintMidiSummary.length > 0 && (
                <dl className="space-y-1 text-gray-300">
                  {blueprintMidiSummary.map(([label, value]) => (
                    <div key={label} className="flex gap-2">
                      <dt className="text-gray-500 capitalize w-32 flex-shrink-0">{label.replace(/_/g, ' ')}</dt>
                      <dd className="text-emerald-100 break-words">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            <div className="space-y-2">
              <div className="text-cyan-200 font-semibold">Audio Render</div>
              {blueprintAudioSummary.length === 0 && <div className="text-gray-500">Brak danych audio.</div>}
              {blueprintAudioSummary.length > 0 && (
                <dl className="space-y-1 text-gray-300">
                  {blueprintAudioSummary.map(([label, value]) => (
                    <div key={label} className="flex gap-2">
                      <dt className="text-gray-500 capitalize w-32 flex-shrink-0">{label.replace(/_/g, ' ')}</dt>
                      <dd className="text-emerald-100 break-words">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            <div className="space-y-2">
              <div className="text-fuchsia-200 font-semibold">Instrument configs</div>
              {blueprintInstrumentConfigs.length === 0 && <div className="text-gray-500">Brak profili instrumentów.</div>}
              {blueprintInstrumentConfigs.length > 0 && (
                <div className="space-y-2">
                  {blueprintInstrumentConfigs.map(cfg => (
                    <div key={cfg.name} className="border border-gray-800/70 rounded p-2 space-y-1 bg-black/40">
                      <div className="text-emerald-200 font-semibold uppercase tracking-wide">{cfg.name}</div>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-gray-400">
                        <span>role: <span className="text-gray-200">{cfg.role}</span></span>
                        <span>register: <span className="text-gray-200">{cfg.register}</span></span>
                        <span>articulation: <span className="text-gray-200">{cfg.articulation}</span></span>
                        <span>dynamic: <span className="text-gray-200">{cfg.dynamic_range}</span></span>
                        {typeof cfg.volume === 'number' && <span>vol: <span className="text-gray-200">{cfg.volume.toFixed(2)}</span></span>}
                        {typeof cfg.pan === 'number' && <span>pan: <span className="text-gray-200">{cfg.pan.toFixed(2)}</span></span>}
                      </div>
                      {cfg.effects.length > 0 && (
                        <div className="flex flex-wrap gap-1 text-[9px] text-gray-500">
                          {cfg.effects.map(effect => (
                            <span key={effect} className="px-2 py-0.5 border border-gray-700 rounded uppercase tracking-wide">{effect}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
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
              <audio controls src={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${audioFile}`} className="w-full" />
              <div className="text-[10px] text-gray-500 mt-1 break-all">{audioFile}</div>
            </div>
          )}
          {midiJsonFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-orange-300 mb-2">MIDI Pattern (JSON)</h3>
              <a className="underline" target="_blank" href={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${midiJsonFile}`}>{midiJsonFile}</a>
              <div className="text-[10px] text-gray-500 mt-1">Strukturalna reprezentacja wygenerowanego patternu.</div>
            </div>
          )}
          {midiMidFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-fuchsia-300 mb-2">MIDI File (.mid)</h3>
              <a className="underline" target="_blank" href={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${midiMidFile}`}>{midiMidFile}</a>
              <div className="text-[10px] text-gray-500 mt-1">Pobierz plik MIDI do DAW.</div>
            </div>
          )}
          {pianoRoll && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-cyan-300 mb-2">Piano Roll</h3>
              <img src={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${pianoRoll}`} alt="pianoroll" className="w-full rounded" />
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
            <button onClick={()=>rebuildInventory('quick')} className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 border border-gray-600 text-[11px]">Rebuild</button>
            <button onClick={()=>rebuildInventory('deep')} className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 border border-gray-600 text-[11px]">Deep Rebuild</button>
          </div>
          <div className="text-[10px] text-gray-600 mt-2">Endpoint: {MODULE_PREFIX}/available-instruments</div>
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
              <div className="text-[10px] text-gray-600 mt-2">Root: {inventory.root} • Schema: v{inventory.schema_version ?? 'n/a'} • Deep: {String(inventory.deep ?? false)}</div>
            )}
            <div className="text-[10px] text-gray-600 mt-2">Zapisane w inventory.json</div>
        </div>
      </div>

      {/* Samples table */}
      <div className="bg-gray-900/40 p-4 rounded-lg border border-gray-800 text-xs">
        <div className="flex items-end justify-between mb-3 gap-3 flex-wrap">
          <h3 className="font-semibold text-gray-300">Samples (from inventory)</h3>
          <div className="flex gap-2 items-center">
            <select value={sampleFilterInst} onChange={e=>setSampleFilterInst(e.target.value)} className="bg-black/60 p-1.5 rounded border border-gray-700">
              <option value="">All instruments</option>
              {Object.keys(inventory?.instruments || {}).sort().map(k => <option key={k} value={k}>{k}</option>)}
            </select>
            <input value={sampleFilterText} onChange={e=>setSampleFilterText(e.target.value)} placeholder="Search..." className="bg-black/60 p-1.5 rounded border border-gray-700" />
          </div>
        </div>
        {!inventory?.samples || inventory.samples.length===0 ? (
          <div className="text-gray-500">Brak danych próbek. Użyj Load/Deep Rebuild.</div>
        ) : (
          <div className="overflow-auto max-h-96">
            <table className="min-w-full border-collapse">
              <thead className="sticky top-0 bg-gray-900">
                <tr className="text-gray-400">
                  <th className="text-left p-2 border-b border-gray-800">instrument</th>
                  <th className="text-left p-2 border-b border-gray-800">subtype</th>
                  <th className="text-left p-2 border-b border-gray-800">family</th>
                  <th className="text-left p-2 border-b border-gray-800">category</th>
                  <th className="text-left p-2 border-b border-gray-800">pitch</th>
                  <th className="text-left p-2 border-b border-gray-800">file</th>
                  <th className="text-left p-2 border-b border-gray-800">size</th>
                  <th className="text-left p-2 border-b border-gray-800">len</th>
                  <th className="text-left p-2 border-b border-gray-800">sr</th>
                </tr>
              </thead>
              <tbody>
                {inventory.samples
                  .filter(s => !sampleFilterInst || s.instrument === sampleFilterInst)
                  .filter(s => {
                    if (!sampleFilterText) return true;
                    const q = sampleFilterText.toLowerCase();
                    return (
                      s.id.toLowerCase().includes(q) ||
                      s.file_rel.toLowerCase().includes(q) ||
                      (s.subtype||'').toLowerCase().includes(q) ||
                      (s.family||'').toLowerCase().includes(q) ||
                      (s.category||'').toLowerCase().includes(q) ||
                      (s.pitch||'').toLowerCase().includes(q)
                    );
                  })
                  .map((s, i) => (
                    <tr key={`${s.instrument}-${s.id}-${i}`} className="hover:bg-gray-800/40">
                      <td className="p-2 border-b border-gray-800 text-emerald-300">{s.instrument}</td>
                      <td className="p-2 border-b border-gray-800">{s.subtype || '-'}</td>
                      <td className="p-2 border-b border-gray-800">{s.family || '-'}</td>
                      <td className="p-2 border-b border-gray-800">{s.category || '-'}</td>
                      <td className="p-2 border-b border-gray-800">{s.pitch || '-'}</td>
                      <td className="p-2 border-b border-gray-800 break-all">{s.file_rel}</td>
                      <td className="p-2 border-b border-gray-800">{formatBytes(s.bytes)}</td>
                      <td className="p-2 border-b border-gray-800">{formatSec(s.length_sec)}</td>
                      <td className="p-2 border-b border-gray-800">{s.sample_rate ?? '-'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

  <div className="mt-12 text-center text-xs text-gray-600">AI Param Test UI • Strict local samples (baseline)</div>
    </div>
  );
}
