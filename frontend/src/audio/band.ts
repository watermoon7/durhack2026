/**
 * The band's audio engine: one voice per instrument, all scheduled on Tone's shared Transport
 * so every instrument plays against the same clock.
 *
 * Lifecycle: create once per page with createBand(), call dispose() on unmount. Scheduled
 * event ids per instrument are replaced wholesale on load() and dropped on clear(), so they
 * never grow beyond one MIDI file's notes per instrument.
 */

import type { Midi } from '@tonejs/midi'
import * as Tone from 'tone'
import type { Instrument } from '../api'
import { MASTER_VOLUME_DB, SOUND_PRESETS } from '../config'
import { createVoice, type Voice } from './voices'

/** Called on the animation frame matching each note, for visual pulses. */
export type NoteListener = (instrumentId: string, velocity: number) => void

interface Slot {
  voice: Voice | null
  readonly instrument: Instrument
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
  /** Current playhead position in beats (fractional, not wrapped). */
  currentBeat(): number
  /** Length of the loop in beats (0 when nothing is loaded). */
  loopBeats(): number
  dispose(): void
}

/**
 * Create the band for the given instruments. Tone runs on a native AudioContext that the smplr
 * voices share, so Transport callback times are directly usable as sample start times.
 */
export function createBand(instruments: readonly Instrument[], onNote: NoteListener): Band {
  if (instruments.length === 0) throw new Error('a band needs at least one instrument')
  const context = new AudioContext()
  const toneContext = new Tone.Context(context)
  Tone.setContext(toneContext)
  const transport = Tone.getTransport()
  const draw = Tone.getDraw()
  const master = new Tone.Volume(MASTER_VOLUME_DB).toDestination()
  const bus = context.createGain() // smplr voices -> bus -> Tone master
  Tone.connect(bus, master)
  const slots = new Map<string, Slot>(
    instruments.map((instrument) => [instrument.id, { instrument, voice: null, eventIds: [], beats: 0 }]),
  )
  let disposed = false
  let playSequence = 0

  const slotFor = (instrumentId: string): Slot => {
    const slot = slots.get(instrumentId)
    if (slot === undefined) throw new Error(`unknown instrument '${instrumentId}'`)
    return slot
  }

  const loopBeats = (): number => Math.max(0, ...[...slots.values()].map((slot) => slot.beats))

  /** Loop the transport over the longest loaded part. */
  const updateLoop = (): void => {
    const beats = loopBeats()
    transport.loop = beats > 0
    if (beats > 0) transport.setLoopPoints(0, `${beats * transport.PPQ}i`)
  }

  const clear = (instrumentId: string): void => {
    const slot = slotFor(instrumentId)
    slot.eventIds.forEach((id) => transport.clear(id))
    slot.voice?.silence()
    slot.eventIds = []
    slot.beats = 0
    updateLoop()
  }

  const load = (instrumentId: string, midi: Midi): void => {
    const tempo = midi.header.tempos[0]
    const track = midi.tracks[0]
    if (tempo === undefined || track === undefined) throw new Error('MIDI lacks tempo or track')
    clear(instrumentId)
    const slot = slotFor(instrumentId)
    if (slot.voice === null) {
      const preset = SOUND_PRESETS[instrumentId]
      if (!preset) throw new Error(`no sound preset for ${instrumentId}`)
      slot.voice = createVoice(preset, slot.instrument.root_midi, context, bus, slot.instrument.octaves)
      void slot.voice.ready.catch((reason: unknown) => console.error('instrument samples failed to load', reason))
    }
    const voice = slot.voice
    transport.bpm.value = tempo.bpm
    const scale = transport.PPQ / midi.header.ppq // MIDI ticks -> transport ticks
    slot.eventIds = track.notes.map((note) => {
      const durationTicks = Math.round(note.durationTicks * scale)
      return transport.schedule((time) => {
        const durationSeconds = Tone.Ticks(durationTicks).toSeconds()
        voice.trigger(note.midi, durationSeconds, time, note.velocity)
        draw.schedule(() => onNote(instrumentId, note.velocity), time)
      }, `${Math.round(note.ticks * scale)}i`)
    })
    const lastTick = Math.max(0, ...track.notes.map((note) => note.ticks + note.durationTicks))
    slot.beats = Math.ceil(lastTick / midi.header.ppq) // whole beats: one per IR row
    updateLoop()
  }

  return {
    load,
    clear,
    play: async () => {
      const sequence = ++playSequence
      await Tone.start()
      await Promise.all([...slots.values()].filter((slot) => slot.beats > 0).map((slot) => slot.voice?.ready))
      if (disposed || sequence !== playSequence) return
      transport.start()
    },
    stop: () => {
      playSequence++
      transport.stop()
      transport.position = 0
      slots.forEach((slot) => slot.voice?.silence())
    },
    currentBeat: () => transport.ticks / transport.PPQ,
    loopBeats,
    dispose: () => {
      disposed = true
      playSequence++
      transport.stop()
      transport.cancel()
      slots.forEach((slot) => slot.voice?.dispose())
      bus.disconnect()
      master.dispose()
      toneContext.dispose() // also closes the AudioContext
    },
  }
}
