/**
 * The band's audio engine: one voice per instrument, all scheduled on Tone's shared Transport
 * so every instrument plays against the same clock.
 *
 * Lifecycle: create once per page with createBand(), call dispose() on unmount. Scheduled
 * event ids per instrument are replaced wholesale on load() and dropped on clear(), so they
 * never grow beyond one MIDI file's notes per instrument. setGenre() builds a second set of
 * voices and mixer, swaps them in once loaded and disposes the old set, so at most two sets
 * exist at once.
 */

import type { Midi } from '@tonejs/midi'
import * as Tone from 'tone'
import type { Instrument } from '../api'
import { GENRE_SOUNDS, MASTER_VOLUME_DB, VOICE_LOOP_BEATS, VOICE_VOLUME_DB } from '../config'
import { createMix, type Mix } from './mix'
import { createVoice, type Voice } from './voices'

/** Called on the animation frame matching each note, for visual pulses. */
export type NoteListener = (instrumentId: string, velocity: number) => void

interface Slot {
  /** Swapped by setGenre(); scheduled notes read it when they fire, so they follow the swap. */
  voice: Voice
  eventIds: number[]
  beats: number
}

/**
 * The scenario's sung track: synced to the transport from beat 0, so it follows pause, seek and
 * loop like the notes do; muted while turned off.
 */
interface Vocal {
  readonly player: Tone.Player
  readonly ready: Promise<void>
  on: boolean
}

/** Every voice plus the mixer they play into, for one genre. */
interface Kit {
  readonly mix: Mix
  readonly voices: ReadonlyMap<string, Voice>
  readonly ready: Promise<void>
}

export interface Band {
  /** Schedule a parsed MIDI file on an instrument, replacing whatever it played before. */
  load(instrumentId: string, midi: Midi): void
  /** Silence an instrument. */
  clear(instrumentId: string): void
  /**
   * Switch every instrument to a genre's sounds and mix without stopping the transport.
   * Resolves once the new sounds are playing; a newer call supersedes an older one.
   */
  setGenre(genre: string): Promise<void>
  /** Load the scenario's sung track (once per band), initially off. */
  loadVocal(url: string): void
  /** Turn the sung track on or off; on, it holds the loop at the song length. */
  setVocal(on: boolean): void
  /** Start, or resume from where pause() or seek() left the playhead. */
  play(): Promise<void>
  /** Stop playback but keep the playhead where it is. */
  pause(): void
  /** Stop playback and rewind to beat 0. */
  stop(): void
  /** Move the playhead to a beat in [0, loopBeats()]; playback, if running, continues from there. */
  seek(beat: number): void
  /** Length of one beat in seconds at the current tempo. */
  secondsPerBeat(): number
  /** Current playhead position in beats (fractional, not wrapped). */
  currentBeat(): number
  /** Length of the loop in beats (0 when nothing is loaded). */
  loopBeats(): number
  dispose(): void
}

/** List the instruments a genre has no sound for; empty means the genre is complete. */
export function missingSounds(genre: string, instruments: readonly Instrument[]): string[] {
  const sounds = GENRE_SOUNDS[genre]
  if (sounds === undefined) return instruments.map((instrument) => instrument.id)
  return instruments.filter((instrument) => sounds[instrument.id] === undefined).map((i) => i.id)
}

/** Build every voice and the mixer for one genre, failing loudly on any missing preset. */
function createKit(genre: string, instruments: readonly Instrument[], context: AudioContext): Kit {
  const missing = missingSounds(genre, instruments)
  if (missing.length > 0) throw new Error(`genre '${genre}' has no sound for: ${missing.join(', ')}`)
  const sounds = GENRE_SOUNDS[genre] ?? {}
  const mix = createMix(context, instruments.map((instrument) => instrument.id), genre, MASTER_VOLUME_DB)
  const voices = new Map<string, Voice>()
  for (const instrument of instruments) {
    const preset = sounds[instrument.id]
    if (preset === undefined) throw new Error(`no sound preset for instrument '${instrument.id}'`)
    voices.set(instrument.id, createVoice(preset, instrument.root_midi, context, mix.input(instrument.id)))
  }
  const ready = Promise.all([mix.ready, ...[...voices.values()].map((voice) => voice.ready)])
  return { mix, voices, ready: ready.then(() => undefined) }
}

/** Dispose every voice and the mixer of a kit. */
function disposeKit(kit: Kit): void {
  kit.voices.forEach((voice) => voice.dispose())
  kit.mix.dispose()
}

/**
 * Create the band for the given instruments in a genre. Tone runs on a native AudioContext that
 * the smplr voices share, so Transport callback times are directly usable as sample start times.
 */
