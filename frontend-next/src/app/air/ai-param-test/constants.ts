export const STYLE_OPTIONS = [
  'ambient','jazz','rock','techno','classical','orchestral','lofi','hiphop','house','metal','trap','pop','cinematic','folk','world','experimental'
] as const;
export type StyleOption = typeof STYLE_OPTIONS[number];

export const MOOD_OPTIONS = [
  'calm','energetic','melancholic','joyful','mysterious','epic','relaxed','aggressive','dreamy','groovy','romantic','dark','uplifting','serene','tense'
] as const;
export type MoodOption = typeof MOOD_OPTIONS[number];

export const KEY_OPTIONS = ['C','C#','Db','D','D#','Eb','E','F','F#','Gb','G','G#','Ab','A','A#','Bb','B'] as const;
export type KeyOption = typeof KEY_OPTIONS[number];

export const SCALE_OPTIONS = ['major','minor','harmonic_minor','melodic_minor','dorian','phrygian','lydian','mixolydian','locrian','pentatonic_major','pentatonic_minor','blues','whole_tone','phrygian_dominant','hungarian_minor'] as const;
export type ScaleOption = typeof SCALE_OPTIONS[number];

export const METER_OPTIONS = ['4/4','3/4','6/8','5/4','7/8','12/8'] as const;
export type MeterOption = typeof METER_OPTIONS[number];

export const DYNAMIC_PROFILE_OPTIONS = ['gentle','moderate','energetic'] as const;
export type DynamicProfileOption = typeof DYNAMIC_PROFILE_OPTIONS[number];

export const ARRANGEMENT_DENSITY_OPTIONS = ['minimal','balanced','dense'] as const;
export type ArrangementDensityOption = typeof ARRANGEMENT_DENSITY_OPTIONS[number];

export const HARMONIC_COLOR_OPTIONS = ['diatonic','modal','chromatic','modulating','experimental'] as const;
export type HarmonicColorOption = typeof HARMONIC_COLOR_OPTIONS[number];

export const REGISTER_OPTIONS = ['low','mid','high','full'] as const;
export type RegisterOption = typeof REGISTER_OPTIONS[number];

export const ROLE_OPTIONS = ['lead','accompaniment','rhythm','pad','bass','percussion','fx'] as const;
export type RoleOption = typeof ROLE_OPTIONS[number];

export const ARTICULATION_OPTIONS = ['sustain','staccato','legato','pizzicato','accented','slurred','percussive','glide','arpeggiated'] as const;
export type ArticulationOption = typeof ARTICULATION_OPTIONS[number];

export const DYNAMIC_RANGE_OPTIONS = ['delicate','moderate','intense'] as const;
export type DynamicRangeOption = typeof DYNAMIC_RANGE_OPTIONS[number];

export const EFFECT_OPTIONS = ['reverb','delay','chorus','distortion','filter','compression','phaser','flanger','shimmer','lofi'] as const;

export const DEFAULT_FORM = ['intro','verse','chorus','verse','chorus','bridge','chorus','outro'] as const;
export const DEFAULT_INSTRUMENTS = ['piano','pad','strings'] as const;

export const INSTRUMENT_CHOICES = ['piano','pad','strings','bass','guitar','lead','choir','flute','trumpet','saxophone','kick','snare','hihat','clap','rim','tom','808','perc','drumkit','fx'] as const;

export const FORM_SECTION_OPTIONS = ['intro','verse','chorus','pre-chorus','bridge','build','drop','solo','breakdown','outro'] as const;

export const AUDIO_MODEL_OPTIONS = ['basic','enhanced','neural','hybrid'] as const;
export type AudioModelOption = typeof AUDIO_MODEL_OPTIONS[number];

export const MIXING_STYLE_OPTIONS = ['neutral','wide','warm','punchy','vintage','cinematic'] as const;
export type MixingStyleOption = typeof MIXING_STYLE_OPTIONS[number];

export const MASTERING_STYLE_OPTIONS = ['transparent','loud','analog','broadcast','club'] as const;
export type MasteringStyleOption = typeof MASTERING_STYLE_OPTIONS[number];

export const SAMPLE_RATE_OPTIONS = [44100, 48000, 96000, 192000] as const;
export type SampleRateOption = typeof SAMPLE_RATE_OPTIONS[number];

export const BIT_DEPTH_OPTIONS = [16, 24, 32] as const;
export type BitDepthOption = typeof BIT_DEPTH_OPTIONS[number];

export const LOUDNESS_TARGET_OPTIONS = ['streaming','broadcast','club','cinema'] as const;
export type LoudnessTargetOption = typeof LOUDNESS_TARGET_OPTIONS[number];

export const REFERENCE_METER_OPTIONS = ['rms','crest_factor','true_peak','lufs_short','lufs_integrated','dynamic_range'] as const;
export type ReferenceMeterOption = typeof REFERENCE_METER_OPTIONS[number];
