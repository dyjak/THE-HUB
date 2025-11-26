"use client";
import { memo, useCallback, useMemo } from "react";
import {
  ARRANGEMENT_DENSITY_OPTIONS,
  ARTICULATION_OPTIONS,
  DYNAMIC_PROFILE_OPTIONS,
  DYNAMIC_RANGE_OPTIONS,
  HARMONIC_COLOR_OPTIONS,
  KEY_OPTIONS,
  METER_OPTIONS,
  MOOD_OPTIONS,
  SCALE_OPTIONS,
  STYLE_OPTIONS,
} from "../lib/constants";
import type { InstrumentConfig, ParamPlan } from "../lib/paramTypes";
import { SampleSelector } from "./SampleSelector";

interface ParamPanelProps {
  midi: ParamPlan;
  availableInstruments: string[];
  selectableInstruments: string[];
  fxSubtypes?: string[];
  apiBase: string;
  apiPrefix: string;
  modulePrefix: string;
  onUpdate: (patch: Partial<ParamPlan>) => void;
  onToggleInstrument: (instrument: string) => void;
  onUpdateInstrumentConfig: (name: string, patch: Partial<InstrumentConfig>) => void;
  selectedSamples: Record<string, string | undefined>;
  onSelectSample: (instrument: string, sampleId: string | null) => void;
  compact?: boolean;
  columns?: 1 | 2 | 3 | 4;
  hideFx?: boolean;
}

