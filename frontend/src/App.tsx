import { useEffect, useRef, useState } from 'react'
import { fetchInstruments, type Instrument } from './api'
import { createBand, type Band } from './audio/band'
import { SONG_EXTRA_INSTRUMENTS, SONGS } from './config'
import { useLit, usePlayhead } from './hooks'
import { fetchSong, splitSong } from './songs'
import { Stage } from './stage/Stage'
import { StockTray } from './stage/StockTray'
import './App.css'

/** Remove one key from a record, returning a new record. */
function without(record: Readonly<Record<string, string>>, key: string): Record<string, string> {
  const next = { ...record }
  delete next[key]
  return next
}

export default function App() {
  /** Instruments drawn on stage (from the backend). */
  const [instruments, setInstruments] = useState<Instrument[]>([])
  /** Every instrument the band can play: the stage ones plus off-stage song parts. */
  const [bandInstruments, setBandInstruments] = useState<readonly Instrument[]>([])
  const [assignments, setAssignments] = useState<Readonly<Record<string, string>>>({})
  const [band, setBand] = useState<Band | null>(null)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lit, flash] = useLit()
  const beat = usePlayhead(band, playing)
  // Latest song drop; a slower, older fetch must not overwrite a newer drop.
  const requestSeq = useRef(0)

  useEffect(() => {
    let cancelled = false
    let created: Band | null = null
    const load = async (): Promise<void> => {
      const loadedInstruments = await fetchInstruments()
      if (cancelled) return
      const all = [...loadedInstruments, ...SONG_EXTRA_INSTRUMENTS]
      created = createBand(all, flash)
      setInstruments(loadedInstruments)
      setBandInstruments(all)
      setBand(created)
    }
    load().catch((reason: unknown) => setError(`Backend unreachable: ${String(reason)}`))
    return () => {
      cancelled = true
      created?.dispose()
    }
  }, [flash])

  const stopPlayback = (): void => {
    band?.stop()
    setPlaying(false)
  }

  /** Dropping a song on any instrument loads the whole arrangement across the band. */
  const handleAssign = (_instrumentId: string, songId: string): void => {
    if (band === null) return
    requestSeq.current += 1
    const seq = requestSeq.current
    setError(null)
    fetchSong(songId)
      .then((midi) => {
        if (requestSeq.current !== seq) return // superseded by a newer drop
        const parts = splitSong(midi, bandInstruments)
        bandInstruments.forEach(({ id }) => {
          const part = parts.get(id)
          if (part === undefined) band.clear(id)
          else band.load(id, part)
        })
        setAssignments(Object.fromEntries([...parts.keys()].map((id) => [id, songId])))
      })
      .catch((reason: unknown) => setError(String(reason)))
  }

  /** Clicking a tag mutes that part; muting the last stage part also clears off-stage parts. */
  const handleClear = (instrumentId: string): void => {
    if (band === null) return
    band.clear(instrumentId)
    const next = without(assignments, instrumentId)
    const stageLeft = Object.keys(next).filter((id) => instruments.some((i) => i.id === id))
    if (stageLeft.length > 0) {
      setAssignments(next)
      return
    }
    Object.keys(next).forEach((id) => band.clear(id))
    setAssignments({})
    if (playing) stopPlayback()
  }

  const togglePlay = (): void => {
    if (band === null) return
    if (playing) {
      stopPlayback()
      return
    }
    band
      .play()
      .then(() => setPlaying(true))
      .catch((reason: unknown) => setError(`Audio failed to start: ${String(reason)}`))
  }

  const loopBeats = band?.loopBeats() ?? 0
  const progress = beat === null || loopBeats === 0 ? 0 : (beat % loopBeats) / loopBeats

  return (
    <main className="app">
      <Stage
        instruments={instruments}
        datasets={SONGS}
        assignments={assignments}
        lit={lit}
        playing={playing}
        progress={progress}
        onAssign={handleAssign}
        onClear={handleClear}
        onTogglePlay={togglePlay}
      />
      <StockTray datasets={SONGS} irs={{}} beat={beat} />
      {error !== null && (
        <p className="toast" role="alert" onClick={() => setError(null)}>
          {error}
        </p>
      )}
    </main>
  )
}
