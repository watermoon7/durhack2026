import { PLAY } from './layout'

interface PlayButtonProps {
  readonly playing: boolean
  readonly disabled: boolean
  /** Fraction of the loop played, in [0, 1]. */
  readonly progress: number
  readonly onToggle: () => void
}

/** Round play/pause button with a progress ring tracing the loop. */
export function PlayButton({ playing, disabled, progress, onToggle }: PlayButtonProps) {
  if (!(progress >= 0 && progress <= 1)) throw new Error(`progress ${progress} outside [0, 1]`)
  const { cx, cy, r, ringR } = PLAY
  const circumference = 2 * Math.PI * ringR
  const activate = (): void => {
    if (!disabled) onToggle()
  }
  return (
    <g
      className={`play${disabled ? ' play--disabled' : ''}`}
      role="button"
      aria-label={playing ? 'Pause' : 'Play'}
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onClick={activate}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') activate()
      }}
    >
      <circle className="play__track" cx={cx} cy={cy} r={ringR} />
      {progress > 0 && (
        <circle
          className="play__progress"
          cx={cx}
          cy={cy}
          r={ringR}
          strokeDasharray={`${progress * circumference} ${circumference}`}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
      )}
      <circle className="play__face" cx={cx} cy={cy} r={r} />
      {playing ? (
        <>
          <rect className="play__icon" x={cx - 12} y={cy - 14} width={8} height={28} rx={2} />
          <rect className="play__icon" x={cx + 4} y={cy - 14} width={8} height={28} rx={2} />
        </>
      ) : (
        <path className="play__icon" d={`M${cx - 9} ${cy - 16} L${cx - 9} ${cy + 16} L${cx + 17} ${cy} Z`} />
      )}
    </g>
  )
}
