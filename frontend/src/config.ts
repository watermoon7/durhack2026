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
  /** Channel level as a gain multiplier (1 = unchanged, 0.8 = 20% quieter). Defaults to 1. */
  readonly level?: number
}

/** Mixer channel per instrument; ids match backend INSTRUMENTS. Low instruments stay dry. */
const DEFAULT_MIX: Readonly<Record<string, MixPreset>> = {
  kick: { highpassHz: 0, eqDb: { low: 2, mid: 0, high: 0 }, reverbSend: 0.02 },
  snare: { highpassHz: 120, eqDb: { low: 0, mid: 0, high: 1 }, reverbSend: 0.15 },
  hihat: { highpassHz: 400, eqDb: { low: 0, mid: 0, high: 1 }, reverbSend: 0.08 },
  synth: { highpassHz: 150, eqDb: { low: -2, mid: 0, high: 2 }, reverbSend: 0.3 },
  bass: { highpassHz: 0, eqDb: { low: 1, mid: -1, high: -2 }, reverbSend: 0.03 },
  // Chord parts: high-passed and low-cut so their low roots don't muddy the bass.
  // Level set by ear (2026-11-15): the C minor chords were too loud, so 18% quieter.
  pad: { highpassHz: 90, eqDb: { low: -3, mid: 0, high: -1 }, reverbSend: 0.45, level: 0.82 },
  guitar: { highpassHz: 110, eqDb: { low: -2, mid: 0, high: 2 }, reverbSend: 0.25 },
}

/** Mixer channels per genre (ids match backend GENRES); a genre must cover every instrument. */
export const GENRE_MIX: Readonly<Record<string, Readonly<Record<string, MixPreset>>>> = {
  rock: {
    ...DEFAULT_MIX,
    // Levels set by ear (2026-11-15): guitar and cymbals were too loud, bass and organ too quiet.
    // Distortion is fizzy up top and boomy below: cut lows, lift mids, keep it fairly dry.
    guitar: { highpassHz: 120, eqDb: { low: -3, mid: 2, high: 0 }, reverbSend: 0.1, level: 0.8 },
    pad: { highpassHz: 90, eqDb: { low: -2, mid: 0, high: 0 }, reverbSend: 0.25, level: 1.4 },
    bass: { highpassHz: 0, eqDb: { low: 1, mid: -1, high: -2 }, reverbSend: 0.03, level: 1.5 },
    // The hi-hat piece also plays the crashes, so this turns down every cymbal.
    hihat: { highpassHz: 400, eqDb: { low: 0, mid: 0, high: 1 }, reverbSend: 0.08, level: 0.64 },
  },
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
const LM2_KIT_URL = `${SAMPLES_BASE_URL}drums/LM-2/dm.json`

/** dataTransfer type used when dragging a stock onto an instrument. */
export const DRAG_MIME = 'application/x-market-band-dataset'

/** Seeking with the progress bar snaps to a multiple of this many beats (1 = nearest beat). */
export const SEEK_SNAP_BEATS = 1

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
  /** Accent notes (backend DRUM_ACCENT_NOTES) -> their own sample, played untuned. */
  readonly accents?: Readonly<Record<number, string>>
}

export type SoundPreset = PitchedPreset | DrumPreset

/** Sound of each instrument; ids match backend INSTRUMENTS. */
const DEFAULT_SOUNDS: Readonly<Record<string, SoundPreset>> = {
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

/** Rock: distorted guitar, pick bass, rock organ and a LinnDrum (LM-2) kit with crash and toms. */
const ROCK_SOUNDS: Readonly<Record<string, SoundPreset>> = {
  ...DEFAULT_SOUNDS,
  kick: { kind: 'drum', kitUrl: LM2_KIT_URL, sample: 'kick', volume: 115 },
  snare: {
    kind: 'drum',
    kitUrl: LM2_KIT_URL,
    sample: 'snare-m',
    volume: 110,
    accents: { 47: 'tom-hh', 45: 'tom-h', 43: 'tom-m', 41: 'tom-l' },
  },
  hihat: {
    kind: 'drum',
    kitUrl: LM2_KIT_URL,
    sample: 'hhclosed',
    volume: 95,
    accents: { 49: 'crash' },
  },
  bass: {
    kind: 'pitched',
    url: `${SAMPLES_BASE_URL}soundfonts/electric_bass_pick-mp3.js`,
    volume: 95,
  },
  pad: { kind: 'pitched', url: `${SAMPLES_BASE_URL}soundfonts/rock_organ-mp3.js`, volume: 85 },
  guitar: {
    kind: 'pitched',
    url: `${SAMPLES_BASE_URL}soundfonts/distortion_guitar-mp3.js`,
    volume: 100,
  },
}

/** Sounds per genre (ids match backend GENRES); a genre must cover every instrument. */
export const GENRE_SOUNDS: Readonly<Record<string, Readonly<Record<string, SoundPreset>>>> = {
  rock: ROCK_SOUNDS,
}

/** URL hash that opens a scenario's stage, e.g. `#scenario/2020_covid_crash_rebound`; no hash shows the menu. */
export const SCENARIO_HASH_PREFIX = '#scenario/'

/** A scenario's sung track: one audio file, played from beat 0 of every loop when turned on. */
export interface VoiceTrack {
  readonly url: string
  readonly title: string
}

/** Sung track per scenario id (files in public/voice/, see its README). No entry: no voice. */
export const VOICE_TRACKS: Readonly<Record<string, VoiceTrack>> = {
  '2010_flash_crash': { url: `${SAMPLES_BASE_URL}voice/2010_flash_crash.mp3`, title: 'Flash Crash Ride' },
  '2011_debt_ceiling_euro_crisis': {
    url: `${SAMPLES_BASE_URL}voice/2011_debt_ceiling_euro_crisis.mp3`,
    title: 'Raise The Roof',
  },
  '2013_taper_tantrum': { url: `${SAMPLES_BASE_URL}voice/2013_taper_tantrum.mp3`, title: 'Bond Market Tantrum' },
  '2015_china_devaluation': { url: `${SAMPLES_BASE_URL}voice/2015_china_devaluation.mp3`, title: 'Panic Song' },
  '2016_oil_growth_scare': { url: `${SAMPLES_BASE_URL}voice/2016_oil_growth_scare.mp3`, title: 'Barrel Roll Blues' },
  '2016_brexit_us_equities': { url: `${SAMPLES_BASE_URL}voice/2016_brexit_us_equities.mp3`, title: 'Brexit Boogie' },
  '2016_us_election': { url: `${SAMPLES_BASE_URL}voice/2016_us_election.mp3`, title: 'Election Night Shuffle' },
  '2018_february_volatility': { url: `${SAMPLES_BASE_URL}voice/2018_february_volatility.mp3`, title: 'VIX Tricks' },
  '2018_q4_selloff': { url: `${SAMPLES_BASE_URL}voice/2018_q4_selloff.mp3`, title: 'Santa Protect My Cash' },
  '2020_covid_crash_rebound': {
    url: `${SAMPLES_BASE_URL}voice/2020_covid_crash_rebound.mp3`,
    title: 'Market Rollercoaster',
  },
}

/** Voice level in dB. It bypasses the band's mixer, so this is its only level control. */
export const VOICE_VOLUME_DB = -6

/** Loop length while the voice is on: the backend's song length (SONG_BEATS, 64 = 32 s). */
export const VOICE_LOOP_BEATS = 64
