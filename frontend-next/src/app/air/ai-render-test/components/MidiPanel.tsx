import { memo, useCallback } from 'react';
import {
  ARRANGEMENT_DENSITY_OPTIONS,
  ARTICULATION_OPTIONS,
  DYNAMIC_PROFILE_OPTIONS,
  DYNAMIC_RANGE_OPTIONS,
  EFFECT_OPTIONS,
  FORM_SECTION_OPTIONS,
  HARMONIC_COLOR_OPTIONS,
  KEY_OPTIONS,
  METER_OPTIONS,
  MOOD_OPTIONS,
  SCALE_OPTIONS,
  STYLE_OPTIONS,
} from '../constants';
import type { InstrumentConfig, MidiParameters } from '../types';
import { SampleSelector } from './SampleSelector';

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
  onAddFormSection: (section: string) => void;
  onRemoveFormSection: (index: number) => void;
  onResetForm: () => void;
  onClearForm: () => void;
  onUpdateInstrumentConfig: (name: string, patch: Partial<InstrumentConfig>) => void;
  onToggleInstrumentEffect: (name: string, effect: string) => void;
  onResetInstrumentEffects: (name: string) => void;
  selectedSamples: Record<string, string | undefined>;
  onSelectSample: (instrument: string, sampleId: string | null) => void;
}