export function createBand(
  instruments: readonly Instrument[],
  genre: string,
  onNote: NoteListener,
): Band {
  if (instruments.length === 0) throw new Error('a band needs at least one instrument')
  const context = new AudioContext()
  const toneContext = new Tone.Context(context)
  Tone.setContext(toneContext)
  const transport = Tone.getTransport()
  const draw = Tone.getDraw()
  let kit = createKit(genre, instruments, context)
  let genreRequest = 0 // the newest setGenre() call; older ones discard their kit
  let vocal: Vocal | null = null // at most one per band, created by loadVocal()
  const slots = new Map<string, Slot>(
    instruments.map((instrument) => {
      const voice = kit.voices.get(instrument.id)
      if (voice === undefined) throw new Error(`no voice for instrument '${instrument.id}'`)
      return [instrument.id, { voice, eventIds: [], beats: 0 }]
    }),
  )
  // Report a failed load straight away; play() still rejects with it so the UI shows it too.
  void kit.ready.catch((reason: unknown) => console.error('instrument samples failed to load', reason))

  const slotFor = (instrumentId: string): Slot => {
    const slot = slots.get(instrumentId)
    if (slot === undefined) throw new Error(`unknown instrument '${instrumentId}'`)
    return slot
  }

  const vocalBeats = (): number => (vocal?.on === true ? VOICE_LOOP_BEATS : 0)
  const loopBeats = (): number =>
    Math.max(vocalBeats(), ...[...slots.values()].map((slot) => slot.beats))

  /** Loop the transport over the longest loaded part. */
  const updateLoop = (): void => {
    const beats = loopBeats()
    transport.loop = beats > 0
    if (beats > 0) transport.setLoopPoints(0, `${beats * transport.PPQ}i`)
  }

  const clear = (instrumentId: string): void => {
    const slot = slotFor(instrumentId)
    slot.eventIds.forEach((id) => transport.clear(id))
    slot.voice.silence()
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
    transport.bpm.value = tempo.bpm
    const scale = transport.PPQ / midi.header.ppq // MIDI ticks -> transport ticks
    slot.eventIds = track.notes.map((note) => {
      const durationTicks = Math.round(note.durationTicks * scale)
      return transport.schedule((time) => {
        const durationSeconds = Tone.Ticks(durationTicks).toSeconds()
        slot.voice.trigger(note.midi, durationSeconds, time, note.velocity)
        draw.schedule(() => onNote(instrumentId, note.velocity), time)
      }, `${Math.round(note.ticks * scale)}i`)
    })
    const lastTick = Math.max(0, ...track.notes.map((note) => note.ticks + note.durationTicks))
    // The backend ends every part at the song length; fall back to the last note for other files.
    const endTick = track.endOfTrackTicks ?? lastTick
    slot.beats = Math.ceil(Math.max(endTick, lastTick) / midi.header.ppq)
    updateLoop()
  }

  /** Build the new genre's kit, keep the old one playing until it loads, then swap. */
  const setGenre = async (next: string): Promise<void> => {
    genreRequest += 1
    const request = genreRequest
    const incoming = createKit(next, instruments, context)
    await incoming.ready
    if (request !== genreRequest) {
      disposeKit(incoming) // a newer genre was chosen while this one loaded
      return
    }
    const outgoing = kit
    kit = incoming
    slots.forEach((slot, instrumentId) => {
      const voice = incoming.voices.get(instrumentId)
      if (voice === undefined) throw new Error(`no voice for instrument '${instrumentId}'`)
      slot.voice = voice
    })
    disposeKit(outgoing)
  }

  /** Schedule the sung track at beat 0 of every loop; it plays muted until setVocal(true). */
  const loadVocal = (url: string): void => {
    if (url === '') throw new Error('vocal url is required')
    if (vocal !== null) throw new Error('this band already has a vocal')
    const player = new Tone.Player().toDestination()
    player.volume.value = VOICE_VOLUME_DB
    player.mute = true
    // Sync only once loaded, so the transport never starts an empty buffer. If the song is
    // already playing, Tone joins the track at the current offset.
    const ready = player.load(url).then(() => {
      player.sync().start(0)
    })
    void ready.catch((reason: unknown) => console.error('vocal failed to load', reason))
    vocal = { player, ready, on: false }
  }

  const setVocal = (on: boolean): void => {
    if (vocal === null) throw new Error('no vocal loaded')
    vocal.on = on
    vocal.player.mute = !on
    updateLoop()
  }

  const silenceAll = (): void => slots.forEach((slot) => slot.voice.silence())

  /** Jump the transport to a beat, cutting notes that were ringing at the old position. */
  const seek = (beat: number): void => {
    const beats = loopBeats()
    if (beats === 0) throw new Error('nothing loaded to seek in')
    if (!(beat >= 0 && beat <= beats)) throw new Error(`seek beat ${beat} outside [0, ${beats}]`)
    // Seeking onto the loop end would wrap straight to 0; stop one tick short instead.
    const ticks = Math.min(Math.round(beat * transport.PPQ), beats * transport.PPQ - 1)
    silenceAll()
    transport.ticks = ticks // Tone restarts synced sources (the vocal) at the new offset
  }

  return {
    load,
    clear,
    setGenre,
    loadVocal,
    setVocal,
    play: async () => {
      await Tone.start()
      await kit.ready // samples normally finish loading long before the first click
      if (vocal?.on === true) await vocal.ready
      transport.start()
    },
    pause: () => {
      transport.pause() // the synced vocal pauses with it
      silenceAll()
    },
    stop: () => {
      transport.stop() // the synced vocal stops with it; stopping it directly would unschedule it
      transport.position = 0
      silenceAll()
    },
    seek,
    secondsPerBeat: () => 60 / transport.bpm.value,
    currentBeat: () => transport.ticks / transport.PPQ,
    loopBeats,
    dispose: () => {
      genreRequest += 1 // any setGenre() still loading discards its kit
      transport.stop()
      transport.cancel()
      disposeKit(kit)
      vocal?.player.dispose()
      toneContext.dispose() // also closes the AudioContext
    },
  }
}
