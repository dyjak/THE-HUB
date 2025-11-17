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
} from "./constants";
import type { InstrumentConfig, MidiParameters } from "./midiTypes";

type StringOptions = readonly string[];

export const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export const toNumber = (value: unknown, fallback: number): number => {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

export const pickFrom = <T extends StringOptions>(value: unknown, options: T, fallback: T[number]): T[number] => {
  if (typeof value === "string") {
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

// For creative/string parameters coming from the model, we want to keep
// custom values while still snapping to our suggested options when they match.
// If the value is empty/undefined we fall back, otherwise we return either the
// canonical option (case-insensitive match) or the raw trimmed string.
export const normalizeWithSuggestions = <T extends StringOptions>(
  value: unknown,
  options: T,
  fallback: T[number],
): string => {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return fallback;
    const lower = trimmed.toLowerCase();
    const match = (options as readonly string[]).find(opt => opt.toLowerCase() === lower);
    return match ?? trimmed;
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

export const createDefaultInstrumentConfig = (name: string, index = 0): InstrumentConfig => {
  const lower = name.toLowerCase();
  let register: string = "Mid";
  let role: string = index === 0 ? "Lead" : "Accompaniment";
  let articulation: string = "Sustain";
  let dynamic_range: string = "Moderate";

  if (["bass","bass_synth","bass_guitar","808","reese"].includes(lower)) {
    register = "Low";
    role = "Bass";
    dynamic_range = "Intense";
    articulation = "Legato";
  } else if (["kick","snare","hihat","clap","rim","tom","perc","drumkit"].includes(lower)) {
    register = "Low";
    role = "Percussion";
    dynamic_range = "Intense";
    articulation = "Percussive";
  } else if (["pad","strings","choir"].includes(lower)) {
    register = "Full";
    role = "Pad";
    articulation = "Sustain";
  } else if (["lead","synth","guitar","piano","flute","trumpet","saxophone"].includes(lower)) {
    role = index === 0 ? "Lead" : "Accompaniment";
    register = lower === "flute" ? "High" : "Mid";
    articulation = ["synth","flute"].includes(lower) ? "Legato" : "Sustain";
  }

  return {
    name,
    register,
    role,
    articulation,
    dynamic_range,
  };
};

export const toInstrumentConfig = (raw: unknown): InstrumentConfig | null => {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as Record<string, unknown>;
  const name = String(source.name ?? "").trim();
  if (!name) return null;
  const register = normalizeWithSuggestions(source.register, REGISTER_OPTIONS, REGISTER_OPTIONS[1] ?? "Mid");
  const role = normalizeWithSuggestions(source.role, ROLE_OPTIONS, ROLE_OPTIONS[1] ?? "Accompaniment");
  const articulation = normalizeWithSuggestions(source.articulation, ARTICULATION_OPTIONS, ARTICULATION_OPTIONS[0] ?? "Sustain");
  const dynamic_range = normalizeWithSuggestions(source.dynamic_range, DYNAMIC_RANGE_OPTIONS, DYNAMIC_RANGE_OPTIONS[1] ?? "Moderate");
  return { name, register, role, articulation, dynamic_range };
};

export const ensureInstrumentConfigs = (instruments: string[], existing: InstrumentConfig[]): InstrumentConfig[] => {
  // Build lookup maps by exact name and by lowercase name to tolerate
  // casing differences or minor naming mismatches from the model.
  const byExact = new Map(existing.map(cfg => [cfg.name, cfg] as const));
  const byLower = new Map(existing.map(cfg => [cfg.name.toLowerCase(), cfg] as const));

  return instruments.map((inst, index) => {
    const exact = byExact.get(inst);
    if (exact) {
      return { ...exact, name: inst };
    }
    const lower = byLower.get(inst.toLowerCase());
    if (lower) {
      return { ...lower, name: inst };
    }
    // No config provided by the model – fall back to heuristic defaults.
    return createDefaultInstrumentConfig(inst, index);
  });
};

export const normalizeMidi = (input: Partial<MidiParameters> | Record<string, unknown>): MidiParameters => {
  const style = normalizeWithSuggestions(input.style ?? (input as any).genre, STYLE_OPTIONS, STYLE_OPTIONS[0] ?? "Ambient");
  const mood = normalizeWithSuggestions(input.mood, MOOD_OPTIONS, MOOD_OPTIONS[0] ?? "Calm");
  const key = normalizeWithSuggestions(input.key, KEY_OPTIONS, "C");
  const scale = normalizeWithSuggestions(input.scale, SCALE_OPTIONS, SCALE_OPTIONS[0] ?? "Major");
  const meter = normalizeWithSuggestions(input.meter, METER_OPTIONS, "4/4");
  const dynamic_profile = normalizeWithSuggestions(input.dynamic_profile, DYNAMIC_PROFILE_OPTIONS, DYNAMIC_PROFILE_OPTIONS[1] ?? "Moderate");
  const arrangement_density = normalizeWithSuggestions(input.arrangement_density, ARRANGEMENT_DENSITY_OPTIONS, ARRANGEMENT_DENSITY_OPTIONS[1] ?? "Balanced");
  const harmonic_color = normalizeWithSuggestions(input.harmonic_color, HARMONIC_COLOR_OPTIONS, HARMONIC_COLOR_OPTIONS[0] ?? "Diatonic");
  const tempo = clamp(Math.round(toNumber(input.tempo, 80)), 20, 300);
  const bars = clamp(Math.round(toNumber(input.bars, 16)), 1, 512);
  const length_seconds = clamp(toNumber(input.length_seconds, 180), 30, 3600);

  const instrumentsRaw = Array.isArray(input.instruments)
    ? input.instruments
    : typeof input.instruments === "string"
      ? (input.instruments as string).split(",")
      : Array.from(DEFAULT_INSTRUMENTS);
  const instruments = uniqueStrings(instrumentsRaw.map(item => String(item).trim()).filter(Boolean));
  const safeInstruments = instruments.length ? instruments : Array.from(DEFAULT_INSTRUMENTS);

  const configsRaw = Array.isArray(input.instrument_configs) ? input.instrument_configs : [];
  const parsedConfigs = configsRaw.map(toInstrumentConfig).filter(Boolean) as InstrumentConfig[];
  const instrument_configs = ensureInstrumentConfigs(safeInstruments, parsedConfigs);

  let seed: number | null = null;
  if ((input as any).seed !== undefined && (input as any).seed !== null && (input as any).seed !== "") {
    const seedNum = Number((input as any).seed);
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

export const cloneMidi = (params: MidiParameters): MidiParameters => ({
  ...params,
  instruments: [...params.instruments],
  instrument_configs: params.instrument_configs.map(cfg => ({ ...cfg })),
});
