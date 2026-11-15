/**
 * The band's mixer: one channel per instrument (high-pass, 3-band EQ, reverb send) feeding a
 * compressed, limited master. Voices play into `input(id)`; everything after it is Tone nodes.
 *
 * Lifecycle: create once per band, after Tone.setContext(), and dispose() with the band. The
 * node list is fixed at creation (at most three nodes per instrument) and never grows.
 */

import * as Tone from 'tone'
import { COMPRESSOR, LIMITER_DB, MIX_PRESETS, REVERB_DECAY_S, type MixPreset } from '../config'

export interface Mix {
  /** Resolves once the reverb's impulse response has been generated. */
  readonly ready: Promise<void>
  /** The node an instrument's voice plays into. */
  input(instrumentId: string): AudioNode
  dispose(): void
}

interface Channel {
  readonly input: GainNode
  readonly nodes: readonly Tone.ToneAudioNode[]
}

/** Look up an instrument's mix preset, failing loudly so no instrument plays silently dry. */
function presetFor(instrumentId: string): MixPreset {
  const preset = MIX_PRESETS[instrumentId]
  if (preset === undefined) throw new Error(`no mix preset for instrument '${instrumentId}'`)
  if (!(preset.reverbSend >= 0 && preset.reverbSend <= 1)) {
    throw new Error(`${instrumentId}: reverbSend ${preset.reverbSend} outside [0, 1]`)
  }
  if (!(preset.highpassHz >= 0)) throw new Error(`${instrumentId}: highpassHz must be >= 0`)
  return preset
}

/** Build one channel: input -> (high-pass) -> EQ -> master bus, with a send from the EQ to reverb. */
function createChannel(
  context: AudioContext,
  preset: MixPreset,
  masterBus: Tone.Gain,
  reverb: Tone.Reverb,
): Channel {
  const input = context.createGain()
  const eq = new Tone.EQ3(preset.eqDb)
  const send = new Tone.Gain(preset.reverbSend)
  const nodes: Tone.ToneAudioNode[] = [eq, send]
  if (preset.highpassHz > 0) {
    const highpass = new Tone.Filter({ type: 'highpass', frequency: preset.highpassHz })
    Tone.connect(input, highpass)
    highpass.connect(eq)
    nodes.push(highpass)
  } else {
    Tone.connect(input, eq)
  }
  eq.connect(masterBus)
  eq.connect(send)
  send.connect(reverb)
  return { input, nodes }
}

/** Create the mixer for the given instruments. Must run after Tone.setContext(). */
export function createMix(
  context: AudioContext,
  instrumentIds: readonly string[],
  masterVolumeDb: number,
): Mix {
  if (instrumentIds.length === 0) throw new Error('a mix needs at least one instrument')
  if (new Set(instrumentIds).size !== instrumentIds.length) throw new Error('duplicate instrument id')
  if (!Number.isFinite(masterVolumeDb)) throw new Error(`invalid master volume ${masterVolumeDb}`)
  const presets = instrumentIds.map((id) => [id, presetFor(id)] as const) // validate before building

  const masterBus = new Tone.Gain(1)
  const reverb = new Tone.Reverb({ decay: REVERB_DECAY_S, wet: 1 })
  const compressor = new Tone.Compressor({
    threshold: COMPRESSOR.thresholdDb,
    ratio: COMPRESSOR.ratio,
  })
  const limiter = new Tone.Limiter(LIMITER_DB)
  const volume = new Tone.Volume(masterVolumeDb).toDestination()
  reverb.connect(masterBus)
  masterBus.chain(compressor, limiter, volume)
  const channels = new Map<string, Channel>(
    presets.map(([id, preset]) => [id, createChannel(context, preset, masterBus, reverb)]),
  )

  return {
    ready: reverb.ready,
    input: (instrumentId) => {
      const channel = channels.get(instrumentId)
      if (channel === undefined) throw new Error(`no mix channel for instrument '${instrumentId}'`)
      return channel.input
    },
    dispose: () => {
      channels.forEach((channel) => {
        channel.input.disconnect()
        channel.nodes.forEach((node) => node.dispose())
      })
      const master: readonly Tone.ToneAudioNode[] = [masterBus, reverb, compressor, limiter, volume]
      master.forEach((node) => node.dispose())
    },
  }
}
