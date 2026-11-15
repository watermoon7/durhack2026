/** Static configuration for the Market Band frontend. */

/** Base URL of the local FastAPI backend (see backend config API_HOST / API_PORT). */
export const API_BASE_URL = 'http://127.0.0.1:8000'

/**
 * Master output level, applied after the compressor and limiter. Measured on Q1 2020 data at
 * -2 dB: SPY on all seven pieces peaks at ~0.28 of full scale, a mixed band at ~0.38.
 */
export const MASTER_VOLUME_DB = -2

/** One instrument's mixer channel (see audio/mix.ts). */
export interface MixPreset {
  /** High-pass cutoff in Hz; 0 means no high-pass. */
  readonly highpassHz: number
  /** 3-band EQ gains in dB. */
  readonly eqDb: { readonly low: number; readonly mid: number; readonly high: number }
  /** How much of the channel is sent to the shared reverb, 0-1. */
  readonly reverbSend: number
}

/** Mixer channel per instrument; ids match backend INSTRUMENTS. Low instruments stay dry. */
export const MIX_PRESETS: Readonly<Record<string, MixPreset>> = {
  kick: { highpassHz: 0, eqDb: { low: 2, mid: 0, high: 0 }, reverbSend: 0.02 },
  snare: { highpassHz: 120, eqDb: { low: 0, mid: 0, high: 1 }, reverbSend: 0.15 },
  hihat: { highpassHz: 400, eqDb: { low: 0, mid: 0, high: 1 }, reverbSend: 0.08 },
  synth: { highpassHz: 150, eqDb: { low: -2, mid: 0, high: 2 }, reverbSend: 0.3 },
  bass: { highpassHz: 0, eqDb: { low: 1, mid: -1, high: -2 }, reverbSend: 0.03 },
  // Chord parts: high-passed and low-cut so their low roots don't muddy the bass.
  pad: { highpassHz: 90, eqDb: { low: -3, mid: 0, high: -1 }, reverbSend: 0.45 },
  guitar: { highpassHz: 110, eqDb: { low: -2, mid: 0, high: 2 }, reverbSend: 0.25 },
}

/** Shared reverb tail length in seconds. */
export const REVERB_DECAY_S = 2.2

/** Master compressor: gentle glue ahead of the limiter. */
export const COMPRESSOR = { thresholdDb: -18, ratio: 3 } as const

/** Master limiter ceiling in dB, so the output can never clip. */
export const LIMITER_DB = -1

/**
 * Pitched voices: velocity 0 -> BRIGHTNESS_MIN_HZ, velocity 1 -> BRIGHTNESS_MAX_HZ (exponential
 * sweep), applied as a per-note lowpass. Recorded instruments turn muffled below ~800 Hz.
 */
export const BRIGHTNESS_MIN_HZ = 800
export const BRIGHTNESS_MAX_HZ = 12000

/**
 * Drums: fraction of the backend's note range that becomes tuning. The backend gives drums a
 * 1-octave range; 0.25 turns that into a 3-semitone shift so the kit stays a kit.
 */
export const DRUM_TUNING_DEPTH = 0.25

/** Top of the MIDI 0-127 scale; smplr takes velocities on it, @tonejs/midi gives 0-1. */
export const MIDI_VELOCITY_MAX = 127

/** Self-hosted sample files, served from public/ (credits in public/soundfonts/README.md). */
const SAMPLES_BASE_URL = import.meta.env.BASE_URL
const DRUM_KIT_URL = `${SAMPLES_BASE_URL}drums/TR-808/dm.json`

/** dataTransfer type used when dragging a stock onto an instrument. */
export const DRAG_MIME = 'application/x-market-band-dataset'

/** How long an instrument stays lit after it plays a note, in ms. */
export const PULSE_MS = 120

/** Sparkline geometry inside a stock box (box-local px). */
export const SPARK_WIDTH = 108
export const SPARK_HEIGHT = 22

/** A pitched voice: a MIDI.js soundfont file played by smplr's Soundfont. */
export interface PitchedPreset {
  readonly kind: 'pitched'
  readonly url: string
  /** smplr instrument volume, 0-127. */
  readonly volume: number
}

/** A drum voice: one named sample from a smplr drum-machine manifest (dm.json). */
export interface DrumPreset {
  readonly kind: 'drum'
  readonly kitUrl: string
  readonly sample: string
  /** smplr instrument volume, 0-127. */
  readonly volume: number
}

export type SoundPreset = PitchedPreset | DrumPreset

/** Sound of each instrument; ids match backend INSTRUMENTS. */
export const SOUND_PRESETS: Readonly<Record<string, SoundPreset>> = {
  kick: { kind: 'drum', kitUrl: DRUM_KIT_URL, sample: 'kick/bd2550', volume: 115 },
  snare: { kind: 'drum', kitUrl: DRUM_KIT_URL, sample: 'snare/sd5050', volume: 110 },
  hihat: { kind: 'drum', kitUrl: DRUM_KIT_URL, sample: 'hihat-close/ch', volume: 95 },
  synth: {
    kind: 'pitched',
    url: `${SAMPLES_BASE_URL}soundfonts/acoustic_grand_piano-mp3.js`,
    volume: 127,
  },
  bass: {
    kind: 'pitched',
    url: `${SAMPLES_BASE_URL}soundfonts/electric_bass_finger-mp3.js`,
    volume: 95,
  },
  pad: { kind: 'pitched', url: `${SAMPLES_BASE_URL}soundfonts/pad_2_warm-mp3.js`, volume: 80 },
  guitar: {
    kind: 'pitched',
    url: `${SAMPLES_BASE_URL}soundfonts/acoustic_guitar_steel-mp3.js`,
    volume: 100,
  },
}
