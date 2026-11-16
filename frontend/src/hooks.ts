import { useCallback, useEffect, useRef, useState } from 'react'
import type { Band } from './audio/band'
import { PULSE_MS } from './config'

/**
 * Track the transport position once per animation frame while playing. The rAF loop terminates
 * when `playing` turns false or the component unmounts. While paused the last position is kept;
 * call the returned `refresh` after anything that moves the playhead without playing (pause,
 * stop, seek). The beat is null until a band exists.
 */
export function usePlayhead(band: Band | null, playing: boolean): [number | null, () => void] {
  const [beat, setBeat] = useState<number | null>(null)
  const refresh = useCallback((): void => {
    if (band !== null) setBeat(band.currentBeat())
  }, [band])
  useEffect(() => {
    if (band === null || !playing) return
    let frame = 0
    const tick = (): void => {
      setBeat(band.currentBeat())
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [band, playing])
  return [band === null ? null : beat, refresh]
}

/**
 * Per-instrument "just played" flags. `flash(id)` lights an instrument for PULSE_MS; a new
 * flash restarts its timer. One timer per instrument at most; all cleared on unmount.
 */
export function useLit(): [Readonly<Record<string, boolean>>, (instrumentId: string) => void] {
  const [lit, setLit] = useState<Readonly<Record<string, boolean>>>({})
  const timers = useRef(new Map<string, number>())

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((timer) => window.clearTimeout(timer))
  }, [])

  const flash = useCallback((instrumentId: string): void => {
    if (instrumentId === '') throw new Error('instrumentId is required')
    const previous = timers.current.get(instrumentId)
    if (previous !== undefined) window.clearTimeout(previous)
    setLit((current) => (current[instrumentId] === true ? current : { ...current, [instrumentId]: true }))
    const timer = window.setTimeout(() => {
      timers.current.delete(instrumentId)
      setLit((current) => ({ ...current, [instrumentId]: false }))
    }, PULSE_MS)
    timers.current.set(instrumentId, timer)
  }, [])

  return [lit, flash]
}
