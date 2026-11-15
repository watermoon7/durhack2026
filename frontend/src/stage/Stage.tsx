import type { Dataset, Instrument } from '../api'
import { Piece } from './Piece'
import { Defs } from './Defs'
import { PlayButton } from './PlayButton'
import type { PiecePlacement } from './layout'
interface Props {
  readonly instruments: readonly Instrument[]
  readonly datasets: readonly Dataset[]
  readonly assignments: Readonly<Record<string, string>>
  readonly lit: Readonly<Record<string, boolean>>
  readonly playing: boolean
  readonly progress: number
  readonly onAssign: (instrument: string, dataset: string) => void
  readonly onClear: (instrument: string) => void
  readonly onTogglePlay: () => void
}
export function Stage(p: Props) {
  return <svg className="stage" viewBox="0 0 1200 620" role="group" aria-label="Seven instrument drop zones">
    <Defs />
    <PlayButton playing={p.playing} disabled={Object.keys(p.assignments).length === 0} progress={p.progress} onToggle={p.onTogglePlay} />
    {p.instruments.map((i, n) => {
      const x = n < 4 ? 65 + n * 285 : 205 + (n - 4) * 285
      const y = n < 4 ? 150 : 380
      const placement: PiecePlacement = { outline: { kind: 'rect', x, y, width: 220, height: 150, rx: 18 }, tag: { x: x + 110, y: y + 178 } }
      return <Piece key={i.id} instrumentId={i.id} placement={placement}
        ticker={p.datasets.find(d => d.id === p.assignments[i.id])?.ticker ?? null}
        lit={p.lit[i.id] === true} onAssign={p.onAssign} onClear={p.onClear}>
        <rect x={x+12} y={y+12} width={196} height={126} rx={14} fill="#26273e" stroke="#aaa" />
        <text x={x+110} y={y+65} textAnchor="middle" fill="#fff" fontSize={19}>{i.name}</text>
        <text x={x+110} y={y+100} textAnchor="middle" fill="#ccc" fontSize={14}>Drop stock or index here</text>
      </Piece>
    })}
  </svg>
}