const ParamPanelComponent = ({
  midi,
  availableInstruments,
  selectableInstruments,
  onUpdate,
  onToggleInstrument,
  onUpdateInstrumentConfig,
  fxSubtypes = [],
  apiBase,
  apiPrefix,
  modulePrefix,
  selectedSamples,
  onSelectSample,
  compact = false,
  columns = 2,
  hideFx = false,
}: ParamPanelProps) => {
  const handleStyleChange = useCallback<React.ChangeEventHandler<HTMLSelectElement>>(
    event => {
      const value = event.target.value as ParamPlan["style"];
      onUpdate({ style: value, genre: value });
    },
    [onUpdate],
  );

  const handleNumberChange = useCallback(
    (field: keyof Pick<ParamPlan, "tempo" | "bars" | "length_seconds">, min: number, fallback: number) =>
      (event: React.ChangeEvent<HTMLInputElement>) => {
        const parsed = Number(event.target.value);
        if (Number.isNaN(parsed)) {
          onUpdate({ [field]: fallback } as Partial<ParamPlan>);
          return;
        }
        onUpdate({ [field]: Math.max(min, parsed) } as Partial<ParamPlan>);
      },
    [onUpdate],
  );

  const isInstrumentDisabled = useCallback((instrument: string) => !availableInstruments.includes(instrument), [availableInstruments]);

  const handleInstrumentToggle = useCallback(
    (instrument: string) => () => {
      if (availableInstruments.length === 0 || availableInstruments.includes(instrument)) {
        onToggleInstrument(instrument);
      }
    },
    [availableInstruments, onToggleInstrument],
  );

  const handleInstrumentConfigChange = useCallback(
    (name: string, patch: Partial<InstrumentConfig>) => onUpdateInstrumentConfig(name, patch),
    [onUpdateInstrumentConfig],
  );

  const gridCols = columns === 4 ? "sm:grid-cols-4" : columns === 3 ? "sm:grid-cols-3" : columns === 1 ? "sm:grid-cols-1" : "sm:grid-cols-2";
  const sizeClass = compact ? "text-xs" : "text-sm";

  const DRUMS = ["Kick", "Snare", "Clap", "Hat"];
  const FX = ["Impact", "Riser", "Subdrop", "Swell", "Texture"];
  const genericInstruments = selectableInstruments.filter(inst => !DRUMS.includes(inst) && !FX.includes(inst));

  // Derive instruments that are present in the MIDI meta but not available in the inventory.
  const missingInstruments = useMemo(
    () => midi.instruments.filter(inst => !availableInstruments.includes(inst)),
    [midi.instruments, availableInstruments],
  );

  // Helper to ensure the current value is always present in the select options
  const withCurrent = useCallback(<T extends string>(options: readonly T[], current: string | undefined | null): string[] => {
    const base = Array.from(options) as string[];
    if (!current) return base;
    // Prefer existing preset casing when value matches ignoring case
    const lower = current.toLowerCase();
    if (!base.some(opt => opt.toLowerCase() === lower)) {
      base.push(current);
    }
    return base;
  }, []);

  const styleOptions = useMemo(() => withCurrent(STYLE_OPTIONS, midi.style), [withCurrent, midi.style]);
  const moodOptions = useMemo(() => withCurrent(MOOD_OPTIONS, midi.mood), [withCurrent, midi.mood]);
  const keyOptions = useMemo(() => withCurrent(KEY_OPTIONS, midi.key), [withCurrent, midi.key]);
  const scaleOptions = useMemo(() => withCurrent(SCALE_OPTIONS, midi.scale), [withCurrent, midi.scale]);
  const meterOptions = useMemo(() => withCurrent(METER_OPTIONS, midi.meter), [withCurrent, midi.meter]);
  const dynamicProfileOptions = useMemo(() => withCurrent(DYNAMIC_PROFILE_OPTIONS, midi.dynamic_profile), [withCurrent, midi.dynamic_profile]);
  const arrangementDensityOptions = useMemo(() => withCurrent(ARRANGEMENT_DENSITY_OPTIONS, midi.arrangement_density), [withCurrent, midi.arrangement_density]);
  const harmonicColorOptions = useMemo(() => withCurrent(HARMONIC_COLOR_OPTIONS, midi.harmonic_color), [withCurrent, midi.harmonic_color]);

  return (
    <div className="bg-gray-900/80 p-4 rounded-lg border border-purple-800/40 space-y-4 col-span-2">
      <h2 className="font-semibold text-purple-300">Parametry Muzyczne</h2>
      {missingInstruments.length > 0 && (
        <div className="flex items-start gap-2 text-xs bg-amber-900/40 border border-amber-600/70 text-amber-100 px-3 py-2 rounded-lg">
          <span className="mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-black text-[10px] font-bold">!</span>
          <div>
            <div className="font-semibold uppercase tracking-widest text-[10px] text-amber-200">Instrumenty poza lokalną bazą sampli</div>
            <div className="mt-0.5 text-[11px]">
              Model AI zwrócił instrumenty, dla których nie znaleziono lokalnych sampli:&nbsp;
              <span className="font-mono">
                {missingInstruments.join(", ")}
              </span>
              . Możesz zmienić wybór instrumentów lub ręcznie dobrać najbliższy odpowiednik.
            </div>
          </div>
        </div>
      )}
      <div className={`grid ${gridCols} gap-4 ${sizeClass}`}>
        <div>
          <label className="block mb-1">Style</label>
          <select value={midi.style} onChange={handleStyleChange} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {styleOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Mood</label>
          <select value={midi.mood} onChange={event => onUpdate({ mood: event.target.value as ParamPlan["mood"] })} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {moodOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Key</label>
          <select value={midi.key} onChange={event => onUpdate({ key: event.target.value as ParamPlan["key"] })} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {keyOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Scale</label>
          <select value={midi.scale} onChange={event => onUpdate({ scale: event.target.value as ParamPlan["scale"] })} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {scaleOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Meter</label>
          <select value={midi.meter} onChange={event => onUpdate({ meter: event.target.value as ParamPlan["meter"] })} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {meterOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Tempo: {midi.tempo} BPM</label>
          <input type="range" min={40} max={240} value={midi.tempo} onChange={event => onUpdate({ tempo: parseInt(event.target.value, 10) })} className="w-full" />
        </div>
        <div>
          <label className="block mb-1">Bars</label>
          <input type="number" min={1} max={512} value={midi.bars} onChange={handleNumberChange("bars", 1, 1)} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors" />
        </div>
        <div>
          <label className="block mb-1">Length (seconds)</label>
          <input type="number" min={30} max={3600} step={5} value={midi.length_seconds} onChange={handleNumberChange("length_seconds", 30, 30)} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors" />
        </div>
        <div>
          <label className="block mb-1">Dynamic Profile</label>
          <select value={midi.dynamic_profile} onChange={event => onUpdate({ dynamic_profile: event.target.value as ParamPlan["dynamic_profile"] })} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {dynamicProfileOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Arrangement Density</label>
          <select value={midi.arrangement_density} onChange={event => onUpdate({ arrangement_density: event.target.value as ParamPlan["arrangement_density"] })} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {arrangementDensityOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Harmonic Color</label>
          <select value={midi.harmonic_color} onChange={event => onUpdate({ harmonic_color: event.target.value as ParamPlan["harmonic_color"] })} className="w-full bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
            {harmonicColorOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
      </div>

      <div className={compact ? "text-xs" : undefined}>
        <label className="block mb-2">Instruments (only available)</label>
        {(() => {
          const present = DRUMS.filter(d => availableInstruments.includes(d));
          if (present.length === 0) return null;
          return (
            <div className="mb-2 p-2 border border-purple-800/30 rounded bg-black/30">
              <div className="text-xs text-gray-400 mb-1">Drums</div>
              <div className="flex flex-wrap gap-2">
                {present.map(inst => (
                  <button
                    key={inst}
                    onClick={handleInstrumentToggle(inst)}
                    className={`px-3 py-1 rounded-full border text-xs ${midi.instruments.includes(inst) ? "bg-purple-700 border-purple-500" : "bg-black/50 border-purple-800/20 hover:bg-black/60"}`}
                  >{inst}</button>
                ))}
              </div>
            </div>
          );
        })()}
        {!hideFx && (() => {
          const presentFx = FX.filter(f => availableInstruments.includes(f) || midi.instruments.includes(f));
          if (presentFx.length === 0) return null;
          return (
            <div className="mb-2 p-2 border border-purple-800/30 rounded bg-black/30">
              <div className="text-xs text-gray-400 mb-1">FX</div>
              <div className="flex flex-wrap gap-2">
                {presentFx.map(inst => (
                  <button
                    key={inst}
                    onClick={handleInstrumentToggle(inst)}
                    className={`px-3 py-1 rounded-full border text-xs ${midi.instruments.includes(inst) ? "bg-purple-700 border-purple-500" : "bg-black/50 border-purple-800/20 hover:bg-black/60"}`}
                  >{inst}</button>
                ))}
              </div>
            </div>
          );
        })()}
        <div className="mb-1 text-xs text-gray-400">Instruments</div>
        <div className="flex flex-wrap gap-2">
          {genericInstruments.map(instrument => {
            const active = midi.instruments.includes(instrument);
            const disabled = isInstrumentDisabled(instrument) && !active;
            const baseClasses = active ? "bg-purple-700 border-purple-500 text-white" : "bg-black/50 border-purple-800/20";
            const disabledClasses = disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer hover:bg-black/60";
            return (
              <button
                key={instrument}
                onClick={handleInstrumentToggle(instrument)}
                disabled={disabled}
                className={`px-3 py-1 rounded-full border text-xs ${baseClasses} ${disabledClasses}`}
              >
                {instrument}
              </button>
            );
          })}
        </div>
        <div className="text-[10px] text-gray-500 mt-1">Niedostępne instrumenty są wyszarzone (brak sample na backendzie).</div>
      </div>

      {midi.instrument_configs.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs text-gray-400 uppercase tracking-widest">Instrument configs</div>
          {midi.instrument_configs.filter(cfg => cfg.name !== "drums").map(config => (
            <div key={config.name} className="bg-black/40 border border-purple-800/20 rounded-lg p-4 space-y-3">
              <div className="flex flex-wrap gap-3 items-center justify-between">
                <div className="flex flex-wrap gap-3 items-center">
                  <div className="font-semibold text-purple-200">{config.name}</div>
                  <div className="text-[11px] text-gray-500">{config.role} • {config.register}</div>
                </div>
                <button
                  type="button"
                  onClick={() => onToggleInstrument(config.name)}
                  className="ml-auto text-[11px] px-2 py-1.5 rounded border border-red-600/70 text-red-300 hover:bg-red-900/40 transition-colors"
                  title="Usuń instrument"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                    <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
              <SampleSelector
                apiBase={apiBase}
                apiPrefix={apiPrefix}
                modulePrefix={modulePrefix}
                instrument={config.name}
                selectedId={selectedSamples[config.name] || null}
                onChange={onSelectSample}
              />
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-[11px]">
                <label className="flex flex-col gap-1 min-w-[120px]">
                  Dynamic range
                  <select value={config.dynamic_range}
                    onChange={event => handleInstrumentConfigChange(config.name, { dynamic_range: event.target.value as InstrumentConfig["dynamic_range"] })}
                    className="bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
                    {withCurrent(DYNAMIC_RANGE_OPTIONS, config.dynamic_range).map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 min-w-[120px]">
                  Role
                  <select value={config.role}
                    onChange={event => handleInstrumentConfigChange(config.name, { role: event.target.value as InstrumentConfig["role"] })}
                    className="bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors">
                    {withCurrent(["Lead", "Accompaniment", "Rhythm", "Pad", "Bass", "Percussion", "Fx"], config.role ?? "").map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 min-w-[120px]">
                  Register
                  <select
                    value={config.register}
                    onChange={event => handleInstrumentConfigChange(config.name, { register: event.target.value as InstrumentConfig["register"] })}
                    className="bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors"
                  >
                    {withCurrent(["Low", "Mid", "High", "Full"], config.register ?? "").map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 min-w-[120px]">
                  Articulation
                  <select
                    value={config.articulation}
                    onChange={event => handleInstrumentConfigChange(config.name, { articulation: event.target.value as InstrumentConfig["articulation"] })}
                    className="bg-black/60 p-2 rounded border border-purple-800/30 focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 transition-colors"
                  >
                    {withCurrent(["Sustain", "Staccato", "Legato", "Accented", "Marcato", "Pizzicato"], config.articulation ?? "").map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const ParamPanel = memo(ParamPanelComponent);
