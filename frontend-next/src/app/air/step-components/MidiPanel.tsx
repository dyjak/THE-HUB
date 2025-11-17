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
import type { InstrumentConfig, MidiParameters } from "../lib/midiTypes";
import { SampleSelector } from "./SampleSelector";

interface MidiPanelProps {
  midi: MidiParameters;
  availableInstruments: string[];
  selectableInstruments: string[];
  fxSubtypes?: string[];
  apiBase: string;
  apiPrefix: string;
  modulePrefix: string;
  onUpdate: (patch: Partial<MidiParameters>) => void;
  onToggleInstrument: (instrument: string) => void;
  onUpdateInstrumentConfig: (name: string, patch: Partial<InstrumentConfig>) => void;
  selectedSamples: Record<string, string | undefined>;
  onSelectSample: (instrument: string, sampleId: string | null) => void;
  compact?: boolean;
  columns?: 1 | 2 | 3 | 4;
  hideFx?: boolean;
}

const MidiPanelComponent = ({
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
}: MidiPanelProps) => {
  const handleStyleChange = useCallback<React.ChangeEventHandler<HTMLSelectElement>>(
    event => {
      const value = event.target.value as MidiParameters["style"];
      onUpdate({ style: value, genre: value });
    },
    [onUpdate],
  );

  const handleNumberChange = useCallback(
    (field: keyof Pick<MidiParameters, "tempo" | "bars" | "length_seconds">, min: number, fallback: number) =>
      (event: React.ChangeEvent<HTMLInputElement>) => {
        const parsed = Number(event.target.value);
        if (Number.isNaN(parsed)) {
          onUpdate({ [field]: fallback } as Partial<MidiParameters>);
          return;
        }
        onUpdate({ [field]: Math.max(min, parsed) } as Partial<MidiParameters>);
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
    <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 space-y-4 col-span-2">
      <h2 className="font-semibold text-emerald-300">MIDI Parameters</h2>
      <div className={`grid ${gridCols} gap-4 ${sizeClass}`}>
        <div>
          <label className="block mb-1">Style</label>
          <select value={midi.style} onChange={handleStyleChange} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {styleOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Mood</label>
          <select value={midi.mood} onChange={event => onUpdate({ mood: event.target.value as MidiParameters["mood"] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {moodOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Key</label>
          <select value={midi.key} onChange={event => onUpdate({ key: event.target.value as MidiParameters["key"] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {keyOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Scale</label>
          <select value={midi.scale} onChange={event => onUpdate({ scale: event.target.value as MidiParameters["scale"] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {scaleOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Meter</label>
          <select value={midi.meter} onChange={event => onUpdate({ meter: event.target.value as MidiParameters["meter"] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
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
          <input type="number" min={1} max={512} value={midi.bars} onChange={handleNumberChange("bars", 1, 1)} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
        </div>
        <div>
          <label className="block mb-1">Length (seconds)</label>
          <input type="number" min={30} max={3600} step={5} value={midi.length_seconds} onChange={handleNumberChange("length_seconds", 30, 30)} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
        </div>
        <div>
          <label className="block mb-1">Dynamic Profile</label>
          <select value={midi.dynamic_profile} onChange={event => onUpdate({ dynamic_profile: event.target.value as MidiParameters["dynamic_profile"] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {dynamicProfileOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Arrangement Density</label>
          <select value={midi.arrangement_density} onChange={event => onUpdate({ arrangement_density: event.target.value as MidiParameters["arrangement_density"] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {arrangementDensityOptions.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Harmonic Color</label>
          <select value={midi.harmonic_color} onChange={event => onUpdate({ harmonic_color: event.target.value as MidiParameters["harmonic_color"] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
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
            <div className="mb-2 p-2 border border-gray-800 rounded bg-black/30">
              <div className="text-xs text-gray-400 mb-1">Drums</div>
              <div className="flex flex-wrap gap-2">
                {present.map(inst => (
                  <button
                    key={inst}
                    onClick={handleInstrumentToggle(inst)}
                    className={`px-3 py-1 rounded-full border text-xs ${midi.instruments.includes(inst) ? "bg-emerald-700 border-emerald-500" : "bg-black/50 border-gray-700 hover:bg-black/60"}`}
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
            <div className="mb-2 p-2 border border-gray-800 rounded bg-black/30">
              <div className="text-xs text-gray-400 mb-1">FX</div>
              <div className="flex flex-wrap gap-2">
                {presentFx.map(inst => (
                  <button
                    key={inst}
                    onClick={handleInstrumentToggle(inst)}
                    className={`px-3 py-1 rounded-full border text-xs ${midi.instruments.includes(inst) ? "bg-emerald-700 border-emerald-500" : "bg-black/50 border-gray-700 hover:bg-black/60"}`}
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
            const baseClasses = active ? "bg-emerald-700 border-emerald-500 text-white" : "bg-black/50 border-gray-700";
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
            <div key={config.name} className="bg-black/40 border border-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex flex-wrap gap-3 items-center">
                <div className="font-semibold text-emerald-200">{config.name}</div>
                <div className="text-[11px] text-gray-500">{config.role} • {config.register}</div>
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
                    className="bg-black/60 p-2 rounded border border-gray-700">
                    {withCurrent(DYNAMIC_RANGE_OPTIONS, config.dynamic_range).map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 min-w-[120px]">
                  Role
                  <select value={config.role}
                    onChange={event => handleInstrumentConfigChange(config.name, { role: event.target.value as InstrumentConfig["role"] })}
                    className="bg-black/60 p-2 rounded border border-gray-700">
                    {withCurrent(["Lead","Accompaniment","Rhythm","Pad","Bass","Percussion","Fx"], config.role ?? "").map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 min-w-[120px]">
                  Register
                  <select
                    value={config.register}
                    onChange={event => handleInstrumentConfigChange(config.name, { register: event.target.value as InstrumentConfig["register"] })}
                    className="bg-black/60 p-2 rounded border border-gray-700"
                  >
                    {withCurrent(["Low","Mid","High","Full"], config.register ?? "").map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 min-w-[120px]">
                  Articulation
                  <select
                    value={config.articulation}
                    onChange={event => handleInstrumentConfigChange(config.name, { articulation: event.target.value as InstrumentConfig["articulation"] })}
                    className="bg-black/60 p-2 rounded border border-gray-700"
                  >
                    {withCurrent(["Sustain","Staccato","Legato","Accented","Marcato","Pizzicato"], config.articulation ?? "").map(option => (
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

export const MidiPanel = memo(MidiPanelComponent);
