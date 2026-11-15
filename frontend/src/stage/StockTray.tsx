import type { DragEvent } from 'react'
import type { Dataset, IRSeries } from '../api'
import { DRAG_MIME, SPARK_HEIGHT, SPARK_WIDTH } from '../config'

interface StockTrayProps {
  readonly datasets: readonly Dataset[]
  readonly irs: Readonly<Record<string, IRSeries>>
  readonly beat: number | null
}

function sparkPoints(ir: IRSeries): { readonly x: number; readonly y: number }[] {
  const count = ir.beats.length
  if (count < 2) return []
  return ir.beats.map((b,index) => ({
    x: (index/(count-1))*SPARK_WIDTH, y: (1-b.level)*SPARK_HEIGHT,
  }))
}

function StockBox(props: { readonly dataset: Dataset; readonly ir: IRSeries | undefined; readonly beat: number | null }) {
  const { dataset,ir,beat } = props
  const points = ir === undefined ? [] : sparkPoints(ir)
  const dot = beat === null || points.length === 0 ? undefined : points[Math.floor(beat)%points.length]
  const handleDragStart = (event: DragEvent<HTMLDivElement>): void => {
    event.dataTransfer.setData(DRAG_MIME,dataset.id)
    event.dataTransfer.effectAllowed = 'copy'
  }
  return <div className="stock" draggable onDragStart={handleDragStart} title={dataset.name}>
    <span className="stock__bar" />
    <span className="stock__ticker">{dataset.ticker}</span>
    <svg className="stock__spark" viewBox={`-4 -4 ${SPARK_WIDTH+8} ${SPARK_HEIGHT+8}`} aria-hidden="true">
      <polyline points={points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')} />
      {dot !== undefined && <circle cx={dot.x} cy={dot.y} r={3.5} />}
    </svg>
  </div>
}

export function StockTray({ datasets,irs,beat }: StockTrayProps) {
  return <section className="tray" aria-label="Stocks and index to drag onto instruments">
    {datasets.length === 0 ? <p className="tray__empty" role="status">
      No playable assets for this period yet. DATA progress means candles are being created;
      assets become playable after their MIDI is rendered. Click Refresh generated data above,
      then choose a period with available assets. If generation has finished, expand Availability
      and generation errors to see why files were not loaded. Do not restart generation just for this message.
    </p> : datasets.map(dataset => <StockBox key={dataset.id} dataset={dataset} ir={irs[dataset.id]} beat={beat} />)}
  </section>
}
