export const STYLE_OPTIONS = [
  "Ambient","Jazz","Rock","Techno","Classical","Orchestral","Lofi","Hiphop","House","Metal","Trap","Pop","Cinematic","Folk","World","Experimental"
] as const;
export type StyleOption = (typeof STYLE_OPTIONS)[number];

export const MOOD_OPTIONS = [
  "Calm","Energetic","Melancholic","Joyful","Mysterious","Epic","Relaxed","Aggressive","Dreamy","Groovy","Romantic","Dark","Uplifting","Serene","Tense"
] as const;
export type MoodOption = (typeof MOOD_OPTIONS)[number];

export const KEY_OPTIONS = ["C","C#","Db","D","D#","Eb","E","F","F#","Gb","G","G#","Ab","A","A#","Bb","B"] as const;
export type KeyOption = (typeof KEY_OPTIONS)[number];

export const SCALE_OPTIONS = ["Major","Minor","Harmonic_minor","Melodic_minor","Dorian","Phrygian","Lydian","Mixolydian","Locrian","Pentatonic_major","Pentatonic_minor","Blues","Whole_tone","Phrygian_dominant","Hungarian_minor"] as const;
export type ScaleOption = (typeof SCALE_OPTIONS)[number];

export const METER_OPTIONS = ["4/4","3/4","6/8","5/4","7/8","12/8"] as const;
export type MeterOption = (typeof METER_OPTIONS)[number];

export const DYNAMIC_PROFILE_OPTIONS = ["Gentle","Moderate","Energetic"] as const;
export type DynamicProfileOption = (typeof DYNAMIC_PROFILE_OPTIONS)[number];

export const ARRANGEMENT_DENSITY_OPTIONS = ["Minimal","Balanced","Dense"] as const;
export type ArrangementDensityOption = (typeof ARRANGEMENT_DENSITY_OPTIONS)[number];

export const HARMONIC_COLOR_OPTIONS = ["Diatonic","Modal","Chromatic","Modulating","Experimental"] as const;
export type HarmonicColorOption = (typeof HARMONIC_COLOR_OPTIONS)[number];

export const REGISTER_OPTIONS = ["Low","Mid","High","Full"] as const;
export type RegisterOption = (typeof REGISTER_OPTIONS)[number];

export const ROLE_OPTIONS = ["Lead","Accompaniment","Rhythm","Pad","Bass","Percussion","Fx"] as const;
export type RoleOption = (typeof ROLE_OPTIONS)[number];

export const ARTICULATION_OPTIONS = ["Sustain","Staccato","Legato","Pizzicato","Accented","Slurred","Percussive","Glide","Arpeggiated"] as const;
export type ArticulationOption = (typeof ARTICULATION_OPTIONS)[number];

export const DYNAMIC_RANGE_OPTIONS = ["Delicate","Moderate","Intense"] as const;
export type DynamicRangeOption = (typeof DYNAMIC_RANGE_OPTIONS)[number];

export const DEFAULT_INSTRUMENTS = ["Piano","Pad","Strings"] as const;

// Instrument choices exposed in the main AIR UI. Keep drums in sync with
// backend "Drums" subtypes: Kick, Snare, Hat, Clap, Tom, Rim, Crash,
// Ride, Splash, Shake.
export const INSTRUMENT_CHOICES = [
  "Piano","Pad","Strings","Bass","Guitar","Lead","Choir","Flute","Trumpet","Saxophone",
  "Kick","Snare","Hat","Clap","Tom","Rim","Crash","Ride","Splash","Shake",
  "808","Perc","Drumkit","Fx"
] as const;
