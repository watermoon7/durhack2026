import { useEffect, useState, type DragEvent } from 'react'
import {
  fetchDatasets,
  fetchInstruments,
  fetchIR,
  fetchMidi,
  type Dataset,
  type Instrument,
  type IRSeries,
} from './api'
import { createBand, type Band } from './audio/band'
import { InstrumentSlot } from './components/InstrumentSlot'
import { DRAG_MIME } from './config'
import './App.css'

/**
 * Track the transport position once per animation frame while playing.
 * The rAF loop terminates when `playing` turns false or the component unmounts.
 */
function usePlayhead(band: Band | null, playing: boolean): number | null {
  const [beat, setBeat] = useState<number | null>(null)
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
  return playing ? beat : null
}

/** Start dragging a dataset card. */
function handleDatasetDragStart(event: DragEvent<HTMLLIElement>, datasetId: string): void {
  event.dataTransfer.setData(DRAG_MIME, datasetId)
  event.dataTransfer.effectAllowed = 'copy'
}

export default function App() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [assignments, setAssignments] = useState<Readonly<Record<string, string>>>({})
  const [irs, setIrs] = useState<Readonly<Record<string, IRSeries>>>({})
  const [band, setBand] = useState<Band | null>(null)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const beat = usePlayhead(band, playing)

  useEffect(() => {
    let cancelled = false
    let created: Band | null = null
    Promise.all([fetchDatasets(), fetchInstruments()])
      .then(([loadedDatasets, loadedInstruments]) => {
        if (cancelled) return
        created = createBand(loadedInstruments.map((instrument) => instrument.id))
        setDatasets(loadedDatasets)
        setInstruments(loadedInstruments)
        setBand(created)
      })
      .catch((reason: unknown) => setError(`Could not reach the backend: ${String(reason)}`))
    return () => {
      cancelled = true
      created?.dispose()
    }
  }, [])

  /** Fetch a dataset's .mid for an instrument (plus its IR for the chart) and schedule it. */
  const assign = async (instrumentId: string, datasetId: string): Promise<void> => {
    if (band === null) throw new Error('band not ready')
    const cached = irs[datasetId]
    const [midi, ir] = await Promise.all([
      fetchMidi(datasetId, instrumentId),
      cached === undefined ? fetchIR(datasetId) : Promise.resolve(cached),
    ])
    band.load(instrumentId, midi)
    setIrs((previous) => ({ ...previous, [datasetId]: ir }))
    setAssignments((previous) => ({ ...previous, [instrumentId]: datasetId }))
  }

  const handleAssign = (instrumentId: string, datasetId: string): void => {
    setError(null)
    assign(instrumentId, datasetId).catch((reason: unknown) => setError(String(reason)))
  }

  const handleClear = (instrumentId: string): void => {
    band?.clear(instrumentId)
    setAssignments((previous) => {
      const next = { ...previous }
      delete next[instrumentId]
      return next
    })
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

  const firstIr = Object.values(assignments)
    .map((datasetId) => irs[datasetId])
    .find((ir) => ir !== undefined)
  const currentDate =
    firstIr && beat !== null ? firstIr.beats[Math.floor(beat) % firstIr.beats.length]?.date : null
  const hasAssignments = Object.keys(assignments).length > 0

  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>Market Band</h1>
          <p className="subtitle">{datasets[0]?.period ?? ''} · drag a dataset onto an instrument</p>
        </div>
        <div className="transport">
          <span className="transport__date">{currentDate ?? '—'}</span>
          <button type="button" onClick={togglePlay} disabled={band === null || !hasAssignments}>
            {playing ? 'Stop' : 'Play'}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="palette" aria-label="Datasets">
        <h2>Datasets</h2>
        <ul>
          {datasets.map((dataset) => (
            <li
              key={dataset.id}
              draggable
              onDragStart={(event) => handleDatasetDragStart(event, dataset.id)}
            >
              <strong>{dataset.ticker}</strong>
              <span>{dataset.name}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="stage" aria-label="Stage">
        {instruments.map((instrument) => {
          const datasetId = assignments[instrument.id]
          const dataset = datasets.find((candidate) => candidate.id === datasetId) ?? null
          return (
            <InstrumentSlot
              key={instrument.id}
              instrument={instrument}
              dataset={dataset}
              ir={datasetId === undefined ? null : (irs[datasetId] ?? null)}
              beat={beat}
              onAssign={handleAssign}
              onClear={handleClear}
            />
          )
        })}
      </section>
    </main>
  )
}
