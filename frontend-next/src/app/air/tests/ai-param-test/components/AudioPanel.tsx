import { memo, useCallback } from 'react';
import type { AudioRenderParameters } from '../types';

interface AudioPanelProps {
  audio: AudioRenderParameters;
  onUpdate: (patch: Partial<AudioRenderParameters>) => void;
}

const clampNumber = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const AudioPanelComponent = ({ audio, onUpdate }: AudioPanelProps) => {
  const handleSampleRateChange = useCallback<React.ChangeEventHandler<HTMLSelectElement>>(
    event => {
      const parsed = Number(event.target.value);
      if (!Number.isFinite(parsed)) return;
      onUpdate({ sample_rate: parsed });
    },
    [onUpdate],
  );

  const handleSecondsChange = useCallback<React.ChangeEventHandler<HTMLInputElement>>(
    event => {
      const parsed = Number(event.target.value);
      if (!Number.isFinite(parsed)) {
        onUpdate({ seconds: 60 });
        return;
      }
      onUpdate({ seconds: clampNumber(parsed, 0.5, 600) });
    },
    [onUpdate],
  );

  const handleMasterGainChange = useCallback<React.ChangeEventHandler<HTMLInputElement>>(
    event => {
      const parsed = Number(event.target.value);
      if (!Number.isFinite(parsed)) {
        onUpdate({ master_gain_db: -3 });
        return;
      }
      onUpdate({ master_gain_db: clampNumber(parsed, -24, 6) });
    },
    [onUpdate],
  );

  return (
    <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 space-y-4">
      <h2 className="font-semibold text-blue-300">Audio Parameters</h2>
      <div className="grid sm:grid-cols-2 gap-4 text-sm">
        <div>
          <label className="block mb-1">Sample Rate</label>
          <select value={audio.sample_rate} onChange={handleSampleRateChange} className="w-full bg-black/60 p-2 rounded border border-gray-700">
            {[44100, 48000, 96000].map(rate => (
              <option key={rate} value={rate}>{rate}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1">Length (seconds)</label>
          <input type="number" step={0.5} min={0.5} max={600} value={audio.seconds} onChange={handleSecondsChange} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
        </div>
        <div>
          <label className="block mb-1">Master Gain (dB)</label>
          <input type="number" step={0.5} min={-24} max={6} value={audio.master_gain_db} onChange={handleMasterGainChange} className="w-full bg-black/60 p-2 rounded border border-gray-700" />
        </div>
      </div>
      <div className="text-[10px] text-gray-500">
        Ustal parametry renderowania audio. Master gain wpływa na poziom końcowego miksu.
      </div>
    </div>
  );
};

export const AudioPanel = memo(AudioPanelComponent);
