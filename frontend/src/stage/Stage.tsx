import type { Dataset, Instrument } from '../api'
import type { JSX } from 'react'
import { BassArt, GuitarArt, HihatArt, KickArt, PadArt, SnareArt, SynthArt } from './art'
import { Defs } from './Defs'
import { PLACEMENTS, POOLS, STAGE_HEIGHT, STAGE_WIDTH } from './layout'
import { Piece } from './Piece'
import { PlayButton } from './PlayButton'
import { VoicePiece } from './VoicePiece'

/** Art component per backend instrument id. */
const ART: Readonly<Record<string, () => JSX.Element>> = {
  kick: KickArt,
  snare: SnareArt,
  hihat: HihatArt,
  synth: SynthArt,
  bass: BassArt,
  pad: PadArt,
  guitar: GuitarArt,
}

interface StageProps {
  readonly instruments: readonly Instrument[]
  readonly datasets: readonly Dataset[]
  /** instrument id -> dataset id */
  readonly assignments: Readonly<Record<string, string>>
  readonly lit: Readonly<Record<string, boolean>>
  readonly playing: boolean
  readonly progress: number
  readonly onAssign: (instrumentId: string, datasetId: string) => void
  readonly onClear: (instrumentId: string) => void
  readonly onTogglePlay: () => void
  /** The scenario's sung track and whether it is on, or null when the scenario has none. */
  readonly voice: { readonly on: boolean; readonly title: string } | null
  readonly onToggleVoice: () => void
}

/** The whole stage: room, light pools, play button and every band member. */
export function Stage(props: StageProps) {
  const { instruments, datasets, assignments, lit, playing, progress, voice } = props
  const tickerFor = (instrumentId: string): string | null => {
    const datasetId = assignments[instrumentId]
    return datasets.find((d) => d.id === datasetId)?.ticker ?? null
  }

  return (
    <svg className="stage" viewBox={`0 0 ${STAGE_WIDTH} ${STAGE_HEIGHT}`} role="group" aria-label="Stage">
      <Defs />
      {POOLS.map((pool) => (
        <ellipse key={pool.cx} {...pool} fill="url(#mb-pool)" />
      ))}
      <PlayButton
        playing={playing}
        disabled={Object.keys(assignments).length === 0 && voice?.on !== true}
        progress={progress}
        onToggle={props.onTogglePlay}
      />
      {instruments.map((instrument) => {
        const placement = PLACEMENTS[instrument.id]
        const Art = ART[instrument.id]
        if (placement === undefined || Art === undefined) return null // not part of this stage
        return (
          <Piece
            key={instrument.id}
            instrumentId={instrument.id}
            placement={placement}
            ticker={tickerFor(instrument.id)}
            lit={lit[instrument.id] === true}
            onAssign={props.onAssign}
            onClear={props.onClear}
          >
            <Art />
          </Piece>
        )
      })}
      {voice !== null && <VoicePiece on={voice.on} title={voice.title} onToggle={props.onToggleVoice} />}
    </svg>
  )
}
