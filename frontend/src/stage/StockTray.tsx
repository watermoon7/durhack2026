import type { DragEvent } from 'react'
import type { Dataset, IRSeries } from '../api'
import { DRAG_MIME, SPARK_HEIGHT, SPARK_WIDTH } from '../config'

interface StockTrayProps {
  readonly datasets: readonly Dataset[]
  readonly irs: Readonly<Record<string, IRSeries>>
  /** Playhead in beats, or null when stopped. */
  readonly beat: number | null
}

/** Points of the IR level line, scaled into the sparkline box. */
function sparkPoints(ir: IRSeries): { readonly x: number; readonly y: number }[] {
  const count = ir.beats.length
  if (count < 2) throw new Error('sparkline needs at least two beats')
  return ir.beats.map((b, index) => ({
    x: (index / (count - 1)) * SPARK_WIDTH,
    y: (1 - b.level) * SPARK_HEIGHT,
  }))
}

/** One draggable stock: ticker plus the price shape that drives its pitch. */
function StockBox(props: { readonly dataset: Dataset; readonly ir: IRSeries | undefined; readonly beat: number | null }) {
  const { dataset, ir, beat } = props
  const points = ir === undefined ? [] : sparkPoints(ir)
  const dot = beat === null || points.length === 0 ? undefined : points[Math.floor(beat) % points.length]

  const handleDragStart = (event: DragEvent<HTMLDivElement>): void => {
    event.dataTransfer.setData(DRAG_MIME, dataset.id)
    event.dataTransfer.effectAllowed = 'copy'
  }

  return (
    <div className="stock" draggable onDragStart={handleDragStart} title={dataset.name}>
      <span className="stock__bar" />
      <span className="stock__ticker">{dataset.ticker}</span>
      <svg
        className="stock__spark"
        viewBox={`-4 -4 ${SPARK_WIDTH + 8} ${SPARK_HEIGHT + 8}`}
        aria-hidden="true"
      >
        <polyline points={points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')} />
        {dot !== undefined && <circle cx={dot.x} cy={dot.y} r={3.5} />}
      </svg>
    </div>
  )
}

/** The bottom tray of draggable stocks. */
export function StockTray({ datasets, irs, beat }: StockTrayProps) {
  return (
    <section className="tray" aria-label="Stocks">
      {datasets.map((dataset) => (
        <StockBox key={dataset.id} dataset={dataset} ir={irs[dataset.id]} beat={beat} />
      ))}
    </section>
  )
}
