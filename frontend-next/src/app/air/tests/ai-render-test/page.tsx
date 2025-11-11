"use client";
import { useState, useEffect, useCallback } from 'react';
import { ChatPlanner } from './components/ChatPlanner';
import { MidiPanel } from './components/MidiPanel';
import { AudioPanel } from './components/AudioPanel';
import { ChatMidiComposer } from './components/ChatMidiComposer';
import type {
  AudioRenderParameters,
  AvailableInstruments,
  ChatProviderInfo,
  DebugEvent,
  DebugRun,
  InstrumentConfig,
  MidiParameters,
  ParamifyNormalizedPlan,
  ParamifyResultView,
} from './types';
// form/effects constants removed from model scope; no longer importing DEFAULT_FORM or effect/form options
import {
  DEFAULT_AUDIO,
  DEFAULT_MIDI,
  clamp,
  cloneAudio,
  cloneMidi,
  createDefaultInstrumentConfig,
  ensureInstrumentConfigs,
  normalizeAudio,
  normalizeMidi,
  uniqueStrings,
} from './utils';
const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_PREFIX = '/api';
const MODULE_PREFIX = '/ai-render-test';
const OUTPUT_PREFIX = `${MODULE_PREFIX}/output`;

type BlueprintSection = Record<string, unknown>;
type BlueprintState = {
  midi?: BlueprintSection | null;
  audio?: BlueprintSection | null;
} | null;

const timeFmt = (unix: number) => new Date(unix * 1000).toLocaleTimeString();

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;

const toBlueprintSection = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return { ...(value as Record<string, unknown>) };
};

const getErrorMessage = (err: unknown): string => {
  if (err instanceof Error && err.message) {
    return err.message;
  }
  if (typeof err === 'string') {
    return err;
  }
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
};

const extractErrorMessage = (value: unknown): string | null => {
  if (!isRecord(value)) {
    return null;
  }
  const detail = value['detail'];
  if (typeof detail === 'string') {
    return detail;
  }
  if (isRecord(detail)) {
    const detailMessage = detail['message'];
    if (typeof detailMessage === 'string') {
      return detailMessage;
    }
    const detailError = detail['error'];
    if (typeof detailError === 'string') {
      return detailError;
    }
  }
  const error = value['error'];
  if (typeof error === 'string') {
    return error;
  }
  const message = value['message'];
  if (typeof message === 'string') {
    return message;
  }
  return null;
};

const toStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
};

const toStringValue = (value: unknown): string | null => (typeof value === 'string' ? value : null);

const toRecord = (value: unknown): Record<string, unknown> | null => (isRecord(value) ? value : null);

