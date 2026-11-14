import { useEffect, useRef, useState } from 'react'
import { fetchDatasets, fetchInstruments, fetchIR, fetchMidi, type Dataset, type Instrument, type IRSeries } from './api'
import { createBand, type Band } from './audio/band'
import { useLit, usePlayhead } from './hooks'
import { Stage } from './stage/Stage'
import { StockTray } from './stage/StockTray'
import './App.css'

/** Fetch every dataset's IR up front so the tray can draw price shapes before any drop. */
async function fetchAllIrs(datasets: readonly Dataset[]): Promise<Record<string, IRSeries>> {
  const entries = await Promise.all(datasets.map(async (d) => [d.id, await fetchIR(d.id)] as const))
  return Object.fromEntries(entries)
}

/** Remove one key from a record, returning a new record. */
function without(record: Readonly<Record<string, string>>, key: string): Record<string, string> {
  const next = { ...record }
  delete next[key]
  return next
}

export default function App() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [irs, setIrs] = useState<Readonly<Record<string, IRSeries>>>({})
  const [assignments, setAssignments] = useState<Readonly<Record<string, string>>>({})
  const [band, setBand] = useState<Band | null>(null)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lit, flash] = useLit()
  const beat = usePlayhead(band, playing)
  // Latest drop per instrument; a slower, older fetch must not overwrite a newer drop.
  const requestSeq = useRef(new Map<string, number>())

  useEffect(() => {
    let cancelled = false
    let created: Band | null = null
    const load = async (): Promise<void> => {
      const [loadedDatasets, loadedInstruments] = await Promise.all([fetchDatasets(), fetchInstruments()])
      const loadedIrs = await fetchAllIrs(loadedDatasets)
      if (cancelled) return
      created = createBand(loadedInstruments, flash)
      setDatasets(loadedDatasets)
      setInstruments(loadedInstruments)
      setIrs(loadedIrs)
      setBand(created)
    }
    load().catch((reason: unknown) => setError(`Backend unreachable: ${String(reason)}`))
    return () => {
      cancelled = true
      created?.dispose()
    }
  }, [flash])

  const handleAssign = (instrumentId: string, datasetId: string): void => {
    if (band === null) return
    const seq = (requestSeq.current.get(instrumentId) ?? 0) + 1
    requestSeq.current.set(instrumentId, seq)
    setError(null)
    fetchMidi(datasetId, instrumentId)
      .then((midi) => {
        if (requestSeq.current.get(instrumentId) !== seq) return // superseded by a newer drop
        band.load(instrumentId, midi)
        setAssignments((previous) => ({ ...previous, [instrumentId]: datasetId }))
      })
      .catch((reason: unknown) => setError(String(reason)))
  }

  const handleClear = (instrumentId: string): void => {
    if (band === null) return
    requestSeq.current.set(instrumentId, (requestSeq.current.get(instrumentId) ?? 0) + 1)
    band.clear(instrumentId)
    const next = without(assignments, instrumentId)
    setAssignments(next)
    if (Object.keys(next).length === 0 && playing) {
      band.stop()
      setPlaying(false)
    }
  }

  const togglePlay = (): void => {
    if (band === null) return
    if (playing) {
      band.stop()
      setPlaying(false)
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
        datasets={datasets}
        assignments={assignments}
        lit={lit}
        playing={playing}
        progress={progress}
        onAssign={handleAssign}
        onClear={handleClear}
        onTogglePlay={togglePlay}
      />
      <StockTray datasets={datasets} irs={irs} beat={beat} />
      {error !== null && (
        <p className="toast" role="alert" onClick={() => setError(null)}>
          {error}
        </p>
      )}
    </main>
  )
}

