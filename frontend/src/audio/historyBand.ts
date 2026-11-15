/** Historical playback: seven native voices, one asset/instrument MIDI per slot. */
import type { Midi } from '@tonejs/midi'
import * as Tone from 'tone'
import type { Instrument } from '../api'
import type { Band, NoteListener } from './band'
import { normalisePlayableMidi } from './playableMidi.js'

export function createBand(instruments: readonly Instrument[], onNote: NoteListener): Band {
  const context = new AudioContext()
  const toneContext = new Tone.Context(context)
  Tone.setContext(toneContext)
  const transport = Tone.getTransport()
  const draw = Tone.getDraw()
  const compressor = context.createDynamicsCompressor()
  compressor.threshold.value = -8
  compressor.ratio.value = 8
  compressor.connect(context.destination)
  const noise = context.createBuffer(1, Math.ceil(context.sampleRate * .3), context.sampleRate)
  const values = noise.getChannelData(0)
  for (let i = 0; i < values.length; i += 1) values[i] = Math.random() * 2 - 1
  const slots = new Map(instruments.map(i => [i.id, { events: [] as number[], stops: new Set<() => void>(), beats: 0 }]))
  const slotFor = (id: string) => {
    const slot = slots.get(id)
    if (slot === undefined) throw new Error(`Unknown instrument: ${id}`)
    return slot
  }
  const loopBeats = (): number => Math.max(0, ...[...slots.values()].map(s => s.beats))
  const updateLoop = (): void => {
    const beats = loopBeats()
    transport.loop = beats > 0
    if (beats > 0) transport.setLoopPoints(0, `${beats * transport.PPQ}i`)
  }
  const silence = (id: string): void => { slotFor(id).stops.forEach(stop => stop()) }
  const clear = (id: string): void => {
    const slot = slotFor(id)
    slot.events.forEach(event => transport.clear(event))
    silence(id)
    slot.events = []
    slot.beats = 0
    updateLoop()
  }
  const trigger = (id: string, midi: number, duration: number, time: number, velocity: number): void => {
    const slot = slotFor(id)
    const now = Math.max(time, context.currentTime)
    const drum = id === 'drums'
    const kick = drum && midi === 36
    const decay = drum ? (kick ? .2 : midi === 38 ? .15 : .06) : id.includes('guitar') ? Math.min(.7, duration) : duration
    const envelope = context.createGain()
    const filter = context.createBiquadFilter()
    const pan = context.createStereoPanner()
    pan.pan.value = id.includes('counter') ? .35 : id === 'guitar' ? -.35 : id === 'synth_lead' ? -.15 : 0
    let source: AudioScheduledSourceNode
    if (drum && !kick) {
      const buffer = context.createBufferSource()
      buffer.buffer = noise
      source = buffer
      filter.type = 'highpass'
      filter.frequency.value = midi === 38 ? 1400 : 6500
    } else {
      const oscillator = context.createOscillator()
      oscillator.type = id === 'bass' ? 'sawtooth' : id === 'synth_counter' || kick ? 'sine' : 'triangle'
      oscillator.frequency.setValueAtTime(kick ? 140 : 440 * 2 ** ((midi - 69) / 12), now)
      if (kick) oscillator.frequency.exponentialRampToValueAtTime(42, now + .16)
      filter.frequency.value = id === 'bass' ? 650 : id === 'synth_pad' ? 1400 : 6500
      source = oscillator
    }
    const attack = id === 'synth_pad' ? .08 : .005
    envelope.gain.setValueAtTime(.0001, now)
    envelope.gain.exponentialRampToValueAtTime(Math.max(.0002, Math.min(1, velocity) * (drum ? .3 : .16)), now + attack)
    envelope.gain.exponentialRampToValueAtTime(.0001, now + Math.max(attack + .02, decay))
    source.connect(filter).connect(envelope).connect(pan).connect(compressor)
    const stop = (): void => { try { source.stop() } catch { /* already stopped */ } }
    slot.stops.add(stop)
    source.onended = () => { slot.stops.delete(stop); source.disconnect(); filter.disconnect(); envelope.disconnect(); pan.disconnect() }
    source.start(now)
    source.stop(now + Math.max(attack + .03, decay) + .02)
  }
  const load = (id: string, midi: Midi): void => {
    const track = normalisePlayableMidi(midi).tracks[0]
    if (track === undefined) throw new Error('No playable notes returned')
    clear(id)
    const slot = slotFor(id)
    transport.bpm.value = 120
    const scale = transport.PPQ / midi.header.ppq
    slot.events = track.notes.map(note => transport.schedule(time => {
      trigger(id, note.midi, Tone.Ticks(Math.round(note.durationTicks * scale)).toSeconds(), time, note.velocity)
      draw.schedule(() => onNote(id, note.velocity), time)
    }, `${Math.round(note.ticks * scale)}i`))
    slot.beats = 240
    updateLoop()
  }
  return {
    load, clear, loopBeats, currentBeat: () => transport.ticks / transport.PPQ,
    play: async () => { await Tone.start(); await context.resume(); transport.start() },
    stop: () => { transport.stop(); transport.position = 0; instruments.forEach(i => silence(i.id)) },
    dispose: () => {
      transport.stop(); transport.cancel(); instruments.forEach(i => silence(i.id))
      compressor.disconnect(); toneContext.dispose()
    },
  }
}
