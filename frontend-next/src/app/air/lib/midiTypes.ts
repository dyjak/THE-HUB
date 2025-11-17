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
} from "./constants";

export interface InstrumentConfig {
  name: string;
  register: RegisterOption;
  role: RoleOption;
  volume: number;
  pan: number;
  articulation: ArticulationOption;
  dynamic_range: DynamicRangeOption;
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
  dynamic_profile: DynamicProfileOption;
  arrangement_density: ArrangementDensityOption;
  harmonic_color: HarmonicColorOption;
  instruments: string[];
  instrument_configs: InstrumentConfig[];
}

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
