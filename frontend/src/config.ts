/** Static configuration for the Market Band frontend. */

import type { Dataset, Instrument } from './api' // type-only: no runtime cycle with api.ts

/** Base URL of the local FastAPI backend (see backend config API_HOST / API_PORT). */
export const API_BASE_URL = 'http://127.0.0.1:8000'

/** Master output level. Measured: full band on Q1 2020 data peaks ~0.35 of full scale at -2 dB. */
export const MASTER_VOLUME_DB = -2

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
    url: `${SAMPLES_BASE_URL}soundfonts/acoustic_guitar_nylon-mp3.js`,
    volume: 100,
  },
}

// --- Friend's pre-rendered songs (Market_Events_to_MIDI.py, data/market_events_v3 on main) ---

/** Where the copied song.mid files are served from (public/songs/<id>.mid). */
export const SONGS_BASE_URL = `${SAMPLES_BASE_URL}songs/`

/** The songs shown in the tray. `ticker` is the short label on the stage tags. */
export const SONGS: readonly Dataset[] = [
  { id: '2010_flash_crash', ticker: 'FLASH', name: '2010 flash crash', period: 'Apr–Nov 2010' },
  { id: '2011_debt_ceiling_euro_crisis', ticker: 'DEBT', name: '2011 debt ceiling & euro crisis', period: 'Apr 2011–Mar 2012' },
  { id: '2013_taper_tantrum', ticker: 'TAPER', name: '2013 taper tantrum', period: 'Apr–Sep 2013' },
  { id: '2015_china_devaluation', ticker: 'CHINA', name: '2015 China devaluation', period: 'Jun–Nov 2015' },
  { id: '2016_oil_growth_scare', ticker: 'OIL', name: '2016 oil & growth scare', period: 'Dec 2015–May 2016' },
  { id: '2016_brexit_us_equities', ticker: 'BREXIT', name: '2016 Brexit (US equities)', period: 'Jun–Aug 2016' },
  { id: '2016_us_election', ticker: 'ELECTION', name: '2016 US election', period: 'Sep 2016–Jan 2017' },
  { id: '2018_february_volatility', ticker: 'FEB 18', name: '2018 February volatility', period: 'Jan–Sep 2018' },
  { id: '2018_q4_selloff', ticker: 'Q4 18', name: '2018 Q4 selloff', period: 'Sep 2018–May 2019' },
  { id: '2020_covid_crash_rebound', ticker: 'COVID', name: '2020 COVID crash & rebound', period: 'Dec 2019–Feb 2021' },
]

/** Song track name -> band instrument id (the drums track is split separately). */
export const SONG_TRACK_ROUTES: Readonly<Record<string, string>> = {
  bass: 'bass',
  synth_lead: 'synth',
  synth_pad: 'pad',
  guitar: 'guitar',
}

/** The song's General MIDI drum track, split by note number into the three drum voices. */
export const SONG_DRUM_TRACK = 'drums'
export const SONG_DRUM_NOTES: Readonly<Record<number, string>> = { 36: 'kick', 38: 'snare', 42: 'hihat' }

/** Song parts with no stage piece: played by the band, not drawn. root_midi only tunes drums. */
export const SONG_EXTRA_INSTRUMENTS: readonly Instrument[] = [
  { id: 'pad', name: 'Pad', root_midi: 48, octaves: 2 },
  { id: 'guitar', name: 'Guitar', root_midi: 48, octaves: 2 },
]