const toRelativeArtifact = (value: string | null): string | null => {
  if (!value) {
    return null;
  }
  const segments = value.split(/\\|\//).slice(-2);
  if (!segments.length) {
    return value;
  }
  return segments.join('/');
};

const toStringRecord = (value: unknown): Record<string, string> | null => {
  const source = toRecord(value);
  if (!source) {
    return null;
  }
  const result: Record<string, string> = {};
  for (const [key, val] of Object.entries(source)) {
    if (typeof val === 'string') {
      result[key] = val;
    }
  }
  return Object.keys(result).length ? result : null;
};

const toRelativeRecord = (value: Record<string, string> | null): Record<string, string> | null => {
  if (!value) {
    return null;
  }
  const result: Record<string, string> = {};
  for (const [key, entry] of Object.entries(value)) {
    result[key] = toRelativeArtifact(entry) ?? entry;
  }
  return Object.keys(result).length ? result : null;
};

const toParamifyNormalizedPlan = (value: unknown): ParamifyNormalizedPlan | null => {
  if (!isRecord(value)) {
    return null;
  }
  const midiValue = value['midi'];
  const audioValue = value['audio'];
  return {
    midi: isRecord(midiValue) ? (midiValue as Partial<MidiParameters>) : null,
    audio: isRecord(audioValue) ? (audioValue as Partial<AudioRenderParameters>) : null,
  };
};

export default function AIParamTestPage() {
  const [midi, setMidi] = useState<MidiParameters>(() => cloneMidi(DEFAULT_MIDI));
  const [audio, setAudio] = useState<AudioRenderParameters>(() => cloneAudio(DEFAULT_AUDIO));
  const [runId, setRunId] = useState<string | null>(null);
  const [debugRun, setDebugRun] = useState<DebugRun | null>(null);
  const [polling, setPolling] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawResponse, setRawResponse] = useState<unknown>(null);
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [available, setAvailable] = useState<string[]>([]);
  const [audioFile, setAudioFile] = useState<string | null>(null);
  const [midiJsonFile, setMidiJsonFile] = useState<string | null>(null);
  const [midiMidFile, setMidiMidFile] = useState<string | null>(null);
  const [pianoRoll, setPianoRoll] = useState<string | null>(null);
  // Diagnostics inventory UI removed
  const [blueprint, setBlueprint] = useState<BlueprintState>(null);
  const [midiMidLayers, setMidiMidLayers] = useState<Record<string, string> | null>(null);
  const [pianoRollLayers, setPianoRollLayers] = useState<Record<string, string> | null>(null);
  const [audioStems, setAudioStems] = useState<Record<string, string> | null>(null);
  const [aiMidiData, setAiMidiData] = useState<any | null>(null);
  const [chatPrompt, setChatPrompt] = useState<string>('');
  const [chatProviders, setChatProviders] = useState<ChatProviderInfo[]>([]);
  const [chatProvider, setChatProvider] = useState<string>('');
  const [chatModels, setChatModels] = useState<string[]>([]);
  const [chatModel, setChatModel] = useState<string>('');
  const [chatStructured, setChatStructured] = useState<boolean>(true);
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatWarnings, setChatWarnings] = useState<string[]>([]);
  const [chatReply, setChatReply] = useState<string | null>(null);
  const [chatParamResult, setChatParamResult] = useState<ParamifyResultView | null>(null);
  const [chatRunId, setChatRunId] = useState<string | null>(null);
  const [chatDebug, setChatDebug] = useState<DebugRun | null>(null);
  const [selectedSamples, setSelectedSamples] = useState<Record<string, string>>({});

  const loadAvailable = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/available-instruments`);
      if (!res.ok) return;
      const data: AvailableInstruments = await res.json();
      const list = data.available || [];
      setAvailable(list);
      // Remove any instruments not in available (strict backend) and keep configs aligned
      setMidi(prev => {
        const filtered = prev.instruments.filter(i => list.includes(i));
        return {
          ...prev,
          instruments: filtered,
          instrument_configs: ensureInstrumentConfigs(filtered, prev.instrument_configs),
        };
      });
    } catch (e) {
      console.warn('avail fetch fail', e);
    }
  };
  // Inventory endpoints retained on backend but diagnostics UI removed

  const loadPresets = async () => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/presets`);
      if (!res.ok) return;
      const data: Record<string, { midi?: MidiParameters; audio?: AudioRenderParameters }> = await res.json();
      const full = data?.full;
      if (full?.midi) {
        const normalized = normalizeMidi(full.midi);
        setMidi(cloneMidi(normalized));
      }
      if (full?.audio) {
        setAudio(cloneAudio(normalizeAudio(full.audio)));
      }
    } catch (e) {
      console.warn('preset fetch fail', e);
    }
  };

  useEffect(() => {
    loadAvailable();
    loadPresets();
  }, []);

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/providers`);
        if (!res.ok) return;
        const data = await res.json();
        const list = Array.isArray(data?.providers) ? data.providers as ChatProviderInfo[] : [];
        setChatProviders(list);
        if (list.length > 0) {
          const first = list[0];
          setChatProvider(prev => (prev ? prev : first.id));
          setChatModel(prev => (prev ? prev : first.default_model ?? ''));
        }
      } catch (e) {
        console.warn('providers fetch fail', e);
      }
    };
    loadProviders();
  }, []);

  useEffect(() => {
    if (!chatProvider) {
      setChatModels([]);
      return;
    }
    const loadModels = async () => {
      try {
        const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/models/${chatProvider}`);
        if (!res.ok) {
          setChatModels([]);
          return;
        }
        const data = await res.json();
        const models = Array.isArray(data?.models) ? data.models as string[] : [];
        setChatModels(models);
        if (models.length > 0) {
          setChatModel(prev => (prev && models.includes(prev) ? prev : models[0]));
        } else {
          setChatModel(prev => prev);
        }
      } catch (e) {
        console.warn('models fetch fail', e);
        setChatModels([]);
      }
    };
    loadModels();
  }, [chatProvider]);

  const prettyJson = useCallback((value: unknown) => {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }, []);

  // Robustly extract a JSON object from raw model output, even if wrapped in code fences or extra text
  const extractJsonObject = useCallback((text: string): any | null => {
    if (!text) return null;
    let s = text.trim();
    // strip ```json ... ``` fences
    if (s.startsWith("```")) {
      const first = s.indexOf("\n");
      if (first !== -1) s = s.slice(first + 1);
      const lastFence = s.lastIndexOf("```");
      if (lastFence !== -1) s = s.slice(0, lastFence).trim();
    }
    // fast path
    try { return JSON.parse(s); } catch {}
    // fallback: take substring from first '{' to last '}'
    const start = s.indexOf('{');
    const end = s.lastIndexOf('}');
    if (start !== -1 && end !== -1 && end > start) {
      const sub = s.slice(start, end + 1);
      try { return JSON.parse(sub); } catch {}
    }
    return null;
  }, []);

  const applyParamPlan = useCallback((plan: ParamifyNormalizedPlan | null) => {
    const warnings: string[] = [];
    let appliedMidi: MidiParameters | null = null;
    let appliedAudio: AudioRenderParameters | null = null;

    const midiInput = plan?.midi ?? null;
    if (midiInput) {
      try {
        const normalized = normalizeMidi(midiInput);
        const availableSet = new Set(available);
        if (available.length > 0) {
          const allowed = normalized.instruments.filter(inst => availableSet.has(inst));
          if (allowed.length === 0) {
            warnings.push('Model zasugerował instrumenty niedostępne w lokalnej bibliotece. Pozostawiamy poprzednią konfigurację instrumentów.');
          } else {
            if (allowed.length !== normalized.instruments.length) {
              const missing = normalized.instruments.filter(inst => !availableSet.has(inst));
              warnings.push(`Pominięto niedostępne instrumenty: ${missing.join(', ')}`);
            }
            const adjustedConfigs = ensureInstrumentConfigs(allowed, normalized.instrument_configs);
            const nextMidi: MidiParameters = {
              ...normalized,
              instruments: allowed,
              instrument_configs: adjustedConfigs,
            };
            setMidi(cloneMidi(nextMidi));
            appliedMidi = nextMidi;
          }
        } else {
          setMidi(cloneMidi(normalized));
          appliedMidi = normalized;
        }
      } catch (e) {
        warnings.push(`Nie udało się zastosować parametrów MIDI: ${String(e)}`);
      }
    }

    const audioInput = plan?.audio ?? null;
    if (audioInput) {
      try {
        const normalized = normalizeAudio(audioInput);
        setAudio(cloneAudio(normalized));
        appliedAudio = normalized;
      } catch (e) {
        warnings.push(`Nie udało się zastosować parametrów audio: ${String(e)}`);
      }
    }

    if (appliedMidi || appliedAudio) {
      const midiSection = toBlueprintSection(appliedMidi);
      const audioSection = toBlueprintSection(appliedAudio);
      setBlueprint(prev => {
        const base: NonNullable<BlueprintState> = { ...(prev ?? {}) };
        return {
          ...base,
          midi: midiSection ?? base.midi ?? null,
          audio: audioSection ?? base.audio ?? null,
        };
      });
    }

    return { warnings, applied: { midi: appliedMidi, audio: appliedAudio } };
  }, [available]);

  const handleChatSend = useCallback(async () => {
    if (!chatPrompt.trim()) {
      setChatError('Wprowadź opis zanim wyślesz zapytanie.');
      return;
    }
    const providerId = chatProvider || chatProviders[0]?.id || 'gemini';
    setChatLoading(true);
    setChatError(null);
    setChatWarnings([]);
    setChatReply(null);
    setChatParamResult(null);
    setChatRunId(null);
    setChatDebug(null);
    try {
      const endpoint = chatStructured ? 'paramify' : 'send';
      const requestBody: Record<string, unknown> = {
        prompt: chatPrompt,
        provider: providerId,
      };
      if (chatModel) {
        requestBody.model = chatModel;
      }
      if (!chatStructured) {
        requestBody.structured = false;
      }
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });
      const payload: unknown = await res.json().catch(() => null);
      if (!res.ok) {
        const message = extractErrorMessage(payload) || res.statusText || (chatStructured ? 'Błąd podczas generowania parametrów.' : 'Błąd podczas konwersacji.');
        throw new Error(message);
      }

      const runIdValue = isRecord(payload) && typeof payload['run_id'] === 'string' ? payload['run_id'] : null;
      setChatRunId(runIdValue);

      if (chatStructured) {
        const normalizedBlock = toParamifyNormalizedPlan(isRecord(payload) ? payload['normalized'] : null);
        const applyResult = applyParamPlan(normalizedBlock);
        const rawSource = isRecord(payload) ? payload['raw'] : null;
        const rawString = typeof rawSource === 'string' ? rawSource : rawSource ? JSON.stringify(rawSource) : null;
        const errorsList = isRecord(payload) ? toStringArray(payload['errors']) : [];
        const result: ParamifyResultView = {
          provider: isRecord(payload) && typeof payload['provider'] === 'string' ? payload['provider'] : providerId,
          model: isRecord(payload) && typeof payload['model'] === 'string' ? payload['model'] : (chatModel || ''),
          raw: rawString,
          parsed: isRecord(payload) ? payload['parsed'] ?? null : null,
          normalized: normalizedBlock,
          applied: applyResult.applied,
          errors: errorsList.length > 0 ? errorsList : null,
        };
        const combinedWarnings = [...applyResult.warnings];
        if (result.errors) {
          combinedWarnings.push(...result.errors.map(err => `Backend: ${err}`));
        }
        if (!normalizedBlock?.midi && !normalizedBlock?.audio) {
          combinedWarnings.push('Model nie zwrócił pełnych parametrów.');
        }
        setChatParamResult(result);
        setChatWarnings(Array.from(new Set(combinedWarnings.filter(Boolean))));
      } else {
        const replySource = isRecord(payload) ? payload['reply'] : null;
        const replyText = typeof replySource === 'string'
          ? replySource
          : replySource
            ? JSON.stringify(replySource)
            : '';
        setChatReply(replyText || '(empty)');
      }
    } catch (err) {
      setChatError(getErrorMessage(err));
    } finally {
      setChatLoading(false);
    }
  }, [chatPrompt, chatStructured, chatProvider, chatProviders, chatModel, applyParamPlan]);

  const handleChatClear = useCallback(() => {
    setChatPrompt('');
    setChatError(null);
    setChatWarnings([]);
    setChatReply(null);
    setChatParamResult(null);
    setChatRunId(null);
    setChatDebug(null);
  }, []);

  const handleLoadChatDebug = useCallback(async () => {
    if (!chatRunId) return;
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/chat-smoke/debug/${chatRunId}`);
      if (!res.ok) {
        throw new Error(`Debug HTTP ${res.status}`);
      }
      const data = await res.json();
      setChatDebug(data);
    } catch (err) {
      const message = getErrorMessage(err);
      setChatError(prev => (prev ? `${prev}
Debug: ${message}` : `Debug: ${message}`));
    }
  }, [chatRunId]);

  const pollDebug = useCallback(async (rid: string) => {
    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/debug/${rid}`);
      const data = await res.json();
      if (data && data.run_id) {
        setDebugRun(data);
        if (data.events.some((e: DebugEvent) => e.stage === 'run' && e.message === 'completed')) {
          setPolling(false); setIsRunning(false);
        }
      }
  } catch { /* silent */ }
  }, []);
  useEffect(() => { if (polling && runId) { const id = setInterval(() => pollDebug(runId), 1000); return () => clearInterval(id); } }, [polling, runId, pollDebug]);

  const updateMidi = (patch: Partial<MidiParameters>) => setMidi(p => ({ ...p, ...patch }));
  const updateAudio = (patch: Partial<AudioRenderParameters>) => setAudio(p => ({...p, ...patch}));

  const toggleInstrument = (inst: string) => {
    const wasActive = midi.instruments.includes(inst);
    setMidi(prev => {
      const exists = prev.instruments.includes(inst);
      // Allow special virtual instrument 'drums' even if not in backend-available list.
      if (!exists && inst !== 'drums' && !available.includes(inst)) {
        return prev;
      }
      const nextInstruments = exists ? prev.instruments.filter(i => i !== inst) : [...prev.instruments, inst];
      return {
        ...prev,
        instruments: nextInstruments,
        instrument_configs: ensureInstrumentConfigs(nextInstruments, prev.instrument_configs),
      };
    });
    // Clean up any selected sample for removed instrument
    setSelectedSamples(prev => {
      const next = { ...prev };
      // If it was active, we just removed it; drop any selection
      if (wasActive && next[inst]) {
        delete next[inst];
      }
      return next;
    });
  };

  const updateInstrumentConfig = (name: string, patch: Partial<InstrumentConfig>) => {
    setMidi(prev => {
      const nextConfigs = prev.instrument_configs.map(cfg => {
        if (cfg.name !== name) return cfg;
        const next: InstrumentConfig = {
          ...cfg,
          ...patch,
        };
        if (patch.volume !== undefined) {
          const vol = Number(patch.volume);
          next.volume = clamp(Number.isFinite(vol) ? vol : cfg.volume, 0, 1);
        }
        if (patch.pan !== undefined) {
          const panValue = Number(patch.pan);
          next.pan = clamp(Number.isFinite(panValue) ? panValue : cfg.pan, -1, 1);
        }
        return { ...next };
      });
      return {
        ...prev,
        instrument_configs: ensureInstrumentConfigs(prev.instruments, nextConfigs),
      };
    });
  };
  // form removed

  // effects removed

  const run = async (mode: 'midi' | 'render' | 'full') => {
    setIsRunning(true);
    setError(null);
    setRunId(null);
    setDebugRun(null);
    setAudioFile(null);
    setMidiJsonFile(null);
    setMidiMidFile(null);
    setPianoRoll(null);
    setRawResponse(null);
    setResponseStatus(null);
    setBlueprint(null);
    setMidiMidLayers(null);
    setPianoRollLayers(null);
    setAudioStems(null);

    const buildMidiRequest = (params: MidiParameters) => ({
      ...params,
      genre: params.style,
      instrument_configs: params.instrument_configs.map(cfg => ({ ...cfg })),
    });

    const buildAudioRequest = (params: AudioRenderParameters) => ({
      ...params,
      sample_rate: Number(params.sample_rate),
      seconds: Number(params.seconds),
      master_gain_db: Number(params.master_gain_db),
    });

    const midiPayload = buildMidiRequest(midi);
    const audioPayload = buildAudioRequest(audio);

    let endpoint: string;
    let requestBody: Record<string, unknown>;
    if (mode === 'midi') {
      endpoint = `${MODULE_PREFIX}/run/midi`;
      requestBody = { ...midiPayload } as Record<string, unknown>;
      // Include composer provider/model hints (backend supports both direct and wrapped bodies)
      if (chatProvider) (requestBody as any).composer_provider = chatProvider;
      if (chatModel) (requestBody as any).composer_model = chatModel;
    } else if (mode === 'render') {
      endpoint = `${MODULE_PREFIX}/run/render`;
      requestBody = { midi: midiPayload, audio: audioPayload };
      if (chatProvider) (requestBody as any).composer_provider = chatProvider;
      if (chatModel) (requestBody as any).composer_model = chatModel;
    } else {
      endpoint = `${MODULE_PREFIX}/run/full`;
      requestBody = { midi: midiPayload, audio: audioPayload };
      if (chatProvider) (requestBody as any).composer_provider = chatProvider;
      if (chatModel) (requestBody as any).composer_model = chatModel;
    }
    // Attach user-selected samples if any
    const ssKeys = Object.keys(selectedSamples || {});
    if (mode !== 'midi' && ssKeys.length > 0) {
      (requestBody as any).selected_samples = selectedSamples;
    }

    try {
      const res = await fetch(`${API_BASE}${API_PREFIX}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });
      setResponseStatus(res.status);
      const payload: unknown = await res.json().catch(() => null);
      setRawResponse(payload);
      if (!res.ok) {
        setError(extractErrorMessage(payload) || `HTTP ${res.status}`);
        setIsRunning(false);
        return;
      }

      const data = toRecord(payload);
      if (!data) {
        setError('Unexpected response structure');
        setIsRunning(false);
        return;
      }

      const blueprintSource = toRecord(data['blueprint']);
      if (blueprintSource) {
        setBlueprint({
          midi: toBlueprintSection(blueprintSource['midi']),
          audio: toBlueprintSection(blueprintSource['audio']),
        });
      }

      const runIdValue = toStringValue(data['run_id']);
      if (runIdValue) {
        setRunId(runIdValue);
        setPolling(true);
      }

      const audioBlock = toRecord(data['audio']);
      const audioFileValue = toRelativeArtifact(toStringValue(audioBlock?.['audio_file_rel'] ?? null))
        ?? toRelativeArtifact(toStringValue(audioBlock?.['audio_file'] ?? null));
      setAudioFile(audioFileValue ?? null);
      if (audioBlock) {
        const stemsRecord = toRelativeRecord(
          toStringRecord(audioBlock['stems_rel']) ?? toStringRecord(audioBlock['stems']),
        );
        if (stemsRecord) {
          setAudioStems(stemsRecord);
        }
      }

      const midiJsonValue = toRelativeArtifact(toStringValue(data['midi_json_rel']))
        ?? toRelativeArtifact(toStringValue(data['midi_json']));
      setMidiJsonFile(midiJsonValue ?? null);

      const midiMidValue = toRelativeArtifact(toStringValue(data['midi_mid_rel']))
        ?? toRelativeArtifact(toStringValue(data['midi_mid']));
      setMidiMidFile(midiMidValue ?? null);

      const midiImageBlock = toRecord(data['midi_image']);
      const combinedValue = toRelativeArtifact(toStringValue(midiImageBlock?.['combined_rel'] ?? null))
        ?? toRelativeArtifact(toStringValue(midiImageBlock?.['combined'] ?? null));
      setPianoRoll(combinedValue ?? null);

      const midiImageLayers = toRelativeRecord(
        toStringRecord(data['midi_image_layers_rel']) ?? toStringRecord(data['midi_image_layers']),
      );
      if (midiImageLayers) {
        setPianoRollLayers(midiImageLayers);
      }

      const midiMidLayersValue = toRelativeRecord(
        toStringRecord(data['midi_mid_layers_rel']) ?? toStringRecord(data['midi_mid_layers']),
      );
      if (midiMidLayersValue) {
        setMidiMidLayers(midiMidLayersValue);
      }
    } catch (err) {
      setError(getErrorMessage(err));
      setIsRunning(false);
    }
  };

  // Build selectable instruments grouped logic: exclude drums and 'fx' from the generic list.
  // Drums and FX are handled as dedicated panels in MidiPanel.
  const DRUMS = ['kick','snare','hihat','clap','808'];
  const selectableInstruments = available.filter(i => !DRUMS.includes(i) && i !== 'fx');

  const formatBytes = (n?: number) => {
    if (!n || n <= 0) return '-';
    const units = ['B','KB','MB','GB'];
    let i=0; let v=n;
    while (v>=1024 && i<units.length-1) { v/=1024; i++; }
    return `${v.toFixed(1)} ${units[i]}`;
  };
  const formatSec = (s?: number | null) => (s==null? '-' : `${s.toFixed(2)}s`);
  const formatSummaryValue = (value: unknown, separator = ', '): string | undefined => {
    if (value === undefined || value === null) return undefined;
    if (Array.isArray(value)) {
      const parts = value
        .map(item => {
          if (item === undefined || item === null) return '';
          if (typeof item === 'object') {
            try {
              return JSON.stringify(item);
            } catch {
              return '';
            }
          }
          return String(item);
        })
        .filter(Boolean);
      if (parts.length === 0) return undefined;
      return parts.join(separator);
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return undefined;
      }
    }
    const text = String(value);
    if (text.trim() === '') return undefined;
    return text;
  };

  const blueprintMidi = toRecord(blueprint?.midi ?? null);
  const blueprintAudio = toRecord(blueprint?.audio ?? null);
  const paramsReady = !!(chatParamResult?.applied?.midi || blueprintMidi);

  const getMidiValue = (key: string): unknown => (blueprintMidi ? blueprintMidi[key] : undefined);
  const getAudioValue = (key: string): unknown => (blueprintAudio ? blueprintAudio[key] : undefined);

  const instrumentConfigsRaw = Array.isArray(getMidiValue('instrument_configs'))
    ? (getMidiValue('instrument_configs') as unknown[])
    : [];

  const blueprintInstrumentConfigs = instrumentConfigsRaw
    .map(item => {
      const record = toRecord(item);
      if (!record) {
        return null;
      }
      const name = toStringValue(record['name'])?.trim();
      if (!name) {
        return null;
      }
      const effectsSource = Array.isArray(record['effects']) ? (record['effects'] as unknown[]) : [];
      const effects = effectsSource
        .map(effect => {
          if (typeof effect === 'string') {
            return effect;
          }
          try {
            return String(effect);
          } catch {
            return '';
          }
        })
        .filter(effect => effect !== '');
      const volumeValue = record['volume'];
      const panValue = record['pan'];
      return {
        name,
        role: formatSummaryValue(record['role']) ?? '-',
        register: formatSummaryValue(record['register']) ?? '-',
        articulation: formatSummaryValue(record['articulation']) ?? '-',
        dynamic_range: formatSummaryValue(record['dynamic_range']) ?? '-',
        volume: typeof volumeValue === 'number' ? volumeValue : undefined,
        pan: typeof panValue === 'number' ? panValue : undefined,
        effects,
      };
    })
    .filter((item): item is {
      name: string;
      role: string;
      register: string;
      articulation: string;
      dynamic_range: string;
      volume: number | undefined;
      pan: number | undefined;
      effects: string[];
    } => item !== null);

  const blueprintMidiSummary: Array<[string, string]> = blueprintMidi
    ? ([
        ['style', formatSummaryValue(getMidiValue('style'))],
        ['mood', formatSummaryValue(getMidiValue('mood'))],
        ['tempo', typeof getMidiValue('tempo') === 'number' ? `${getMidiValue('tempo')} bpm` : undefined],
        ['key', formatSummaryValue(getMidiValue('key'))],
        ['scale', formatSummaryValue(getMidiValue('scale'))],
        ['meter', formatSummaryValue(getMidiValue('meter'))],
        ['length', typeof getMidiValue('length_seconds') === 'number' ? `${getMidiValue('length_seconds')}s` : undefined],
        ['bars', typeof getMidiValue('bars') === 'number' ? String(getMidiValue('bars')) : undefined],
        ['dynamic_profile', formatSummaryValue(getMidiValue('dynamic_profile'))],
        ['arrangement_density', formatSummaryValue(getMidiValue('arrangement_density'))],
        ['harmonic_color', formatSummaryValue(getMidiValue('harmonic_color'))],
        ['form', formatSummaryValue(getMidiValue('form'), ' → ')],
        ['instruments', formatSummaryValue(getMidiValue('instruments'))],
      ].filter(([, value]) => value !== undefined) as Array<[string, string]>)
    : [];

  const blueprintAudioSummary: Array<[string, string]> = blueprintAudio
    ? ([
        ['sample_rate', typeof getAudioValue('sample_rate') === 'number' ? `${getAudioValue('sample_rate')} Hz` : undefined],
        ['seconds', typeof getAudioValue('seconds') === 'number' ? `${getAudioValue('seconds')}s` : undefined],
        ['master_gain_db', typeof getAudioValue('master_gain_db') === 'number' ? `${getAudioValue('master_gain_db')} dB` : undefined],
      ].filter(([, value]) => value !== undefined) as Array<[string, string]>)
    : [];

  const blueprintHasData = blueprintMidiSummary.length > 0 || blueprintAudioSummary.length > 0 || blueprintInstrumentConfigs.length > 0;

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-black via-gray-950 to-black text-white px-6 py-10 space-y-10">
  <h1 className="text-3xl font-bold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-500">AI Param Test (Local Hybrid)</h1>
  <p className="text-sm text-gray-400 max-w-3xl">Eksperymentalny pipeline AI budowany na bazie lokalnych sampli: <span className='text-emerald-300'>MIDI → selekcja próbek → Audio</span>. Ta wersja zachowuje wszystkie restrykcje lokalne, ale będzie rozszerzana o generatywne modele. Wybieraj tylko instrumenty wykryte na backendzie.</p>

      <ChatPlanner
        prompt={chatPrompt}
        onPromptChange={setChatPrompt}
        providers={chatProviders}
        provider={chatProvider}
        onProviderChange={value => {
          setChatProvider(value);
          const found = chatProviders.find(item => item.id === value);
          if (found) {
            setChatModel(found.default_model ?? '');
          }
        }}
        models={chatModels}
        model={chatModel}
        onModelChange={setChatModel}
        structured={chatStructured}
        onStructuredChange={setChatStructured}
        onSend={handleChatSend}
        onClear={handleChatClear}
        loading={chatLoading}
        error={chatError}
        warnings={chatWarnings}
        reply={chatReply}
        paramResult={chatParamResult}
        runId={chatRunId}
        onLoadDebug={handleLoadChatDebug}
        debugData={chatDebug}
        prettyJson={prettyJson}
      />

      {/* Parameters panels */}
      <div className="grid md:grid-cols-3 gap-6">
        <MidiPanel
          midi={midi}
          availableInstruments={available}
          selectableInstruments={selectableInstruments}
          apiBase={API_BASE}
          apiPrefix={API_PREFIX}
          modulePrefix={MODULE_PREFIX}
          onUpdate={updateMidi}
          onToggleInstrument={toggleInstrument}
          onUpdateInstrumentConfig={updateInstrumentConfig}
          selectedSamples={selectedSamples}
          onSelectSample={(inst, id) => setSelectedSamples(prev => ({ ...prev, [inst]: id || '' }))}
        />
        <AudioPanel
          audio={audio}
          onUpdate={updateAudio}
        />
      </div>

      {/* AI MIDI composer below the entire parameters section; triggers the same flow as Run MIDI */}
      <ChatMidiComposer
        disabled={!paramsReady}
        midi={midi}
        providers={chatProviders}
        provider={chatProvider || (chatProviders[0]?.id || '')}
        onProviderChange={value => {
          setChatProvider(value);
          const found = chatProviders.find(item => item.id === value);
          if (found) setChatModel(found.default_model ?? '');
        }}
        models={chatModels}
        model={chatModel}
        onModelChange={setChatModel}
        apiBase={API_BASE}
        apiPrefix={API_PREFIX}
        modulePrefix={MODULE_PREFIX}
        onAfterCompose={({ parsed, raw }) => {
          // Prefer parsed JSON; fallback to parsing raw
          let aiMidi: any = parsed ?? null;
          if (!aiMidi && typeof raw === 'string') {
            aiMidi = extractJsonObject(raw);
          }
          if (!aiMidi) { return; }
          setAiMidiData(aiMidi);
          // Trigger the exact same post-processing as Run MIDI, but bypass recomposition by passing ai_midi
          (async () => {
            setIsRunning(true);
            setError(null);
            setRunId(null);
            setDebugRun(null);
            setAudioFile(null);
            setMidiJsonFile(null);
            setMidiMidFile(null);
            setPianoRoll(null);
            setRawResponse(null);
            setResponseStatus(null);
            setBlueprint(null);
            setMidiMidLayers(null);
            setPianoRollLayers(null);
            setAudioStems(null);

            const buildMidiRequest = (params: MidiParameters) => ({
              ...params,
              genre: params.style,
              instrument_configs: params.instrument_configs.map(cfg => ({ ...cfg })),
            });
            const midiPayload = buildMidiRequest(midi);
            const body: Record<string, unknown> = { ...midiPayload, ai_midi: aiMidi };
            if (chatProvider) (body as any).composer_provider = chatProvider;
            if (chatModel) (body as any).composer_model = chatModel;
            try {
              const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/run/midi`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
              });
              setResponseStatus(res.status);
              const payload: unknown = await res.json().catch(() => null);
              setRawResponse(payload);
              if (!res.ok) {
                setError(extractErrorMessage(payload) || `HTTP ${res.status}`);
                setIsRunning(false);
                return;
              }
              const data = toRecord(payload);
              if (!data) { setError('Unexpected response structure'); setIsRunning(false); return; }
              // Ensure we keep AI MIDI for subsequent render even if initial parse failed
              const midiObj = toRecord(data['midi']);
              if (midiObj) setAiMidiData(midiObj);
              const blueprintSource = toRecord(data['blueprint']);
              if (blueprintSource) {
                setBlueprint({ midi: toBlueprintSection(blueprintSource['midi']), audio: toBlueprintSection(blueprintSource['audio']) });
              }
              const rid = toStringValue(data['run_id']); if (rid) { setRunId(rid); setPolling(true); }
              const midiJsonValue = toRelativeArtifact(toStringValue(data['midi_json_rel'])) ?? toRelativeArtifact(toStringValue(data['midi_json']));
              setMidiJsonFile(midiJsonValue ?? null);
              const midiMidValue = toRelativeArtifact(toStringValue(data['midi_mid_rel'])) ?? toRelativeArtifact(toStringValue(data['midi_mid']));
              setMidiMidFile(midiMidValue ?? null);
              const midiImageBlock = toRecord(data['midi_image']);
              const combinedValue = toRelativeArtifact(toStringValue(midiImageBlock?.['combined_rel'] ?? null)) ?? toRelativeArtifact(toStringValue(midiImageBlock?.['combined'] ?? null));
              setPianoRoll(combinedValue ?? null);
              const midiImageLayers = toRelativeRecord(toStringRecord(data['midi_image_layers_rel']) ?? toStringRecord(data['midi_image_layers']));
              if (midiImageLayers) setPianoRollLayers(midiImageLayers);
              const midiMidLayersValue = toRelativeRecord(toStringRecord(data['midi_mid_layers_rel']) ?? toStringRecord(data['midi_mid_layers']));
              if (midiMidLayersValue) setMidiMidLayers(midiMidLayersValue);
            } catch (err) {
              setError(getErrorMessage(err));
            } finally {
              setIsRunning(false);
            }
          })();
        }}
      />

      {/* Render audio from last composed AI MIDI */}
      <div className="flex flex-wrap gap-4 border-t border-gray-800 pt-6">
        <button
          disabled={isRunning || !aiMidiData}
          onClick={async () => {
            if (!aiMidiData) return;
            setIsRunning(true);
            setError(null);
            setRunId(null);
            setDebugRun(null);
            setAudioFile(null);
            setMidiJsonFile(null);
            setMidiMidFile(null);
            setPianoRoll(null);
            setRawResponse(null);
            setResponseStatus(null);
            setBlueprint(null);
            setMidiMidLayers(null);
            setPianoRollLayers(null);
            setAudioStems(null);

            const buildMidiRequest = (params: MidiParameters) => ({
              ...params,
              genre: params.style,
              instrument_configs: params.instrument_configs.map(cfg => ({ ...cfg })),
            });
            const buildAudioRequest = (params: AudioRenderParameters) => ({
              ...params,
              sample_rate: Number(params.sample_rate),
              seconds: Number(params.seconds),
              master_gain_db: Number(params.master_gain_db),
            });

            const midiPayload = buildMidiRequest(midi);
            const audioPayload = buildAudioRequest(audio);
            const body: Record<string, unknown> = { midi: midiPayload, audio: audioPayload, ai_midi: aiMidiData };
            if (chatProvider) (body as any).composer_provider = chatProvider;
            if (chatModel) (body as any).composer_model = chatModel;
            const ssKeys = Object.keys(selectedSamples || {});
            if (ssKeys.length > 0) (body as any).selected_samples = selectedSamples;

            try {
              const res = await fetch(`${API_BASE}${API_PREFIX}${MODULE_PREFIX}/run/render`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
              });
              setResponseStatus(res.status);
              const payload: unknown = await res.json().catch(() => null);
              setRawResponse(payload);
              if (!res.ok) { setError(extractErrorMessage(payload) || `HTTP ${res.status}`); setIsRunning(false); return; }
                const data = toRecord(payload); if (!data) { setError('Unexpected response structure'); setIsRunning(false); return; }
                // Keep aiMidiData fresh from backend's echo of midi
                const midiObj = toRecord(data['midi']);
                if (midiObj) setAiMidiData(midiObj);
              const blueprintSource = toRecord(data['blueprint']);
              if (blueprintSource) setBlueprint({ midi: toBlueprintSection(blueprintSource['midi']), audio: toBlueprintSection(blueprintSource['audio']) });
              const rid = toStringValue(data['run_id']); if (rid) { setRunId(rid); setPolling(true); }
              const audioBlock = toRecord(data['audio']);
              const audioFileValue = toRelativeArtifact(toStringValue(audioBlock?.['audio_file_rel'] ?? null)) ?? toRelativeArtifact(toStringValue(audioBlock?.['audio_file'] ?? null));
              setAudioFile(audioFileValue ?? null);
              if (audioBlock) {
                const stemsRecord = toRelativeRecord(toStringRecord(audioBlock['stems_rel']) ?? toStringRecord(audioBlock['stems']));
                if (stemsRecord) setAudioStems(stemsRecord);
              }
              const midiJsonValue = toRelativeArtifact(toStringValue(data['midi_json_rel'])) ?? toRelativeArtifact(toStringValue(data['midi_json']));
              setMidiJsonFile(midiJsonValue ?? null);
              const midiMidValue = toRelativeArtifact(toStringValue(data['midi_mid_rel'])) ?? toRelativeArtifact(toStringValue(data['midi_mid']));
              setMidiMidFile(midiMidValue ?? null);
              const midiImageBlock = toRecord(data['midi_image']);
              const combinedValue = toRelativeArtifact(toStringValue(midiImageBlock?.['combined_rel'] ?? null)) ?? toRelativeArtifact(toStringValue(midiImageBlock?.['combined'] ?? null));
              setPianoRoll(combinedValue ?? null);
              const midiImageLayers = toRelativeRecord(toStringRecord(data['midi_image_layers_rel']) ?? toStringRecord(data['midi_image_layers']));
              if (midiImageLayers) setPianoRollLayers(midiImageLayers);
              const midiMidLayersValue = toRelativeRecord(toStringRecord(data['midi_mid_layers_rel']) ?? toStringRecord(data['midi_mid_layers']));
              if (midiMidLayersValue) setMidiMidLayers(midiMidLayersValue);
            } catch (err) {
              setError(getErrorMessage(err));
            } finally {
              setIsRunning(false);
            }
          }}
          className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700"
        >Render audio</button>
        {isRunning && <div className="text-sm text-gray-400 flex items-center">⏳ Running...</div>}
      </div>

      {/* Old run controls removed; flow is: Compose → (auto) finalize MIDI → Render audio */}
      {error && <div className="p-3 bg-red-900 text-sm rounded border border-red-600 max-w-xl">{error}</div>}

      {/* Raw response if no run id */}
      {responseStatus !== null && !runId && (
        <div className="p-4 bg-gray-900/60 border border-gray-800 rounded text-xs max-h-60 overflow-auto max-w-2xl">
          <div className="mb-1 text-gray-400">Raw response (status {responseStatus}):</div>
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify(rawResponse, null, 2)}</pre>
        </div>
      )}

      {blueprintHasData && (
        <div className="bg-gray-900/50 border border-emerald-800/50 rounded-lg p-4 space-y-4">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold text-emerald-300 text-sm uppercase tracking-wide">Blueprint snapshot</h3>
            {runId && <span className="text-[11px] text-gray-500">run {runId}</span>}
          </div>
          <div className="grid md:grid-cols-3 gap-4 text-xs">
            <div className="space-y-2">
              <div className="text-emerald-200 font-semibold">Composition</div>
              {blueprintMidiSummary.length === 0 && <div className="text-gray-500">Brak danych MIDI.</div>}
              {blueprintMidiSummary.length > 0 && (
                <dl className="space-y-1 text-gray-300">
                  {blueprintMidiSummary.map(([label, value]) => (
                    <div key={label} className="flex gap-2">
                      <dt className="text-gray-500 capitalize w-32 flex-shrink-0">{label.replace(/_/g, ' ')}</dt>
                      <dd className="text-emerald-100 break-words">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            <div className="space-y-2">
              <div className="text-cyan-200 font-semibold">Audio Render</div>
              {blueprintAudioSummary.length === 0 && <div className="text-gray-500">Brak danych audio.</div>}
              {blueprintAudioSummary.length > 0 && (
                <dl className="space-y-1 text-gray-300">
                  {blueprintAudioSummary.map(([label, value]) => (
                    <div key={label} className="flex gap-2">
                      <dt className="text-gray-500 capitalize w-32 flex-shrink-0">{label.replace(/_/g, ' ')}</dt>
                      <dd className="text-emerald-100 break-words">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            <div className="space-y-2">
              <div className="text-fuchsia-200 font-semibold">Instrument configs</div>
              {blueprintInstrumentConfigs.length === 0 && <div className="text-gray-500">Brak profili instrumentów.</div>}
              {blueprintInstrumentConfigs.length > 0 && (
                <div className="space-y-2">
                  {blueprintInstrumentConfigs.map(cfg => (
                    <div key={cfg.name} className="border border-gray-800/70 rounded p-2 space-y-1 bg-black/40">
                      <div className="text-emerald-200 font-semibold uppercase tracking-wide">{cfg.name}</div>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-gray-400">
                        <span>role: <span className="text-gray-200">{cfg.role}</span></span>
                        <span>register: <span className="text-gray-200">{cfg.register}</span></span>
                        <span>articulation: <span className="text-gray-200">{cfg.articulation}</span></span>
                        <span>dynamic: <span className="text-gray-200">{cfg.dynamic_range}</span></span>
                        {typeof cfg.volume === 'number' && <span>vol: <span className="text-gray-200">{cfg.volume.toFixed(2)}</span></span>}
                        {typeof cfg.pan === 'number' && <span>pan: <span className="text-gray-200">{cfg.pan.toFixed(2)}</span></span>}
                      </div>
                      {cfg.effects.length > 0 && (
                        <div className="flex flex-wrap gap-1 text-[9px] text-gray-500">
                          {cfg.effects.map(effect => (
                            <span key={effect} className="px-2 py-0.5 border border-gray-700 rounded uppercase tracking-wide">{effect}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Debug timeline */}
      <div className="bg-black/40 border border-gray-800 rounded-lg p-4 backdrop-blur-sm">
        <h3 className="font-semibold mb-4">Debug Events {runId && <span className="text-xs text-gray-400">(run {runId})</span>}</h3>
        {!debugRun && <div className="text-sm text-gray-500">Brak danych. Uruchom pipeline.</div>}
        {debugRun && (
          <ul className="text-xs space-y-1 max-h-80 overflow-auto font-mono">
            {debugRun.events.map((e, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="text-gray-500">{timeFmt(e.ts)}</span>
                <span className="text-emerald-400">[{e.stage}]</span>
                <span>{e.message}</span>
                {e.data && <span className="text-gray-400 truncate">{JSON.stringify(e.data)}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Artifacts */}
      {(audioFile || midiJsonFile || midiMidFile || pianoRoll || (midiMidLayers && Object.keys(midiMidLayers).length>0) || (pianoRollLayers && Object.keys(pianoRollLayers).length>0) || (audioStems && Object.keys(audioStems).length>0)) && (
        <div className="grid md:grid-cols-4 gap-6">
          {audioFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-blue-300 mb-2">Audio Preview</h3>
              <audio controls src={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${audioFile}`} className="w-full" />
              <div className="text-[10px] text-gray-500 mt-1 break-all">{audioFile}</div>
            </div>
          )}
          {midiJsonFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-orange-300 mb-2">MIDI Pattern (JSON)</h3>
              <a className="underline" target="_blank" href={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${midiJsonFile}`}>{midiJsonFile}</a>
              <div className="text-[10px] text-gray-500 mt-1">Strukturalna reprezentacja wygenerowanego patternu.</div>
            </div>
          )}
          {midiMidFile && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-fuchsia-300 mb-2">MIDI File (.mid)</h3>
              <a className="underline" target="_blank" href={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${midiMidFile}`}>{midiMidFile}</a>
              <div className="text-[10px] text-gray-500 mt-1">Pobierz plik MIDI do DAW.</div>
            </div>
          )}
          {pianoRoll && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs">
              <h3 className="font-semibold text-cyan-300 mb-2">Piano Roll</h3>
              <img src={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${pianoRoll}`} alt="pianoroll" className="w-full rounded" />
              <div className="text-[10px] text-gray-500 mt-1 break-all">{pianoRoll}</div>
            </div>
          )}
          {midiMidLayers && Object.keys(midiMidLayers).length>0 && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs md:col-span-2">
              <h3 className="font-semibold text-pink-300 mb-2">Per-instrument MIDI</h3>
              <ul className="space-y-1">
                {Object.entries(midiMidLayers).map(([inst, rel]) => (
                  <li key={inst} className="flex items-center justify-between gap-2">
                    <span className="text-emerald-200 uppercase tracking-wide">{inst}</span>
                    <a className="underline break-all" target="_blank" href={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${rel}`}>{rel}</a>
                  </li>
                ))}
              </ul>
              <div className="text-[10px] text-gray-500 mt-1">Osobne pliki .mid dla każdej warstwy instrumentu.</div>
            </div>
          )}
          {pianoRollLayers && Object.keys(pianoRollLayers).length>0 && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs md:col-span-2">
              <h3 className="font-semibold text-cyan-300 mb-2">Per-instrument Piano Rolls</h3>
              <div className="grid sm:grid-cols-2 gap-3">
                {Object.entries(pianoRollLayers).map(([inst, rel]) => (
                  <div key={inst} className="border border-gray-700 rounded p-2">
                    <div className="text-emerald-300 uppercase tracking-wide mb-1">{inst}</div>
                    <img src={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${rel}`} alt={`pianoroll-${inst}`} className="w-full rounded" />
                    <div className="text-[10px] text-gray-500 mt-1 break-all">{rel}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {audioStems && Object.keys(audioStems).length>0 && (
            <div className="bg-gray-900/60 p-4 rounded-lg border border-gray-700 text-xs md:col-span-2">
              <h3 className="font-semibold text-blue-300 mb-2">Per-instrument Audio Stems</h3>
              <div className="space-y-2">
                {Object.entries(audioStems).map(([inst, rel]) => (
                  <div key={inst} className="flex flex-col gap-1">
                    <div className="text-emerald-300 uppercase tracking-wide">{inst}</div>
                    <audio controls src={`${API_BASE}${API_PREFIX}${OUTPUT_PREFIX}/${rel}`} className="w-full" />
                    <div className="text-[10px] text-gray-500 break-all">{rel}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Diagnostics (local samples) removed */}

  <div className="mt-12 text-center text-xs text-gray-600">AI Param Test UI • Strict local samples (baseline)</div>
    </div>
  );
}
