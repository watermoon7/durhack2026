import { useEffect, useRef, useState } from 'react'
import { fetchCatalogue, fetchInstruments, fetchIR, fetchMidi, type Catalogue, type Instrument, type IRSeries } from './historyApi'
import { createBand } from './audio/historyBand'
import type { Band } from './audio/band'
import { useLit, usePlayhead } from './hooks'
import { Stage } from './stage/Stage'
import { StockTray } from './stage/StockTray'
import './App.css'

export default function App() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null)
  const [periodId, setPeriodId] = useState('')
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [irs, setIrs] = useState<Record<string, IRSeries>>({})
  const [assignments, setAssignments] = useState<Record<string, string>>({})
  const [band, setBand] = useState<Band | null>(null)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lit, flash] = useLit()
  const epoch = useRef(0)
  const sequence = useRef(new Map<string, number>())
  const beat = usePlayhead(band, playing)
  const datasets = catalogue?.datasets.filter(d => d.period_id === periodId) ?? []
  const period = catalogue?.periods.find(p => p.id === periodId)

  useEffect(() => {
    let cancelled = false
    let created: Band | null = null
    Promise.all([fetchCatalogue(), fetchInstruments()]).then(([data, members]) => {
      if (cancelled) return
      created = createBand(members, flash)
      setBand(created)
      setCatalogue(data)
      setInstruments(members)
      setPeriodId((data.periods.find(p => p.complete) ?? data.periods.find(p => p.available > 0) ?? data.periods[0])?.id ?? '')
    }).catch((reason: unknown) => { if (!cancelled) setError(String(reason)) })
    return () => { cancelled = true; epoch.current += 1; created?.dispose() }
  }, [flash])

  useEffect(() => {
    let cancelled = false
    setIrs({})
    const selected = catalogue?.datasets.filter(d => d.period_id === periodId) ?? []
    Promise.all(selected.map(async d => [d.id, await fetchIR(d.id)] as const))
      .then(entries => { if (!cancelled) setIrs(Object.fromEntries(entries)) })
      .catch((reason: unknown) => { if (!cancelled) setError(`Chart load: ${String(reason)}`) })
    return () => { cancelled = true }
  }, [catalogue, periodId])

  const reset = (): void => {
    epoch.current += 1
    sequence.current.clear()
    band?.stop()
    instruments.forEach(i => band?.clear(i.id))
    setAssignments({})
    setPlaying(false)
    setError(null)
  }
  const changePeriod = (id: string): void => { reset(); setPeriodId(id) }
  const refresh = (): void => {
    fetchCatalogue().then(data => {
      reset()
      setCatalogue(data)
      if (!data.periods.some(p => p.id === periodId)) setPeriodId(data.periods[0]?.id ?? '')
    }).catch((reason: unknown) => setError(String(reason)))
  }
  const assign = (instrument: string, dataset: string): void => {
    if (band === null || !datasets.some(d => d.id === dataset)) return
    const generation = epoch.current
    const seq = (sequence.current.get(instrument) ?? 0) + 1
    sequence.current.set(instrument, seq)
    fetchMidi(dataset, instrument).then(midi => {
      if (epoch.current !== generation || sequence.current.get(instrument) !== seq) return
      band.load(instrument, midi)
      setAssignments(previous => ({ ...previous, [instrument]: dataset }))
    }).catch((reason: unknown) => {
      if (epoch.current === generation && sequence.current.get(instrument) === seq) setError(String(reason))
    })
  }
  const clear = (instrument: string): void => {
    sequence.current.set(instrument, (sequence.current.get(instrument) ?? 0) + 1)
    band?.clear(instrument)
    const next = { ...assignments }
    delete next[instrument]
    setAssignments(next)
    if (Object.keys(next).length === 0) { band?.stop(); setPlaying(false) }
  }
  const togglePlay = (): void => {
    if (band === null) return
    if (playing) { band.stop(); setPlaying(false); return }
    const generation = epoch.current
    band.play().then(() => {
      if (epoch.current === generation) setPlaying(true)
      else band.stop()
    }).catch((reason: unknown) => { if (epoch.current === generation) setError(String(reason)) })
  }
  const loop = band?.loopBeats() ?? 0
  return (
    <main className="app">
      <section aria-label="Historical period" style={{ padding: '1rem', color: 'inherit' }}>
        <label htmlFor="period">Crash or stable period: </label>
        <select id="period" value={periodId} onChange={event => changePeriod(event.target.value)}>
          <option value="" disabled>Select a period</option>
          {catalogue?.periods.map(p => <option key={p.id} value={p.id}>
            {p.kind === 'stable' ? (p.available > 0 ? 'Stable' : 'Stable candidate') : 'Crash/shock'}: {p.name} ({p.market}) — {p.available}/{p.expected} assets
          </option>)}
        </select>{' '}<button type="button" onClick={refresh}>Refresh generated data</button>
        {period !== undefined && <p>{period.start} to {period.end} (end exclusive). {period.available}/6 assets ready.
          {!period.complete && ' Incomplete: missing pairs have not generated successfully. No demo data is substituted.'}</p>}
        <p>Drag a stock/index onto any instrument; reuse an asset on multiple instruments.</p>
        <p>{datasets.map(d => `${d.ticker}: ${Math.round(d.simulated_fraction * 100)}% simulated`).join('; ')}
          {' '}Simulated paths are not observed intraday trades.</p>
        {catalogue !== null && <details><summary>Availability and generation errors ({catalogue.datasets.length}/90)</summary>
          <p>{catalogue.diagnostics.message} Different runs can have different calibration sets.</p>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{catalogue.diagnostics.issues.join('\n')}</pre>
        </details>}
      </section>
      <Stage instruments={instruments} datasets={datasets} assignments={assignments} lit={lit}
        playing={playing} progress={beat === null || loop === 0 ? 0 : (beat % loop) / loop}
        onAssign={assign} onClear={clear} onTogglePlay={togglePlay} />
      <StockTray datasets={datasets} irs={irs} beat={beat} />
      {error !== null && <p className="toast" role="alert" onClick={() => setError(null)}>{error}</p>}
    </main>
  )
}
