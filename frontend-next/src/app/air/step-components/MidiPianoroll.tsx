"use client";

import React, { useMemo, useState, forwardRef } from "react";

export type MidiEvent = {
  bar: number;
  step: number;
  note: number;
  vel?: number;
  len?: number;
  instrument?: string;
};

export type MidiLayer = {
  bar: number;
  events: MidiEvent[];
  mergedLane?: { instrument: string; events: MidiEvent[] } | null;
};

export type MidiData = {
  pattern?: MidiLayer[];
  layers?: Record<string, MidiLayer[]>;
  meta?: {
    tempo?: number;
    bars?: number;
  } & Record<string, any>;
};

type Props = {
  midi: MidiData | null | undefined;
  stepsPerBar?: number;
};

/**
 * Bardzo lekki pianoroll na froncie, bez canvasów.
 * Zakładamy 8 kroków na takt (tak jak w backendowym promptcie).
 */
export const MidiPianoroll = forwardRef<HTMLDivElement, Props>(({ midi, stepsPerBar = 8 }, ref) => {
  const [colors] = useState<Record<string, string>>(() => ({}));
  const [zoomX, setZoomX] = useState(1); // poziomy zoom
  const [zoomY, setZoomY] = useState(1); // pionowy zoom

  const { lanes, mergedLane, minNote, maxNote, totalSteps, minAbsStep, colorMap, laneNoteRanges } = useMemo(() => {
    const lanes: { instrument: string; events: MidiEvent[] }[] = [];
    const mergedEvents: MidiEvent[] = [];
    const colorMap: Record<string, string> = {};
    const laneNoteRanges: Record<string, { min: number; max: number }> = {};

    if (!midi) return { lanes: [] as { instrument: string; events: MidiEvent[] }[], mergedLane: null, minNote: 60, maxNote: 72, totalSteps: 0, minAbsStep: 0, colorMap, laneNoteRanges };

    const pushLayer = (instrument: string, layers?: MidiLayer[]) => {
      if (!Array.isArray(layers)) return;
      for (const layer of layers) {
        const bar = typeof layer.bar === "number" ? layer.bar : 0;
        const evs = Array.isArray(layer.events) ? layer.events : [];
        for (const ev of evs) {
          if (typeof ev.note !== "number") continue;
          const step = typeof ev.step === "number" ? ev.step : 0;
          const vel = typeof ev.vel === "number" ? ev.vel : 80;
          const len = typeof ev.len === "number" ? ev.len : 1;
          const full: MidiEvent = { bar, step, note: ev.note, vel, len, instrument: instrument || undefined };
          let lane = lanes.find(l => l.instrument === instrument);
          if (!lane) {
            lane = { instrument, events: [] };
            lanes.push(lane);
            if (!colorMap[instrument]) {
              // bardziej zróżnicowane, ale nadal przyjemne kolory
              const hue = Math.floor(Math.random() * 360); // pełne koło barw
              const sat = 55 + Math.floor(Math.random() * 30);  // 55-85%
              const light = 45 + Math.floor(Math.random() * 10); // 45-55%
              colorMap[instrument] = `hsl(${hue} ${sat}% ${light}%)`;
            }
          }
          lane.events.push(full);

          const key = instrument || "__anon__";
          const existing = laneNoteRanges[key];
          if (!existing) {
            laneNoteRanges[key] = { min: full.note, max: full.note };
          } else {
            if (full.note < existing.min) existing.min = full.note;
            if (full.note > existing.max) existing.max = full.note;
          }
          mergedEvents.push(full);
        }
      }
    };

    // layers per instrument z midi.layers (bez specjalnego traktowania pattern)
    if (midi.layers && typeof midi.layers === "object") {
      for (const key of Object.keys(midi.layers)) {
        pushLayer(key, midi.layers[key]);
      }
    }

    const flatEvents = (mergedEvents.length ? mergedEvents : lanes.flatMap(l => l.events));

    if (!flatEvents.length) {
      return { lanes: [], mergedLane: null, minNote: 60, maxNote: 72, totalSteps: 0, minAbsStep: 0, colorMap, laneNoteRanges };
    }

    let minN = Infinity;
    let maxN = -Infinity;
    let maxAbsStep = 0;
    let minAbsStep = Infinity;

    for (const ev of flatEvents) {
      minN = Math.min(minN, ev.note);
      maxN = Math.max(maxN, ev.note);
      const start = ev.bar * stepsPerBar + ev.step;
      const end = start + (ev.len || 1);
      minAbsStep = Math.min(minAbsStep, start);
      maxAbsStep = Math.max(maxAbsStep, end);
    }

    if (!Number.isFinite(minN) || !Number.isFinite(maxN)) {
      minN = 60;
      maxN = 72;
    }

    return {
      lanes,
      mergedLane: mergedEvents.length ? { instrument: "Merged", events: mergedEvents } : null,
      minNote: minN,
      maxNote: maxN,
      totalSteps: Math.max(0, maxAbsStep - minAbsStep),
      minAbsStep: Number.isFinite(minAbsStep) ? minAbsStep : 0,
      colorMap,
      laneNoteRanges,
    };
  }, [midi, stepsPerBar]);

  if (!midi) {
    return (
      <div className="text-[11px] text-gray-500 border border-gray-800 rounded-md p-2">
        Brak danych MIDI do wizualizacji.
      </div>
    );
  }

  if (!lanes.length) {
    return (
      <div className="text-[11px] text-gray-500 border border-gray-800 rounded-md p-2">
        Model nie zwrócił żadnych nut (pattern jest pusty).
      </div>
    );
  }

  const noteRange = Math.max(1, maxNote - minNote + 1);
  // Utrzymujemy przyjemną szerokość kroku, ale dokładne "rozciągnięcie"
  // do pełnej szerokości zostawiamy CSS-owi (flex + w-full), żeby nie
  // ściskać patternów na siłę – przy krótkich patternach całość i tak
  // wygląda szeroko, przy długich pojawia się scroll.
  const baseCellWidth = 36;
  const baseCellHeight = 12;
  const cellWidth = baseCellWidth * zoomX; // poziome przybliżanie/oddalanie
  const cellHeight = baseCellHeight * zoomY; // pionowy zoom lane'ów
  const width = Math.max(1, totalSteps || 1) * cellWidth;
  const height = noteRange * cellHeight;

  const midiNoteName = (note: number): string => {
    const names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
    if (!Number.isFinite(note)) return "";
    const n = Math.round(note);
    const name = names[((n % 12) + 12) % 12];
    const octave = Math.floor(n / 12) - 1;
    return `${name}${octave}`;
  };

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden bg-black/80 w-full flex flex-col">
      <div className="text-[11px] text-gray-400 px-3 py-1 border-b border-gray-800 flex items-center justify-between gap-4">
        <span>Pianoroll (frontend)</span>
        <div className="flex-1 flex flex-wrap gap-2 items-center">
          {mergedLane && (
            <div className="flex items-center gap-1 text-[10px] text-gray-200">
              <span className="inline-block w-3 h-3 rounded-sm bg-gray-200" />
              <span className="truncate max-w-[120px]" title="Merged pattern">
                Merged
              </span>
            </div>
          )}
          {lanes.map((lane, idx) => (
            <div key={lane.instrument || idx} className="flex items-center gap-1 text-[10px] text-gray-300">
              <span
                className="inline-block w-3 h-3 rounded-sm"
                style={{ backgroundColor: colorMap[lane.instrument] || "#34d399" }}
              />
              <span className="truncate max-w-[120px]" title={lane.instrument || "pattern"}>
                {lane.instrument || "pattern"}
              </span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {typeof midi?.meta?.tempo === "number" && (
            <span className="text-[10px] text-gray-500 whitespace-nowrap">tempo: {midi.meta.tempo} BPM</span>
          )}
          <div className="flex items-center gap-2 text-[10px] text-gray-500">
            <span className="hidden sm:inline">H</span>
            <input
              type="range"
              min={0.5}
              max={5}
              step={0.1}
              value={zoomX}
              onChange={e => setZoomX(parseFloat(e.target.value) || 1)}
              className="w-16 accent-emerald-400 cursor-pointer"
            />
            <span className="w-8 text-right">{(zoomX * 100).toFixed(0)}%</span>
            <span className="hidden sm:inline ml-2">V</span>
            <input
              type="range"
              min={0.5}
              max={5}
              step={0.1}
              value={zoomY}
              onChange={e => setZoomY(parseFloat(e.target.value) || 1)}
              className="w-16 accent-emerald-400 cursor-pointer"
            />
            <span className="w-8 text-right">{(zoomY * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>
      <div ref={ref} className="relative w-full flex-1 bg-black overflow-x-auto scroll-container-green overflow-y-hidden">
        <div className="relative" style={{ minWidth: "100%" }}>
            {mergedLane && (
            <div className="border-t border-gray-800/60 first:border-t-0">
              <div className="text-[10px] text-gray-300 px-3 py-1 flex items-center gap-2 bg-black">
                <span className="inline-block w-3 h-3 rounded-sm bg-gray-200" />
                <span className="truncate" title="Merged pattern">
                  Merged pattern
                </span>
              </div>
              <div
                className="relative"
                style={{
                  width,
                  height,
                  backgroundImage:
                    "repeating-linear-gradient(to right," +
                    "rgba(55,65,81,0.4) 0 1px, transparent 1px 36px," +
                    "rgba(148,163,184,0.45) 36px 37px, transparent 37px 288px)," +
                    "repeating-linear-gradient(to bottom," +
                    "rgba(15,23,42,0.9) 0 12px, rgba(17,24,39,0.9) 12px 24px)",
                  backgroundSize: `${cellWidth}px ${cellHeight}px`,
                }}
              >
                {mergedLane.events.map((ev, idx) => {
                  const abs = ev.bar * stepsPerBar + ev.step;
                  const x = (abs - (minAbsStep ?? 0)) * cellWidth;
                  const y = (maxNote - ev.note) * cellHeight;
                  const w = Math.max(cellWidth * (ev.len || 1), 4);
                  const h = cellHeight - 2;
                  const opacity = Math.min(1, Math.max(0.25, (ev.vel || 80) / 127));
                  const noteLabel = midiNoteName(ev.note);
                  const baseColor = ev.instrument ? colorMap[ev.instrument] || "#34d399" : "#e5e7eb";

                  return (
                    <div
                      key={`merged-${idx}`}
                      title={`bar ${ev.bar}, step ${ev.step}, note ${ev.note} (${noteLabel}), vel ${ev.vel ?? 80}`}
                      className="absolute rounded-sm flex items-center justify-center text-[9px] font-medium text-black/80"
                      style={{
                        left: x,
                        top: y,
                        width: w,
                        height: h,
                        background: baseColor,
                        opacity,
                        boxShadow: "0 0 4px rgba(156,163,175,0.8)",
                      }}
                    >
                      {noteLabel && <span className="px-0.5 truncate max-w-full">{noteLabel}</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {lanes.map((lane, laneIdx) => {
            const key = lane.instrument || "__anon__";
            const range = laneNoteRanges[key] || { min: minNote, max: maxNote };
            const laneMin = range.min;
            const laneMax = range.max;
            const laneNoteCount = Math.max(1, laneMax - laneMin + 1);
            const laneHeight = laneNoteCount * cellHeight;

            return (
              <div key={lane.instrument || laneIdx} className="border-t border-gray-800/60 first:border-t-0">
                <div className="text-[10px] text-gray-400 px-3 py-1 flex items-center gap-2 bg-black/70">
                  <span
                    className="inline-block w-3 h-3 rounded-sm"
                    style={{ backgroundColor: colorMap[lane.instrument] || "#34d399" }}
                  />
                  <span className="truncate" title={lane.instrument || "pattern"}>
                    {lane.instrument || "pattern"}
                  </span>
                </div>
                <div
                  className="relative"
                  style={{
                    width,
                    height: laneHeight,
                    backgroundImage:
                      // pionowe linie: co krok cienka, co ósmy krok jaśniejsza
                      "repeating-linear-gradient(to right," +
                      "rgba(55,65,81,0.4) 0 1px, transparent 1px 36px," +
                      "rgba(148,163,184,0.45) 36px 37px, transparent 37px 288px)," +
                      // poziome pasy: naprzemienne delikatnie ciemniejsze/jasniejsze
                      "repeating-linear-gradient(to bottom," +
                      "rgba(15,23,42,0.9) 0 12px, rgba(17,24,39,0.9) 12px 24px)",
                    backgroundSize: `${cellWidth}px ${cellHeight}px`,
                  }}
                >
                  {lane.events.map((ev, idx) => {
                    const abs = ev.bar * stepsPerBar + ev.step;
                    const x = (abs - (minAbsStep ?? 0)) * cellWidth;
                    const y = (laneMax - ev.note) * cellHeight; // wyżej = wyższa nuta w obrębie lane'a
                    const w = Math.max(cellWidth * (ev.len || 1), 4);
                    const h = cellHeight - 2;
                    const opacity = Math.min(1, Math.max(0.25, (ev.vel || 80) / 127));
                    const noteLabel = midiNoteName(ev.note);
                    const color = colorMap[lane.instrument] || "#34d399";

                    return (
                      <div
                        key={`${lane.instrument || "lane"}-${idx}`}
                        title={`bar ${ev.bar}, step ${ev.step}, note ${ev.note} (${noteLabel}), vel ${ev.vel ?? 80}`}
                        className="absolute rounded-sm flex items-center justify-center text-[9px] font-medium text-black/80"
                        style={{
                          left: x,
                          top: y,
                          width: w,
                          height: h,
                          background: color,
                          opacity,
                          boxShadow: "0 0 4px rgba(16,185,129,0.7)",
                        }}
                      >
                        {noteLabel && <span className="px-0.5 truncate max-w-full">{noteLabel}</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
});

export default MidiPianoroll;
