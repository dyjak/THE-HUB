// typy danych dla kroku 1 (param_generation) i przekazania meta dalej.
// listy opcji z ./constants traktujemy jako „sugestie” do ui, a nie twarde ograniczenia.
// dlatego pola są tu stringami: model/backend może zwrócić wartość spoza listy.

export interface InstrumentConfig {
  name: string;
  register: string;
  role: string;
  articulation: string;
  dynamic_range: string;
}

export interface ParamPlan {
  // oryginalny prompt użytkownika z kroku 1.
  // opcjonalne, żeby zachować kompatybilność wstecz (stare plany / stare odpowiedzi modeli).
  user_prompt?: string;
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
  // opcjonalny seed (używany po stronie frontendu do powtarzalności runów)
  seed?: number | null;
}

// minimalne meta przekazywane z param_generation do midi_generation
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
