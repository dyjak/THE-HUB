// We treat option lists in ./constants as *suggested* presets only.
// To allow fully generative values from the model, all meta fields and
// instrument config fields are typed as plain strings here.

export interface InstrumentConfig {
  name: string;
  register: string;
  role: string;
  articulation: string;
  dynamic_range: string;
}

export interface ParamPlan {
  style: string;
  genre: string;
  mood: string;
  tempo: number;
  key: string;
  scale: string;
  meter: string;
  bars: number;
  length_seconds: number;
  dynamic_profile: string;
  arrangement_density: string;
  harmonic_color: string;
  instruments: string[];
  instrument_configs: InstrumentConfig[];
  // Optional seed used only on the frontend to pass through generative runs
  seed?: number | null;
}

// Minimalne meta przekazywane z param_generation do midi_generation
export type ParamPlanMeta = ParamPlan;

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
