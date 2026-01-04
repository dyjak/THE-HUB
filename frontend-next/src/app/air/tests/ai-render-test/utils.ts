import {
  ARTICULATION_OPTIONS,
  ARRANGEMENT_DENSITY_OPTIONS,
  DEFAULT_INSTRUMENTS,
  DYNAMIC_PROFILE_OPTIONS,
  DYNAMIC_RANGE_OPTIONS,
  HARMONIC_COLOR_OPTIONS,
  KEY_OPTIONS,
  METER_OPTIONS,
  MOOD_OPTIONS,
  REGISTER_OPTIONS,
  ROLE_OPTIONS,
  SCALE_OPTIONS,
  STYLE_OPTIONS,
} from './constants';
import type {
  AudioRenderParameters,
  InstrumentConfig,
  MidiParameters,
} from './types';

type StringOptions = readonly string[];

export const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export const toNumber = (value: unknown, fallback: number): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

export const pickFrom = <T extends StringOptions>(value: unknown, options: T, fallback: T[number]): T[number] => {
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

export const uniqueStrings = (items: string[]): string[] => {
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

// Effects removed from model; parser retained as noop fallback (returns empty array) if referenced accidentally.
export const parseEffects = (_value: unknown): string[] => [];

export const createDefaultInstrumentConfig = (name: string, index = 0): InstrumentConfig => {
  const lower = name.toLowerCase();
  let register: (typeof REGISTER_OPTIONS)[number] = 'mid';
  let role: (typeof ROLE_OPTIONS)[number] = index === 0 ? 'lead' : 'accompaniment';
  let articulation: (typeof ARTICULATION_OPTIONS)[number] = 'sustain';
  let dynamic_range: (typeof DYNAMIC_RANGE_OPTIONS)[number] = 'moderate';
  // effects removed
  let volume = 0.8;
  let pan = clamp(-0.2 + index * 0.3, -0.6, 0.6);

  if (['bass','bass_synth','bass_guitar','808','reese'].includes(lower)) {
    register = 'low';
    role = 'bass';
    dynamic_range = 'intense';
    articulation = 'legato';
  // effects removed
    volume = 0.9;
    pan = 0;
  } else if (['kick','snare','hihat','clap','rim','tom','perc','drumkit'].includes(lower)) {
    register = 'low';
    role = 'percussion';
    dynamic_range = 'intense';
    articulation = 'percussive';
  // effects removed
    volume = 0.95;
    pan = 0;
  } else if (['pad','strings','choir'].includes(lower)) {
    register = 'full';
    role = 'pad';
    articulation = 'sustain';
  // effects removed
    volume = 0.85;
  } else if (['lead','synth','guitar','piano','flute','trumpet','saxophone'].includes(lower)) {
    role = index === 0 ? 'lead' : 'accompaniment';
    register = lower === 'flute' ? 'high' : 'mid';
    articulation = ['synth','flute'].includes(lower) ? 'legato' : 'sustain';
  // effects removed
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
  };
};

export const toInstrumentConfig = (raw: unknown): InstrumentConfig | null => {
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
  return { name, register, role, articulation, dynamic_range, volume, pan };
};

export const ensureInstrumentConfigs = (instruments: string[], existing: InstrumentConfig[]): InstrumentConfig[] => {
  const byName = new Map(existing.map(cfg => [cfg.name, cfg] as const));
  return instruments.map((inst, index) => {
    const prev = byName.get(inst);
    if (!prev) return createDefaultInstrumentConfig(inst, index);
    return {
      ...prev,
      name: inst,
    };
  });
};

export const normalizeMidi = (input: Partial<MidiParameters> | Record<string, unknown>): MidiParameters => {
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

  // form removed

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
    dynamic_profile,
    arrangement_density,
    harmonic_color,
    instruments: safeInstruments,
    instrument_configs,
    seed,
  };
};

export const normalizeAudio = (input: Partial<AudioRenderParameters> | Record<string, unknown>): AudioRenderParameters => {
  const sample_rate = clamp(Math.round(toNumber(input.sample_rate, 44100)), 8000, 192000);
  const seconds = clamp(toNumber(input.seconds, 6), 0.5, 600);
  const master_gain_db = toNumber(input.master_gain_db, -3);
  return { sample_rate, seconds, master_gain_db };
};

export const cloneMidi = (params: MidiParameters): MidiParameters => ({
  ...params,
  instruments: [...params.instruments],
  instrument_configs: params.instrument_configs.map(cfg => ({ ...cfg })),
});

export const cloneAudio = (params: AudioRenderParameters): AudioRenderParameters => ({ ...params });

export const DEFAULT_MIDI = cloneMidi(normalizeMidi({}));
export const DEFAULT_AUDIO = cloneAudio(normalizeAudio({}));
