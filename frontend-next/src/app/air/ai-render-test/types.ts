import type {
  RegisterOption,
  RoleOption,
  ArticulationOption,
  DynamicRangeOption,
  StyleOption,
  MoodOption,
  KeyOption,
  ScaleOption,
  MeterOption,
  DynamicProfileOption,
  ArrangementDensityOption,
  HarmonicColorOption,
} from './constants';

export interface InstrumentConfig {
  name: string;
  register: RegisterOption;
  role: RoleOption;
  volume: number;
  pan: number;
  articulation: ArticulationOption;
  dynamic_range: DynamicRangeOption;
  effects: string[];
}

export interface MidiParameters {
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

export interface AudioRenderParameters {
  sample_rate: number;
  seconds: number;
  master_gain_db: number;
}

export interface DebugEvent {
  ts: number;
  stage: string;
  message: string;
  data?: Record<string, unknown> | null;
}

export interface DebugRun {
  run_id: string;
  events: DebugEvent[];
}

export interface AvailableInstruments {
  available: string[];
  count: number;
}

export interface InventoryInstrumentInfo {
  count: number;
  examples: string[];
}

export interface InventorySampleMeta {
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

export interface InventoryPayload {
  schema_version?: string;
  deep?: boolean;
  generated_at: number;
  root: string;
  instruments: Record<string, InventoryInstrumentInfo>;
  samples?: InventorySampleMeta[];
}

export interface ChatProviderInfo {
  id: string;
  name: string;
  default_model: string;
}

export interface ParamifyAppliedPlan {
  midi?: MidiParameters | null;
  audio?: AudioRenderParameters | null;
}

export interface ParamifyNormalizedPlan {
  midi?: Partial<MidiParameters> | null;
  audio?: Partial<AudioRenderParameters> | null;
}

export interface ParamifyResultView {
  provider?: string;
  model?: string;
  raw?: string | null;
  parsed?: unknown;
  normalized?: ParamifyNormalizedPlan | null;
  applied?: ParamifyAppliedPlan | null;
  errors?: string[] | null;
}

// Samples listing for a given instrument (for preview/select)
export interface SampleListItem {
  id: string;
  name: string;
  url: string | null;
  file: string;
  subtype?: string | null;
  family?: string | null;
  category?: string | null;
  pitch?: string | null;
}

export interface SampleListResponse {
  instrument: string;
  count: number;
  offset?: number;
  limit?: number;
  items: SampleListItem[];
  default?: SampleListItem | null;
}
