/**
 * The band's audio engine: one synth + brightness filter per instrument, all scheduled on
 * Tone's shared Transport so every instrument plays against the same clock.
 *
 * Lifecycle: create once per page with createBand(), call dispose() on unmount. Scheduled
 * event ids per voice are replaced wholesale on load() and dropped on clear(), so they never
 * grow beyond one MIDI file's notes per instrument.
 */

import type { Midi } from '@tonejs/midi'
import * as Tone from 'tone'
import {
  BRIGHTNESS_MAX_HZ,
  BRIGHTNESS_MIN_HZ,
  FILTER_Q,
  MASTER_VOLUME_DB,
  SOUND_PRESETS,
} from '../config'

interface Voice {
  readonly synth: Tone.Synth
  readonly filter: Tone.Filter
  eventIds: number[]
  beats: number
}

export interface Band {
  /** Schedule a parsed MIDI file on an instrument, replacing whatever it played before. */
  load(instrumentId: string, midi: Midi): void
  /** Silence an instrument. */
  clear(instrumentId: string): void
  play(): Promise<void>
  stop(): void
  /** Current playhead position in beats (fractional). */
  currentBeat(): number
  dispose(): void
}

/** Map a 0..1 velocity onto an exponential filter-cutoff sweep. */
function velocityToCutoff(velocity: number): number {
  const clamped = Math.min(Math.max(velocity, 0), 1)
  return BRIGHTNESS_MIN_HZ * (BRIGHTNESS_MAX_HZ / BRIGHTNESS_MIN_HZ) ** clamped
}

/** Build one instrument's synth -> filter chain. */
function createVoice(instrumentId: string, output: Tone.ToneAudioNode): Voice {
  const preset = SOUND_PRESETS[instrumentId]
  if (preset === undefined) throw new Error(`no sound preset for instrument '${instrumentId}'`)
  const filter = new Tone.Filter({ type: 'lowpass', frequency: BRIGHTNESS_MIN_HZ, Q: FILTER_Q })
  filter.connect(output)
  const synth = new Tone.Synth({
    oscillator: { type: preset.oscillator },
    envelope: {
      attack: preset.attack,
      decay: preset.decay,
      sustain: preset.sustain,
      release: preset.release,
    },
    volume: preset.volumeDb,
  }).connect(filter)
  return { synth, filter, eventIds: [], beats: 0 }
}

/** Create the band for the given instrument ids. */
export function createBand(instrumentIds: readonly string[]): Band {
  if (instrumentIds.length === 0) throw new Error('a band needs at least one instrument')
  const transport = Tone.getTransport()
  const master = new Tone.Volume(MASTER_VOLUME_DB).toDestination()
  const voices = new Map<string, Voice>(instrumentIds.map((id) => [id, createVoice(id, master)]))

  const voiceFor = (instrumentId: string): Voice => {
    const voice = voices.get(instrumentId)
    if (voice === undefined) throw new Error(`unknown instrument '${instrumentId}'`)
    return voice
  }

  /** Loop the transport over the longest loaded part. */
  const updateLoop = (): void => {
    const beats = Math.max(0, ...[...voices.values()].map((voice) => voice.beats))
    transport.loop = beats > 0
    transport.setLoopPoints(0, `${beats * transport.PPQ}i`)
  }

  const clear = (instrumentId: string): void => {
    const voice = voiceFor(instrumentId)
    voice.eventIds.forEach((id) => transport.clear(id))
    voice.eventIds = []
    voice.beats = 0
    updateLoop()
  }

  const load = (instrumentId: string, midi: Midi): void => {
    const tempo = midi.header.tempos[0]
    const track = midi.tracks[0]
    if (tempo === undefined || track === undefined) throw new Error('MIDI lacks tempo or track')
    clear(instrumentId)
    const voice = voiceFor(instrumentId)
    transport.bpm.value = tempo.bpm
    const scale = transport.PPQ / midi.header.ppq // MIDI ticks -> transport ticks
    voice.eventIds = track.notes.map((note) => {
      const frequency = Tone.Frequency(note.midi, 'midi').toFrequency()
      const duration = `${Math.round(note.durationTicks * scale)}i`
      return transport.schedule((time) => {
        voice.filter.frequency.setValueAtTime(velocityToCutoff(note.velocity), time)
        voice.synth.triggerAttackRelease(frequency, duration, time, note.velocity)
      }, `${Math.round(note.ticks * scale)}i`)
    })
    const lastTick = Math.max(0, ...track.notes.map((note) => note.ticks + note.durationTicks))
    voice.beats = Math.ceil(lastTick / midi.header.ppq) // whole beats: one per IR row
    updateLoop()
  }

  return {
    load,
    clear,
    play: async () => {
      await Tone.start()
      transport.start()
    },
    stop: () => {
      transport.stop()
      transport.position = 0
    },
    currentBeat: () => transport.ticks / transport.PPQ,
    dispose: () => {
      transport.stop()
      transport.cancel()
      voices.forEach((voice) => {
        voice.synth.dispose()
        voice.filter.dispose()
      })
      master.dispose()
    },
  }
}
