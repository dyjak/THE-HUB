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

    const canon = (name: unknown) => String(name || "").trim().toLowerCase().replace(/\s+/g, " ");

    const notesForPercussionInstrument = (name: string): number[] | null => {
      const n = canon(name);
      const direct: Record<string, number[]> = {
        "kick": [36],
        "snare": [38],
        "clap": [39],
        "rim": [37],
        "rimshot": [37],
        "side stick": [37],
        "hat": [42, 46],
        "hihat": [42, 46],
        "hi hat": [42, 46],
        "closed hat": [42],
        "open hat": [46],
        "crash": [49],
        "ride": [51],
        "splash": [55],
        "shake": [82],
        "shaker": [82],
        "808": [35],
        "low tom": [45],
        "mid tom": [47],
        "high tom": [50],
        "tom": [45, 47, 50],
      };
      if (direct[n]) return direct[n];
      if (n.includes("hat")) return [42, 46];
      if (n.includes("clap")) return [39];
      if (n.includes("rim") || n.includes("side")) return [37];
      if (n.includes("crash")) return [49];
      if (n.includes("ride")) return [51];
      if (n.includes("splash")) return [55];
      if (n.includes("shake") || n.includes("shaker")) return [82];
      if (n.includes("tom")) return [45, 47, 50];
      return null;
    };

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
              const sat = 60 + Math.floor(Math.random() * 20);  // 60-80%
              const light = 50 + Math.floor(Math.random() * 10); // 50-60%
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

    // pattern (perkusja) -> rozbijamy na lane per instrument na podstawie nut GM.
    // Bez placeholderów: jeśli instrument nie ma eventów, nie pojawi się jako lane.
    if (Array.isArray(midi.pattern) && midi.pattern.length > 0) {
      const meta = (midi.meta && typeof midi.meta === "object") ? midi.meta : {};
      const configsRaw = Array.isArray((meta as any).instrument_configs) ? (meta as any).instrument_configs as any[] : [];

      const percSet = new Set<string>();
      for (const cfg of configsRaw) {
        if (!cfg || typeof cfg !== "object") continue;
        const role = canon((cfg as any).role);
        const name = String((cfg as any).name || "").trim();
        if (role === "percussion" && name) percSet.add(name);
      }

      // If instrument_configs are missing/empty, fall back to meta.instruments.
      const instrumentsRaw = Array.isArray((meta as any).instruments) ? (meta as any).instruments as any[] : [];
      for (const inst of instrumentsRaw) {
        const name = String(inst || "").trim();
        if (!name) continue;
        if (notesForPercussionInstrument(name)) percSet.add(name);
      }

      // Last resort: standard GM drum set names.
      if (percSet.size === 0) {
        ["Kick", "Snare", "Hat", "Crash", "Ride", "Tom"].forEach(n => percSet.add(n));
      }

      const percNames = Array.from(percSet);

      // Build note->instrument mapping with priority for more specific instruments.
      const percMap = percNames
        .map(name => {
          const notes = notesForPercussionInstrument(name);
          return { name, notes: notes || [] };
        })
        .filter(x => x.notes.length > 0)
        .sort((a, b) => a.notes.length - b.notes.length); // 1-note instruments first

      const byInst: Record<string, MidiLayer[]> = {};
      const fallbackName = "Drums";

      for (const barObj of midi.pattern) {
        const bar = typeof (barObj as any)?.bar === "number" ? (barObj as any).bar : 0;
        const evs = Array.isArray((barObj as any)?.events) ? (barObj as any).events as any[] : [];
        for (const ev of evs) {
          const note = typeof ev?.note === "number" ? ev.note : null;
          if (note === null) continue;
          const step = typeof ev?.step === "number" ? ev.step : 0;
          const vel = typeof ev?.vel === "number" ? ev.vel : 80;
          const len = typeof ev?.len === "number" ? ev.len : 1;

          let instName: string | null = null;
          for (const cand of percMap) {
            if (cand.notes.includes(note)) {
              instName = cand.name;
              break;
            }
          }
          const target = instName || fallbackName;
          if (!byInst[target]) byInst[target] = [];
          let layer = byInst[target].find(l => l.bar === bar);
          if (!layer) {
            layer = { bar, events: [] };
            byInst[target].push(layer);
          }
          layer.events.push({ bar, step, note, vel, len, instrument: target });
        }
      }

      for (const inst of Object.keys(byInst)) {
        // sort bars for stability
        byInst[inst].sort((a, b) => (a.bar || 0) - (b.bar || 0));
        pushLayer(inst, byInst[inst]);
      }
    }

    // Ensure we always expose lanes for every requested instrument from meta,
    // even if the model produced no events for some of them.
    try {
      const meta = (midi.meta && typeof midi.meta === "object") ? midi.meta : {};
      const requested = Array.isArray((meta as any).instruments) ? ((meta as any).instruments as any[]) : [];
      for (const instRaw of requested) {
        const inst = String(instRaw || "").trim();
        if (!inst) continue;
        if (lanes.some(l => l.instrument === inst)) continue;
        lanes.push({ instrument: inst, events: [] });
        if (!colorMap[inst]) {
          const hue = Math.floor(Math.random() * 360);
          const sat = 60 + Math.floor(Math.random() * 20);
          const light = 50 + Math.floor(Math.random() * 10);
          colorMap[inst] = `hsl(${hue} ${sat}% ${light}%)`;
        }
      }
    } catch {
      // best-effort only
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
      <div className="text-[11px] text-gray-500 border border-gray-800/50 rounded-xl p-4 bg-black/30 text-center">
        Brak danych MIDI do wizualizacji.
      </div>
    );
  }

  if (!lanes.length) {
    return (
      <div className="flex items-start gap-2 text-xs bg-red-900/40 border border-red-600/70 text-amber-100 px-3 py-2 rounded-lg">
        <span className="mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-black text-[10px] font-bold">!</span>
        <div>
          <div className="font-semibold uppercase tracking-widest text-[10px] text-amber-200">Pusty pattern MIDI</div>
          <div className="mt-0.5 text-[11px]">
            Model nie zwrócił żadnych nut (pattern jest pusty).
            <br />
            To się zdarza, gdy model nie trzyma się narzuconejstruktury JSON.
            <br />
            Spróbuj ponownie.
          </div>
        </div>
      </div>
    );
  }

  const noteRange = Math.max(1, maxNote - minNote + 1);
  const baseCellWidth = 36;
  const baseCellHeight = 14; // slightly taller for better visibility
  const cellWidth = baseCellWidth * zoomX;
  const cellHeight = baseCellHeight * zoomY;
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
    <div className="border bg-black/20 backdrop-blur-l border-orange-800/40 p-6 rounded-xl overflow-hidden w-full flex flex-col shadow-lg shadow-black/50">
      <div className="text-[11px] text-gray-400 pb-2 mb-2 border-b border-orange-900/30 flex items-center justify-between gap-4">
        <span className="font-semibold text-orange-500/80 uppercase tracking-wider">Pianoroll</span>
        <div className="flex-1 flex flex-wrap gap-2 items-center justify-center">
          {mergedLane && (
            <div className="flex items-center gap-1.5 text-[10px] text-gray-300 bg-white/5 px-2 py-0.5 rounded-full border border-white/10">
              <span className="inline-block w-2 h-2 rounded-full bg-gray-200 shadow-[0_0_5px_rgba(255,255,255,0.5)]" />
              <span className="truncate max-w-[100px]" title="Merged pattern">
                Merged
              </span>
            </div>
          )}
          {lanes.map((lane, idx) => (
            <div key={lane.instrument || idx} className="flex items-center gap-1.5 text-[10px] text-gray-300 bg-white/5 px-2 py-0.5 rounded-full border border-white/10">
              <span
                className="inline-block w-2 h-2 rounded-full shadow-[0_0_5px_currentColor]"
                style={{ backgroundColor: colorMap[lane.instrument] || "#f97316", color: colorMap[lane.instrument] || "#f97316" }}
              />
              <span className="truncate max-w-[100px]" title={lane.instrument || "pattern"}>
                {lane.instrument || "pattern"}
              </span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-4">
          {typeof midi?.meta?.tempo === "number" && (
            <span className="text-[10px] text-orange-400/70 font-mono bg-orange-900/20 px-2 py-0.5 rounded border border-orange-900/30">{midi.meta.tempo} BPM</span>
          )}
          <div className="flex items-center gap-2 text-[10px] text-gray-500">
            <span className="hidden sm:inline font-bold text-gray-600">H</span>
            <input
              type="range"
              min={0.5}
              max={3}
              step={0.1}
              value={zoomX}
              onChange={e => setZoomX(parseFloat(e.target.value) || 1)}
              className="w-16 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
            />

            <span className="hidden sm:inline font-bold text-gray-600 ml-2">V</span>
            <input
              type="range"
              min={0.5}
              max={3}
              step={0.1}
              value={zoomY}
              onChange={e => setZoomY(parseFloat(e.target.value) || 1)}
              className="w-16 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
            />
          </div>
        </div>
      </div>
      <div ref={ref} className="relative w-full flex-1 bg-[#0a0a0a] overflow-x-auto scroll-container-orange overflow-y-hidden rounded-lg border border-orange-900/20">
        <div className="relative" style={{ minWidth: "100%" }}>
          {mergedLane && (
            <div className="border-t border-orange-900/20 first:border-t-0">
              <div className="text-[10px] text-gray-400 px-3 py-1 flex items-center gap-2 bg-black/60 backdrop-blur sticky left-0 z-10 border-b border-white/5 ">
                <span className="inline-block w-2 h-2 rounded-full bg-gray-200" />
                <span className="truncate font-medium" title="Merged pattern">
                  Merged pattern
                </span>
              </div>
              <div
                className="relative "
                style={{
                  width,
                  height,
                  backgroundImage:
                    "repeating-linear-gradient(to right," +
                    "rgba(249, 115, 22, 0.03) 0 1px, transparent 1px 36px," +
                    "rgba(249, 115, 22, 0.07) 36px 37px, transparent 37px 288px)," +
                    "repeating-linear-gradient(to bottom," +
                    "rgba(255,255,255,0.02) 0 1px, transparent 1px 12px)", // subtler grid
                  backgroundSize: `${cellWidth}px ${cellHeight}px`,
                }}
              >
                {mergedLane.events.map((ev, idx) => {
                  const abs = ev.bar * stepsPerBar + ev.step;
                  const x = (abs - (minAbsStep ?? 0)) * cellWidth;
                  const y = (maxNote - ev.note) * cellHeight;
                  const w = Math.max(cellWidth * (ev.len || 1) - 1, 3); // -1 for gap
                  const h = cellHeight - 2;
                  const opacity = Math.min(1, Math.max(0.4, (ev.vel || 80) / 127));
                  const noteLabel = midiNoteName(ev.note);
                  const baseColor = ev.instrument ? colorMap[ev.instrument] || "#f97316" : "#e5e7eb";

                  return (
                    <div
                      key={`merged-${idx}`}
                      title={`bar ${ev.bar}, step ${ev.step}, note ${ev.note} (${noteLabel}), vel ${ev.vel ?? 80}`}
                      className="absolute rounded-[2px] flex items-center justify-center text-[8px] font-bold text-black/70 shadow-sm transition-opacity hover:opacity-100 hover:z-20"
                      style={{
                        left: x,
                        top: y + 1,
                        width: w,
                        height: h,
                        background: baseColor,
                        opacity,
                        boxShadow: `0 0 8px ${baseColor}40`,
                      }}
                    >
                      {noteLabel && zoomX > 0.8 && <span className="px-0.5 truncate max-w-full">{noteLabel}</span>}
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
              <div key={lane.instrument || laneIdx} className="border-t border-orange-900/20 first:border-t-0">
                <div className="text-[10px] text-gray-400 px-3 py-1 flex items-center gap-2 bg-black/60 backdrop-blur sticky left-0 z-10 border-b border-white/5">
                  <span
                    className="inline-block w-2 h-2 rounded-full shadow-[0_0_5px_currentColor]"
                    style={{ backgroundColor: colorMap[lane.instrument] || "#f97316", color: colorMap[lane.instrument] || "#f97316" }}
                  />
                  <span className="truncate font-medium" title={lane.instrument || "pattern"}>
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
                      "rgba(249, 115, 22, 0.03) 0 1px, transparent 1px 36px," +
                      "rgba(249, 115, 22, 0.07) 36px 37px, transparent 37px 288px)," +
                      // poziome pasy
                      "repeating-linear-gradient(to bottom," +
                      "rgba(255,255,255,0.02) 0 1px, transparent 1px 12px)",
                    backgroundSize: `${cellWidth}px ${cellHeight}px`,
                  }}
                >
                  {lane.events.map((ev, idx) => {
                    const abs = ev.bar * stepsPerBar + ev.step;
                    const x = (abs - (minAbsStep ?? 0)) * cellWidth;
                    const y = (laneMax - ev.note) * cellHeight; // wyżej = wyższa nuta w obrębie lane'a
                    const w = Math.max(cellWidth * (ev.len || 1) - 1, 3);
                    const h = cellHeight - 2;
                    const opacity = Math.min(1, Math.max(0.4, (ev.vel || 80) / 127));
                    const noteLabel = midiNoteName(ev.note);
                    const color = colorMap[lane.instrument] || "#f97316";

                    return (
                      <div
                        key={`${lane.instrument || "lane"}-${idx}`}
                        title={`bar ${ev.bar}, step ${ev.step}, note ${ev.note} (${noteLabel}), vel ${ev.vel ?? 80}`}
                        className="absolute rounded-[2px] flex items-center justify-center text-[8px] font-bold text-black/70 shadow-sm transition-opacity hover:opacity-100 hover:z-20"
                        style={{
                          left: x,
                          top: y + 1,
                          width: w,
                          height: h,
                          background: color,
                          opacity,
                          boxShadow: `0 0 8px ${color}40`,
                        }}
                      >
                        {noteLabel && zoomX > 0.8 && <span className="px-0.5 truncate max-w-full">{noteLabel}</span>}
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
