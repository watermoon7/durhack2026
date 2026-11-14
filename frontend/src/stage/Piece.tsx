import { useState, type DragEvent, type ReactNode } from 'react'
import { DRAG_MIME } from '../config'
import type { Outline, PiecePlacement } from './layout'

interface PieceProps {
  readonly instrumentId: string
  readonly placement: PiecePlacement
  /** Ticker of the stock this piece plays, or null when empty. */
  readonly ticker: string | null
  /** True for a moment after the piece plays a note. */
  readonly lit: boolean
  readonly onAssign: (instrumentId: string, datasetId: string) => void
  readonly onClear: (instrumentId: string) => void
  readonly children: ReactNode
}

/** Pill width in viewBox units for a ticker of this length. */
const TAG_CHAR_WIDTH = 12
const TAG_PADDING = 30
const TAG_HEIGHT = 28

/** Render an outline as an SVG shape with the given class. */
function OutlineShape({ outline, className }: { readonly outline: Outline; readonly className: string }) {
  if (outline.kind === 'circle') {
    return <circle className={className} cx={outline.cx} cy={outline.cy} r={outline.r} />
  }
  return (
    <rect
      className={className}
      x={outline.x}
      y={outline.y}
      width={outline.width}
      height={outline.height}
      rx={outline.rx}
    />
  )
}

/** The ticker pill on a filled piece; clicking it empties the piece. */
function Tag(props: { readonly x: number; readonly y: number; readonly ticker: string; readonly onClear: () => void }) {
  const { x, y, ticker, onClear } = props
  if (ticker === '') throw new Error('Tag needs a ticker')
  const width = ticker.length * TAG_CHAR_WIDTH + TAG_PADDING
  return (
    <g
      className="tag"
      role="button"
      aria-label={`Remove ${ticker}`}
      tabIndex={0}
      onClick={onClear}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') onClear()
      }}
    >
      <rect x={x - width / 2} y={y - TAG_HEIGHT / 2} width={width} height={TAG_HEIGHT} rx={TAG_HEIGHT / 2} />
      <text x={x} y={y} dominantBaseline="central" textAnchor="middle">
        {ticker}
      </text>
    </g>
  )
}

/** A band member on stage: its art, a drop area for stocks, and the filled/lit states. */
export function Piece(props: PieceProps) {
  const { instrumentId, placement, ticker, lit, onAssign, onClear, children } = props
  const [hovering, setHovering] = useState(false)

  const handleDragOver = (event: DragEvent<SVGElement>): void => {
    if (!event.dataTransfer.types.includes(DRAG_MIME)) return // not a stock: ignore
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    setHovering(true)
  }

  const handleDrop = (event: DragEvent<SVGElement>): void => {
    setHovering(false)
    const datasetId = event.dataTransfer.getData(DRAG_MIME)
    if (datasetId === '') return
    event.preventDefault()
    onAssign(instrumentId, datasetId)
  }

  const state = [
    'piece',
    hovering ? 'piece--hover' : '',
    ticker !== null ? 'piece--filled' : '',
    lit ? 'piece--lit' : '',
  ].join(' ')

  return (
    <g className={state}>
      <g className="piece__art">{children}</g>
      <OutlineShape outline={placement.outline} className="piece__ring" />
      <g
        onDragOver={handleDragOver}
        onDragLeave={() => setHovering(false)}
        onDrop={handleDrop}
      >
        <OutlineShape outline={placement.outline} className="piece__hit" />
      </g>
      {ticker !== null && (
        <Tag x={placement.tag.x} y={placement.tag.y} ticker={ticker} onClear={() => onClear(instrumentId)} />
      )}
    </g>
  )
}
