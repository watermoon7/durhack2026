import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { SEEK_SNAP_BEATS } from '../config'

interface ScrubberProps {
  /** Playhead in beats within the loop, in [0, loopBeats]. */
  readonly beat: number
  /** Loop length in beats; 0 means nothing is loaded and the bar is disabled. */
  readonly loopBeats: number
  /** For the time labels. */
  readonly secondsPerBeat: number
  /** Called once the user lets go of the handle (or presses an arrow key), with the new beat. */
  readonly onSeek: (beat: number) => void
}

/** Format seconds as m:ss. */
function formatTime(seconds: number): string {
  if (!(seconds >= 0)) throw new Error(`time ${seconds} must be non-negative`)
  const whole = Math.floor(seconds)
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}

/**
 * Song progress bar with a draggable handle. While dragging, the bar shows the handle's position
 * but playback carries on; the seek happens on release (the range input's native `change`
 * event), so dragging doesn't stutter the band. The seek snaps to the nearest SEEK_SNAP_BEATS so
 * the notes on that beat still sound.
 */
export function Scrubber({ beat, loopBeats, secondsPerBeat, onSeek }: ScrubberProps) {
  if (!(loopBeats >= 0)) throw new Error(`loopBeats ${loopBeats} must be non-negative`)
  if (!(secondsPerBeat > 0)) throw new Error(`secondsPerBeat ${secondsPerBeat} must be positive`)
  const [dragBeat, setDragBeat] = useState<number | null>(null)
  const input = useRef<HTMLInputElement>(null)
  // The native listener is attached once; it reads the latest callback from here.
  const onSeekRef = useRef(onSeek)
  useEffect(() => {
    onSeekRef.current = onSeek
  }, [onSeek])

  useEffect(() => {
    const element = input.current
    if (element === null) return
    // React's onChange is the native `input` event (every move); `change` fires on commit.
    const commit = (): void => {
      setDragBeat(null)
      const snapped = Math.round(Number(element.value) / SEEK_SNAP_BEATS) * SEEK_SNAP_BEATS
      onSeekRef.current(Math.min(snapped, Number(element.max)))
    }
    element.addEventListener('change', commit)
    return () => element.removeEventListener('change', commit)
  }, [])

  const disabled = loopBeats === 0
  const shown = disabled ? 0 : Math.min(dragBeat ?? beat, loopBeats)
  const fraction = disabled ? 0 : shown / loopBeats

  return (
    <div className={`scrubber${disabled ? ' scrubber--disabled' : ''}`}>
      <span className="scrubber__time">{formatTime(shown * secondsPerBeat)}</span>
      <input
        ref={input}
        className="scrubber__range"
        type="range"
        aria-label="Song position"
        aria-valuetext={`${formatTime(shown * secondsPerBeat)} of ${formatTime(loopBeats * secondsPerBeat)}`}
        min={0}
        max={loopBeats}
        step="any"
        value={shown}
        disabled={disabled}
        style={{ '--fill': `${(fraction * 100).toFixed(2)}%` } as CSSProperties}
        onChange={(event) => setDragBeat(Number(event.currentTarget.value))}
      />
      <span className="scrubber__time">{formatTime(loopBeats * secondsPerBeat)}</span>
    </div>
  )
}
