import { CHART_HEIGHT, CHART_WIDTH } from '../config'
import type { IRSeries } from '../api'

interface LevelChartProps {
  readonly ir: IRSeries
  /** Playhead position in beats; null hides the playhead. */
  readonly beat: number | null
}

/**
 * The IR `level` channel as a line: the same shape that drives pitch, so what you see is
 * what you hear. A vertical line marks the playhead.
 */
export function LevelChart({ ir, beat }: LevelChartProps) {
  const count = ir.beats.length
  if (count === 0) throw new Error('LevelChart needs at least one beat')
  const xFor = (index: number): number => (count === 1 ? 0 : (index / (count - 1)) * CHART_WIDTH)
  const points = ir.beats
    .map((b, index) => `${xFor(index).toFixed(1)},${((1 - b.level) * CHART_HEIGHT).toFixed(1)}`)
    .join(' ')
  const playheadX = beat === null ? null : xFor(Math.min(beat % count, count - 1))

  return (
    <svg
      className="level-chart"
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`${ir.source} price shape`}
    >
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.5} />
      {playheadX !== null && (
        <line x1={playheadX} x2={playheadX} y1={0} y2={CHART_HEIGHT} className="playhead" />
      )}
    </svg>
  )
}
