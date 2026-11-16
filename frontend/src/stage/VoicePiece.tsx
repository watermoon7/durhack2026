import type { KeyboardEvent } from 'react'
import { VoiceArt } from './art'
import { VOICE } from './layout'

interface VoicePieceProps {
  readonly on: boolean
  /** The sung track's title, shown as the tooltip. */
  readonly title: string
  readonly onToggle: () => void
}

const TAG_HEIGHT = 28
const TAG_WIDTH = 132

/**
 * The Voice piece: click (or Enter / Space) to turn the scenario's sung track on or off.
 * It has no drag handlers, so the browser refuses stock drops on it.
 */
export function VoicePiece({ on, title, onToggle }: VoicePieceProps) {
  if (title === '') throw new Error('VoicePiece needs a track title')
  const handleKey = (event: KeyboardEvent<SVGGElement>): void => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    onToggle()
  }
  const { outline, tag, pool } = VOICE
  return (
    <g
      className={`piece voice ${on ? 'piece--filled voice--on' : ''}`}
      role="switch"
      aria-checked={on}
      aria-label={`Voice: ${title}`}
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={handleKey}
    >
      <title>{`${on ? 'Turn off' : 'Turn on'} the voice: “${title}”`}</title>
      <ellipse {...pool} fill="url(#mb-pool)" />
      <g className="piece__art">
        <VoiceArt />
      </g>
      <rect className="piece__ring" {...outline} />
      <rect className="piece__hit" {...outline} />
      <g className="tag voice__tag">
        <rect x={tag.x - TAG_WIDTH / 2} y={tag.y - TAG_HEIGHT / 2} width={TAG_WIDTH} height={TAG_HEIGHT} rx={TAG_HEIGHT / 2} />
        <text x={tag.x} y={tag.y} dominantBaseline="central" textAnchor="middle">
          {on ? 'VOICE ON' : 'VOICE OFF'}
        </text>
      </g>
    </g>
  )
}
