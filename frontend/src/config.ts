/** Static configuration for the Market Band frontend. */

/** Base URL of the local FastAPI backend (see backend config API_HOST / API_PORT). */
export const API_BASE_URL = 'http://127.0.0.1:8000'

/** Master output level; four synths summed would otherwise clip. */
export const MASTER_VOLUME_DB = -12

/** Velocity 0 -> BRIGHTNESS_MIN_HZ, velocity 1 -> BRIGHTNESS_MAX_HZ (exponential sweep). */
export const BRIGHTNESS_MIN_HZ = 250
export const BRIGHTNESS_MAX_HZ = 6000
export const FILTER_Q = 1

/** dataTransfer type used when dragging a dataset onto an instrument. */
export const DRAG_MIME = 'application/x-market-band-dataset'

/** Price-shape chart size in px (viewBox units; the SVG scales to its container). */
export const CHART_WIDTH = 320
export const CHART_HEIGHT = 64

/** Sound of one instrument; ids match backend INSTRUMENTS. */
export interface SoundPreset {
  readonly oscillator: 'square' | 'sawtooth' | 'fatsawtooth' | 'fmsine'
  readonly attack: number
  readonly decay: number
  readonly sustain: number
  readonly release: number
  readonly volumeDb: number
}

export const SOUND_PRESETS: Readonly<Record<string, SoundPreset>> = {
  bass: { oscillator: 'square', attack: 0.01, decay: 0.2, sustain: 0.6, release: 0.1, volumeDb: -4 },
  keys: { oscillator: 'sawtooth', attack: 0.02, decay: 0.3, sustain: 0.5, release: 0.2, volumeDb: -8 },
  lead: { oscillator: 'fatsawtooth', attack: 0.01, decay: 0.1, sustain: 0.7, release: 0.15, volumeDb: -10 },
  bells: { oscillator: 'fmsine', attack: 0.001, decay: 0.4, sustain: 0.1, release: 0.4, volumeDb: -6 },
}