const MidiPanelComponent = ({
  midi,
  availableInstruments,
  selectableInstruments,
  onUpdate,
  onToggleInstrument,
  onAddFormSection,
  onRemoveFormSection,
  onResetForm,
  onClearForm,
  onUpdateInstrumentConfig,
  onToggleInstrumentEffect,
  onResetInstrumentEffects,
  fxSubtypes = [],
  apiBase,
  apiPrefix,
  modulePrefix,
  selectedSamples,
  onSelectSample,
}: MidiPanelProps) => {
  const handleStyleChange = useCallback<React.ChangeEventHandler<HTMLSelectElement>>(
    event => {
      const value = event.target.value as MidiParameters['style'];
      onUpdate({ style: value, genre: value });
    },
    [onUpdate],
  );

  const handleNumberChange = useCallback(
    (field: keyof Pick<MidiParameters, 'tempo' | 'bars' | 'length_seconds'>, min: number, fallback: number) =>
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

  const handleSeedChange = useCallback<React.ChangeEventHandler<HTMLInputElement>>(
    event => {
      const value = event.target.value;
      if (value === '') {
        onUpdate({ seed: null });
        return;
      }
      const parsed = Number(value);
      onUpdate({ seed: Number.isFinite(parsed) ? Math.trunc(parsed) : null });
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

  const handleFormPreset = useCallback(
    (section: string) => () => onAddFormSection(section),
    [onAddFormSection],
  );

  const handleInstrumentConfigChange = useCallback(
    (name: string, patch: Partial<InstrumentConfig>) => onUpdateInstrumentConfig(name, patch),
    [onUpdateInstrumentConfig],
  );

  const handleEffectToggle = useCallback(
    (name: string, effect: string) => () => onToggleInstrumentEffect(name, effect),
    [onToggleInstrumentEffect],
  );

  const handleResetEffects = useCallback(
    (name: string) => () => onResetInstrumentEffects(name),
    [onResetInstrumentEffects],
  );

  return (
    <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 space-y-4 col-span-2">
      <h2 className="font-semibold text-emerald-300">MIDI Parameters</h2>
      <div className="grid sm:grid-cols-2 gap-4 text-sm">
        <div>
          <label className="block mb-1">Style</label>
          <select value={midi.style} onChange={handleStyleChange} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {STYLE_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Mood</label>
          <select value={midi.mood} onChange={event => onUpdate({ mood: event.target.value as MidiParameters['mood'] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {MOOD_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Key</label>
          <select value={midi.key} onChange={event => onUpdate({ key: event.target.value as MidiParameters['key'] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {KEY_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Scale</label>
          <select value={midi.scale} onChange={event => onUpdate({ scale: event.target.value as MidiParameters['scale'] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {SCALE_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Meter</label>
          <select value={midi.meter} onChange={event => onUpdate({ meter: event.target.value as MidiParameters['meter'] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {METER_OPTIONS.map(option => (
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
          <input type="number" min={1} max={512} value={midi.bars} onChange={handleNumberChange('bars', 1, 1)} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
        </div>
        <div>
          <label className="block mb-1">Length (seconds)</label>
          <input type="number" min={30} max={3600} step={5} value={midi.length_seconds} onChange={handleNumberChange('length_seconds', 30, 30)} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
        </div>
        <div>
          <label className="block mb-1">Dynamic Profile</label>
          <select value={midi.dynamic_profile} onChange={event => onUpdate({ dynamic_profile: event.target.value as MidiParameters['dynamic_profile'] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {DYNAMIC_PROFILE_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Arrangement Density</label>
          <select value={midi.arrangement_density} onChange={event => onUpdate({ arrangement_density: event.target.value as MidiParameters['arrangement_density'] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {ARRANGEMENT_DENSITY_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Harmonic Color</label>
          <select value={midi.harmonic_color} onChange={event => onUpdate({ harmonic_color: event.target.value as MidiParameters['harmonic_color'] })} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {HARMONIC_COLOR_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Seed</label>
          <input type="number" value={midi.seed ?? ''} onChange={handleSeedChange} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs text-gray-400 uppercase tracking-widest">Form</div>
          <div className="flex gap-2">
            <button onClick={onResetForm} className="px-2 py-1 text-[11px] border border-gray-700 rounded">Reset</button>
            <button onClick={onClearForm} className="px-2 py-1 text-[11px] border border-gray-700 rounded">Clear</button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {midi.form.map((section, index) => (
            <div key={`${section}-${index}`} className="px-3 py-1 bg-black/40 border border-gray-700 rounded-full text-xs flex items-center gap-2">
              <span>{section}</span>
              <button onClick={() => onRemoveFormSection(index)} className="text-gray-400 hover:text-white">×</button>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {FORM_SECTION_OPTIONS.map(section => (
            <button key={section} onClick={handleFormPreset(section)} className="px-2 py-1 text-[11px] border border-gray-700 rounded bg-black/50 hover:bg-black/60">
              {section}
            </button>
          ))}
        </div>
        <div className="text-[10px] text-gray-500">Dodawaj sekcje klikając preset. Reset przywraca domyślny układ, Clear usuwa wszystkie.</div>
      </div>

      <div>
        <label className="block mb-2">Instruments (only available)</label>
        {/* Drums quick panel */}
        {(() => {
          const drums = ['kick','snare','hihat','clap','808'];
          const present = drums.filter(d => availableInstruments.includes(d));
          if (present.length === 0) return null;
          const hasVirtual = true; // page adds 'drums' when any present
          return (
            <div className="mb-2 p-2 border border-gray-800 rounded bg-black/30">
              <div className="text-xs text-gray-400 mb-1">Drums</div>
              <div className="flex flex-wrap gap-2">
                {hasVirtual && (
                  <button
                    onClick={handleInstrumentToggle('drums')}
                    className={`px-3 py-1 rounded-full border text-xs ${midi.instruments.includes('drums') ? 'bg-emerald-700 border-emerald-500' : 'bg-black/50 border-gray-700 hover:bg-black/60'}`}
                  >drums</button>
                )}
                {present.map(inst => (
                  <button
                    key={inst}
                    onClick={handleInstrumentToggle(inst)}
                    className={`px-3 py-1 rounded-full border text-xs ${midi.instruments.includes(inst) ? 'bg-emerald-700 border-emerald-500' : 'bg-black/50 border-gray-700 hover:bg-black/60'}`}
                  >{inst}</button>
                ))}
              </div>
            </div>
          );
        })()}
        {/* FX panel */}
        {(() => {
          const hasFx = availableInstruments.includes('fx');
          if (!hasFx) return null;
          const active = midi.instruments.includes('fx');
          const subs = Array.isArray(fxSubtypes) ? fxSubtypes : [];
          return (
            <div className="mb-2 p-2 border border-gray-800 rounded bg-black/30">
              <div className="text-xs text-gray-400 mb-1">FX</div>
              <div className="flex flex-wrap gap-2 mb-2">
                <button
                  onClick={handleInstrumentToggle('fx')}
                  className={`px-3 py-1 rounded-full border text-xs ${active ? 'bg-emerald-700 border-emerald-500' : 'bg-black/50 border-gray-700 hover:bg-black/60'}`}
                >fx</button>
              </div>
              {subs.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {subs.map(s => (
                    <span key={s} className="px-2 py-0.5 rounded-full border border-gray-800 text-[10px] bg-black/40 text-gray-300">{s}</span>
                  ))}
                </div>
              )}
            </div>
          );
        })()}
        <div className="mb-1 text-xs text-gray-400">Instruments</div>
        <div className="flex flex-wrap gap-2">
          {selectableInstruments.map(instrument => {
            const active = midi.instruments.includes(instrument);
            const disabled = isInstrumentDisabled(instrument) && !active;
            const baseClasses = active ? 'bg-emerald-700 border-emerald-500 text-white' : 'bg-black/50 border-gray-700';
            const disabledClasses = disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer hover:bg-black/60';
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
          {midi.instrument_configs.filter(cfg => cfg.name !== 'drums').map(config => (
            <div key={config.name} className="bg-black/40 border border-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex flex-wrap gap-3 items-center">
                <div className="font-semibold text-emerald-200">{config.name}</div>
                <div className="text-[11px] text-gray-500">{config.role} • {config.register} • pan {config.pan.toFixed(2)}</div>
                <button onClick={handleResetEffects(config.name)} className="ml-auto px-2 py-1 text-[11px] border border-gray-700 rounded">Reset FX</button>
              </div>
              {/* Sample selection with preview */}
              <SampleSelector
                apiBase={apiBase}
                apiPrefix={apiPrefix}
                modulePrefix={modulePrefix}
                instrument={config.name}
                selectedId={selectedSamples[config.name] || null}
                onChange={onSelectSample}
              />
              <div className="grid sm:grid-cols-3 gap-3 text-xs">
                <label className="flex flex-col gap-1">
                  Volume
                  <input type="number" min={0} max={1} step={0.05} value={config.volume}
                    onChange={event => handleInstrumentConfigChange(config.name, { volume: Number(event.target.value) })}
                    className="bg-black/60 p-2 rounded border border-gray-700" />
                </label>
                <label className="flex flex-col gap-1">
                  Pan
                  <input type="number" min={-1} max={1} step={0.05} value={config.pan}
                    onChange={event => handleInstrumentConfigChange(config.name, { pan: Number(event.target.value) })}
                    className="bg-black/60 p-2 rounded border border-gray-700" />
                </label>
                <label className="flex flex-col gap-1">
                  Dynamic range
                  <select value={config.dynamic_range}
                    onChange={event => handleInstrumentConfigChange(config.name, { dynamic_range: event.target.value as InstrumentConfig['dynamic_range'] })}
                    className="bg-black/60 p-2 rounded border border-gray-700">
                    {DYNAMIC_RANGE_OPTIONS.map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  Role
                  <select value={config.role}
                    onChange={event => handleInstrumentConfigChange(config.name, { role: event.target.value as InstrumentConfig['role'] })}
                    className="bg-black/60 p-2 rounded border border-gray-700">
                    {['lead','accompaniment','rhythm','pad','bass','percussion','fx'].map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  Register
                  <select value={config.register}
                    onChange={event => handleInstrumentConfigChange(config.name, { register: event.target.value as InstrumentConfig['register'] })}
                    className="bg-black/60 p-2 rounded border border-gray-700">
                    {['low','mid','high','full'].map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1">
                  Articulation
                  <select value={config.articulation}
                    onChange={event => handleInstrumentConfigChange(config.name, { articulation: event.target.value as InstrumentConfig['articulation'] })}
                    className="bg-black/60 p-2 rounded border border-gray-700">
                    {ARTICULATION_OPTIONS.map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div>
                <div className="text-[11px] text-gray-500 mb-1">Effects</div>
                <div className="flex flex-wrap gap-2">
                  {EFFECT_OPTIONS.map(effect => {
                    const active = config.effects.includes(effect);
                    return (
                      <button
                        key={effect}
                        onClick={handleEffectToggle(config.name, effect)}
                        className={`px-3 py-1 rounded-full border text-[11px] ${active ? 'bg-purple-600 border-purple-500 text-white' : 'bg-black/60 border-gray-700 hover:bg-black/70'}`}
                      >
                        {effect}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const MidiPanel = memo(MidiPanelComponent);
