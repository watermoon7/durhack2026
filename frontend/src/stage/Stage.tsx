import type { Dataset, Instrument } from '../api'
import { BassArt, HihatArt, KickArt, SnareArt, SynthArt } from './art'
import { Piece } from './Piece'
import { Defs } from './Defs'
import { PlayButton } from './PlayButton'
import type { PiecePlacement } from './layout'
import './historyStage.css'

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

function GuitarArt({ electric }: { readonly electric: boolean }) {
  return <g>
    <path d="M67 76 L65 22 Q80 1 96 22 L93 76 Z" fill="#d9b77d" />
    <rect x={70} y={72} width={22} height={188} fill="#472e20" />
    {[100,122,144,166,188,210,232].map(y => <path key={y} d={`M70 ${y} H92`} stroke="#ccc" />)}
    <path d="M80 240 C48 216 20 245 35 282 Q52 306 33 337 C4 376 37 418 80 402 C123 418 156 376 127 337 Q108 306 125 282 C140 245 112 216 80 240 Z"
      fill={electric ? '#a12e3a' : '#b77a3c'} stroke="#593720" strokeWidth={3} />
    {electric ? <rect x={62} y={292} width={38} height={12} fill="#eee" /> : <circle cx={81} cy={307} r={21} fill="#38251b" stroke="#e1c48b" strokeWidth={3} />}
    <rect x={59} y={365} width={43} height={9} fill="#38251b" />
    {[73,76,79,82,85,88].map(x => <path key={x} d={`M${x} 22 V370`} stroke="#ddd" strokeWidth={.8} />)}
    {[30,48,66].map(y => <g key={y} fill="#c9ced4"><circle cx={60} cy={y} r={4} /><circle cx={102} cy={y} r={4} /></g>)}
  </g>
}

export function Stage(p: Props) {
  return <svg className="stage" viewBox="0 0 1200 620" role="group" aria-label="Illustrated seven-instrument stage">
    <Defs />
    <PlayButton playing={p.playing} disabled={Object.keys(p.assignments).length===0} progress={p.progress} onToggle={p.onTogglePlay} />
    {p.instruments.map((i,n) => {
      const x = n<4 ? 65+n*285 : 205+(n-4)*285
      const y = n<4 ? 150 : 380
      const guitar = i.id.includes('guitar')
      const box = i.id==='drums' ? '70 125 435 285' : i.id==='bass' ? '980 50 160 425' : guitar ? '0 0 160 425' : '400 420 410 150'
      const placement: PiecePlacement = {outline:{kind:'rect',x,y,width:220,height:150,rx:18},tag:{x:x+110,y:y+178}}
      return <g key={i.id}>
        <text x={x+110} y={y-12} textAnchor="middle" fill="currentColor" fontSize={18}>{i.name}</text>
        <Piece instrumentId={i.id} placement={placement}
          ticker={p.datasets.find(d => d.id===p.assignments[i.id])?.ticker ?? null}
          lit={p.lit[i.id]===true} onAssign={p.onAssign} onClear={p.onClear}>
          <svg x={x+8} y={y+4} width={204} height={142} viewBox={box} preserveAspectRatio="xMidYMid meet">
            {i.id==='drums' ? <><KickArt /><SnareArt /><HihatArt /></> : i.id==='bass' ? <BassArt /> : guitar ? <GuitarArt electric={i.id==='guitar_counter'} /> : <SynthArt />}
          </svg>
        </Piece>
      </g>
    })}
  </svg>
}
