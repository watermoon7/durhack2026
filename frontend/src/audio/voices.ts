/**
 * Instrument voices: one smplr sample player per band member, behind a common trigger interface
 * so the band can schedule pitched and drum notes the same way. All samples are self-hosted
 * under public/ and start loading as soon as the voice is created.
 */

import { DrumMachine, Soundfont, type Smplr } from 'smplr'
import {
  BRIGHTNESS_MAX_HZ,
  BRIGHTNESS_MIN_HZ,
  DRUM_TUNING_DEPTH,
  MIDI_VELOCITY_MAX,
  type DrumPreset,
  type PitchedPreset,
  type SoundPreset,
} from '../config'

/** A playable voice. `midi` is the backend note; drums read it as tuning. */
export interface Voice {
  /** Resolves once every sample is fetched and decoded; rejects if any fails to load. */
  readonly ready: Promise<void>
  /** Play one note at AudioContext `time` (seconds); `velocity` is 0-1. */
  trigger(midi: number, durationSeconds: number, time: number, velocity: number): void
  /** Cut every sounding note now. */
  silence(): void
  dispose(): void
}

/** Clamp a 0..1 velocity. */
function clampUnit(velocity: number): number {
  if (!Number.isFinite(velocity)) throw new Error(`invalid velocity ${velocity}`)
  return Math.min(Math.max(velocity, 0), 1)
}

/** Map a 0..1 velocity onto smplr's 1..127 scale (0 would be silent). */
function toMidiVelocity(velocity: number): number {
  return Math.max(1, Math.round(clampUnit(velocity) * MIDI_VELOCITY_MAX))
}

/** Map a 0..1 velocity onto an exponential filter-cutoff sweep. */
function velocityToCutoff(velocity: number): number {
  return BRIGHTNESS_MIN_HZ * (BRIGHTNESS_MAX_HZ / BRIGHTNESS_MIN_HZ) ** clampUnit(velocity)
}

/** Detune a drum by a fraction of how far `midi` sits above the range root, in cents. */
function drumCents(midi: number, rootMidi: number): number {
  if (!Number.isFinite(midi)) throw new Error(`invalid midi note ${midi}`)
  return (midi - rootMidi) * DRUM_TUNING_DEPTH * 100
}

/** Wrap a loaded smplr instrument's lifecycle into the parts of Voice that don't play notes. */
function lifecycle(player: Smplr): Pick<Voice, 'ready' | 'silence' | 'dispose'> {
  return {
    ready: player.ready,
    silence: () => player.stop(),
    dispose: () => player.dispose(),
  }
}

/** Sampled melodic instrument; velocity sets loudness and a per-note lowpass. */
function createPitched(preset: PitchedPreset, context: AudioContext, output: AudioNode): Voice {
  if (preset.url === '') throw new Error('pitched preset needs a soundfont url')
  const player = Soundfont(context, {
    instrumentUrl: preset.url,
    destination: output,
    volume: preset.volume,
  })
  return {
    ...lifecycle(player),
    trigger: (midi, durationSeconds, time, velocity) => {
      // The returned stop function is not needed: notes end on their own duration.
      void player.start({
        note: midi,
        velocity: toMidiVelocity(velocity),
        time,
        duration: durationSeconds,
        lpfCutoffHz: velocityToCutoff(velocity),
      })
    },
  }
}

/**
 * One drum-machine sample, retuned by the backend note; it rings for its natural length.
 * Accent notes (Rock crash and toms) play their own sample untuned instead.
 */
function createDrum(
  preset: DrumPreset,
  rootMidi: number,
  context: AudioContext,
  output: AudioNode,
): Voice {
  if (preset.sample === '') throw new Error('drum preset needs a sample name')
  const player = DrumMachine(context, {
    url: preset.kitUrl,
    destination: output,
    volume: preset.volume,
  })
  return {
    ...lifecycle(player),
    trigger: (midi, _durationSeconds, time, velocity) => {
      const accent = preset.accents?.[midi]
      // The returned stop function is not needed: a re-trigger cuts the previous hit.
      void player.start({
        note: accent ?? preset.sample,
        velocity: toMidiVelocity(velocity),
        time,
        detune: accent === undefined ? drumCents(midi, rootMidi) : 0,
      })
    },
  }
}

/** Build the voice for a preset. `rootMidi` is the instrument's lowest backend note. */
export function createVoice(
  preset: SoundPreset,
  rootMidi: number,
  context: AudioContext,
  output: AudioNode,
): Voice {
  if (!Number.isInteger(rootMidi)) throw new Error(`rootMidi must be an integer, got ${rootMidi}`)
  switch (preset.kind) {
    case 'pitched':
      return createPitched(preset, context, output)
    case 'drum':
      return createDrum(preset, rootMidi, context, output)
  }
}
