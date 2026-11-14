import { useEffect, useRef, useState } from 'react'
import { fetchDatasets, fetchEvents, fetchInstruments, fetchIR, fetchMidi, type Dataset, type Instrument, type IRSeries, type MarketEvent } from './api'
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

function Studio({ event }: { readonly event: MarketEvent }) {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [irs, setIrs] = useState<Readonly<Record<string, IRSeries>>>({})
  const [assignments, setAssignments] = useState<Readonly<Record<string, string>>>({})
  const [band, setBand] = useState<Band | null>(null)
  const [playing, setPlaying] = useState(false)
  const [starting, setStarting] = useState(false)
  const playPending = useRef(false)
  const playOperation = useRef(0)
  const [error, setError] = useState<string | null>(null)
  const [lit, flash] = useLit()
  const beat = usePlayhead(band, playing)
  // Latest drop per instrument; a slower, older fetch must not overwrite a newer drop.
  const active = useRef(true)
  const requestSeq = useRef(new Map<string, number>())

  useEffect(() => {
    active.current = true
    let cancelled = false
    let created: Band | null = null
    const load = async (): Promise<void> => {
      const [loadedDatasets, loadedInstruments] = await Promise.all([fetchDatasets(), fetchInstruments()])
      if (cancelled) return
      created = createBand(loadedInstruments, flash)
      setDatasets([...loadedDatasets, {
        id: 'event', ticker: `${event.symbol} · ${event.id.slice(0, 4)}`,
        name: `${event.name} · original crash arrangement`, period: `${event.start} to ${event.end}`,
      }])
      setInstruments(loadedInstruments)
      setBand(created)
      const loadedIrs = await fetchAllIrs(loadedDatasets)
      if (!cancelled) setIrs(loadedIrs)
    }
    load().catch((reason: unknown) => { if (!cancelled) setError(`Could not load this event: ${String(reason)}`) })
    return () => {
      active.current = false
      cancelled = true
      created?.dispose()
    }
  }, [flash, event])

  const handleAssign = (instrumentId: string, datasetId: string): void => {
    if (band === null) return
    const seq = (requestSeq.current.get(instrumentId) ?? 0) + 1
    requestSeq.current.set(instrumentId, seq)
    setError(null)
    const eventParts: Record<string, string> = { kick: 'drums', snare: 'drums', hihat: 'drums', bass: 'bass', synth: 'synth_lead', synth2: 'synth_pad', guitar: 'guitar' }
    const midiRequest = datasetId === 'event'
      ? fetchMidi(eventParts[instrumentId] ?? 'synth_lead', instrumentId, event.id)
      : fetchMidi(datasetId, instrumentId)
    midiRequest
      .then((midi) => {
        if (requestSeq.current.get(instrumentId) !== seq || !active.current) return // superseded or unmounted
        band.load(instrumentId, midi)
        setAssignments((previous) => ({ ...previous, [instrumentId]: datasetId }))
      })
      .catch((reason: unknown) => { if (active.current) setError(String(reason)) })
  }

  const handleClear = (instrumentId: string): void => {
    if (band === null) return
    requestSeq.current.set(instrumentId, (requestSeq.current.get(instrumentId) ?? 0) + 1)
    band.clear(instrumentId)
    const next = without(assignments, instrumentId)
    setAssignments(next)
    if (Object.keys(next).length === 0) {
      playOperation.current++
      playPending.current = false
      band.stop()
      setStarting(false)
      setPlaying(false)
    }
  }

  const togglePlay = (): void => {
    if (band === null || playPending.current) return
    if (playing) {
      band.stop()
      setPlaying(false)
      return
    }
    const operation = ++playOperation.current
    playPending.current = true
    setStarting(true)
    band
      .play()
      .then(() => { if (active.current && operation === playOperation.current) setPlaying(true) })
      .catch((reason: unknown) => { if (active.current && operation === playOperation.current) setError(`Audio failed to start: ${String(reason)}`) })
      .finally(() => { if (operation === playOperation.current) { playPending.current = false; if (active.current) setStarting(false) } })
  }

  const loopBeats = band?.loopBeats() ?? 0
  const progress = beat === null || loopBeats === 0 ? 0 : (beat % loopBeats) / loopBeats

  return (
    <main className="app">
      <a className="studio-back" href="#" title={event.name} aria-label={`Back to events from ${event.name}`}>← Events</a>
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
      {(starting || band === null) && <p className="studio-status" role="status">{starting ? 'Loading instrument sounds…' : 'Loading stocks…'}</p>}
      {error !== null && (
        <p className="toast" role="alert" onClick={() => setError(null)}>
          {error}
        </p>
      )}
    </main>
  )
}


/** The URL keeps event selection shareable and supports browser Back. */
export default function App() {
  const [events, setEvents] = useState<MarketEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [hash, setHash] = useState(window.location.hash)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const update = () => setHash(window.location.hash)
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  useEffect(() => {
    let cancelled = false
    fetchEvents().then((loaded) => { if (!cancelled) setEvents(loaded) })
      .catch((reason: unknown) => { if (!cancelled) setError(String(reason)) })
    return () => { cancelled = true }
  }, [attempt])
  const eventId = hash.startsWith('#event/') ? hash.slice(7) : ''
  const selected = events.find((event) => event.id === eventId)
  if (selected) return <Studio key={selected.id} event={selected} />
  return (
    <main className="event-menu">
      <header className="menu-header">
        <span className="brand"><span className="brand-mark" aria-hidden="true">◉</span> MARKET BAND</span>
        <h1>Choose an event</h1>
      </header>
      <section aria-label="Market events" className="event-grid">
        {events.map((event) => (
          <a className="event-card" key={event.id} href={`#event/${event.id}`}>
            <span className="event-year">{event.id.slice(0, 4)}</span>
            <h2>{event.name}</h2>
            <span className="card-arrow" aria-hidden="true">↗</span>
          </a>
        ))}
      </section>
      {events.length === 0 && !error && <p role="status">Loading the sessions…</p>}
      {eventId && !selected && events.length > 0 && <p role="alert">That event isn’t available. Choose a session above.</p>}
      {error && <div role="alert" className="menu-error"><p>Could not load the events. Check that the backend is running.</p><p>{error}</p><button onClick={() => { setError(null); setAttempt((value) => value + 1) }}>Try again</button></div>}
    </main>
  )
}
