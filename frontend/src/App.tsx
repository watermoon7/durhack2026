import { useEffect, useRef, useState } from 'react'
import {
  fetchDatasets,
  fetchGenres,
  fetchInstruments,
  fetchIR,
  fetchMidi,
  type Dataset,
  type Genre,
  type Instrument,
  type IRSeries,
  type Scenario,
} from './api'
import { createBand, missingSounds, type Band } from './audio/band'
import { VOICE_TRACKS } from './config'
import { useLit, usePlayhead } from './hooks'
import { GenreSelect } from './stage/GenreSelect'
import { Scrubber } from './stage/Scrubber'
import { Stage } from './stage/Stage'
import { StockTray } from './stage/StockTray'
import './App.css'

/** Fetch every dataset's IR up front so the tray can draw price shapes before any drop. */
async function fetchAllIrs(datasets: readonly Dataset[], scenarioId: string): Promise<Record<string, IRSeries>> {
  const entries = await Promise.all(datasets.map(async (d) => [d.id, await fetchIR(d.id, scenarioId)] as const))
  return Object.fromEntries(entries)
}

/** Remove one key from a record, returning a new record. */
function without(record: Readonly<Record<string, string>>, key: string): Record<string, string> {
  const next = { ...record }
  delete next[key]
  return next
}

/** Fail loudly if any genre the backend offers has no sound for some instrument. */
function checkGenres(genres: readonly Genre[], instruments: readonly Instrument[]): void {
  for (const genre of genres) {
    const missing = missingSounds(genre.id, instruments)
    if (missing.length > 0) throw new Error(`genre '${genre.id}' has no sound for: ${missing.join(', ')}`)
  }
}

interface AppProps {
  /** The scenario whose band fills the tray; chosen on the menu (see Root). */
  readonly scenario: Scenario
}

export default function App({ scenario }: AppProps) {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [instruments, setInstruments] = useState<Instrument[]>([])
  const [genres, setGenres] = useState<Genre[]>([])
  const [genre, setGenre] = useState('')
  const [irs, setIrs] = useState<Readonly<Record<string, IRSeries>>>({})
  const [assignments, setAssignments] = useState<Readonly<Record<string, string>>>({})
  const [band, setBand] = useState<Band | null>(null)
  const [playing, setPlaying] = useState(false)
  const [voiceOn, setVoiceOn] = useState(false)
  const voiceTrack = VOICE_TRACKS[scenario.id]
  const [error, setError] = useState<string | null>(null)
  const [lit, flash] = useLit()
  const [beat, refreshBeat] = usePlayhead(band, playing)
  // Latest drop per instrument; a slower, older fetch must not overwrite a newer drop.
  const requestSeq = useRef(new Map<string, number>())
  // Latest genre change; an older change that finishes loading later must not win.
  const genreSeq = useRef(0)
  // Async callbacks read the latest genre and assignments from here, not from a stale render.
  const genreRef = useRef('')
  const assignmentsRef = useRef<Readonly<Record<string, string>>>({})

  useEffect(() => {
    let cancelled = false
    let created: Band | null = null
    const load = async (): Promise<void> => {
      const [loadedDatasets, loadedInstruments, loadedGenres] = await Promise.all([
        fetchDatasets(scenario.id),
        fetchInstruments(),
        fetchGenres(),
      ])
      const loadedIrs = await fetchAllIrs(loadedDatasets, scenario.id)
      if (cancelled) return
      checkGenres(loadedGenres, loadedInstruments)
      const first = loadedGenres[0]
      if (first === undefined) throw new Error('the backend offers no genres')
      created = createBand(loadedInstruments, first.id, flash)
      const track = VOICE_TRACKS[scenario.id]
      if (track !== undefined) created.loadVocal(track.url)
      genreRef.current = first.id
      setDatasets(loadedDatasets)
      setInstruments(loadedInstruments)
      setGenres(loadedGenres)
      setGenre(first.id)
      setIrs(loadedIrs)
      setBand(created)
    }
    load().catch((reason: unknown) => setError(`Could not start the band: ${String(reason)}`))
    return () => {
      cancelled = true
      created?.dispose()
    }
  }, [flash, scenario.id])

  /** Fetch and schedule one instrument's part in the current genre, ignoring stale replies. */
  const loadPart = (target: Band, instrumentId: string, datasetId: string): void => {
    const seq = (requestSeq.current.get(instrumentId) ?? 0) + 1
    requestSeq.current.set(instrumentId, seq)
    fetchMidi(datasetId, instrumentId, genreRef.current, scenario.id)
      .then((midi) => {
        if (requestSeq.current.get(instrumentId) !== seq) return // superseded by a newer request
        target.load(instrumentId, midi)
        assignmentsRef.current = { ...assignmentsRef.current, [instrumentId]: datasetId }
        setAssignments(assignmentsRef.current)
      })
      .catch((reason: unknown) => setError(String(reason)))
  }

  const handleAssign = (instrumentId: string, datasetId: string): void => {
    if (band === null) return
    setError(null)
    loadPart(band, instrumentId, datasetId)
  }

  const handleClear = (instrumentId: string): void => {
    if (band === null) return
    requestSeq.current.set(instrumentId, (requestSeq.current.get(instrumentId) ?? 0) + 1)
    band.clear(instrumentId)
    assignmentsRef.current = without(assignmentsRef.current, instrumentId)
    setAssignments(assignmentsRef.current)
    if (Object.keys(assignmentsRef.current).length === 0 && playing && !voiceOn) {
      band.stop()
      setPlaying(false)
      refreshBeat()
    }
  }

  /** Turn the scenario's sung track on or off; off with no stocks left stops playback. */
  const handleToggleVoice = (): void => {
    if (band === null || voiceTrack === undefined) return
    const next = !voiceOn
    band.setVocal(next)
    setVoiceOn(next)
    if (!next && Object.keys(assignmentsRef.current).length === 0 && playing) {
      band.stop()
      setPlaying(false)
      refreshBeat()
    }
  }

  /** Swap every sound to the new genre, then re-render every assigned part in it. */
  const handleGenre = (next: string): void => {
    if (band === null || next === genreRef.current) return
    genreSeq.current += 1
    const seq = genreSeq.current
    genreRef.current = next
    setGenre(next)
    setError(null)
    band
      .setGenre(next)
      .then(() => {
        if (genreSeq.current !== seq) return // a newer genre was chosen meanwhile
        Object.entries(assignmentsRef.current).forEach(([instrumentId, datasetId]) =>
          loadPart(band, instrumentId, datasetId),
        )
      })
      .catch((reason: unknown) => setError(`Genre change failed: ${String(reason)}`))
  }

  const togglePlay = (): void => {
    if (band === null) return
    if (playing) {
      band.pause()
      setPlaying(false)
      refreshBeat() // the exact paused position, not the last animation frame's
      return
    }
    band
      .play()
      .then(() => setPlaying(true))
      .catch((reason: unknown) => setError(`Audio failed to start: ${String(reason)}`))
  }

  /** Jump to a beat from the progress bar; a paused song stays paused at the new spot. */
  const handleSeek = (target: number): void => {
    if (band === null || band.loopBeats() === 0) return
    band.seek(target)
    if (!playing) refreshBeat() // while playing, the next animation frame picks it up
  }

  const loopBeats = band?.loopBeats() ?? 0
  const loopBeat = beat === null || loopBeats === 0 ? 0 : beat % loopBeats
  const progress = loopBeats === 0 ? 0 : loopBeat / loopBeats
  // Fresh or stopped at the start: no playhead dot on the tray, as before pause existed.
  const trayBeat = playing || loopBeat > 0 ? beat : null

  return (
    <main className="app">
      <GenreSelect genres={genres} value={genre} onChange={handleGenre} />
      <a className="scenario-back" href="#" title="Back to scenarios">
        ← {scenario.name}
      </a>
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
        voice={voiceTrack === undefined ? null : { on: voiceOn, title: voiceTrack.title }}
        onToggleVoice={handleToggleVoice}
      />
      {band !== null && (
        <Scrubber
          beat={loopBeat}
          loopBeats={loopBeats}
          secondsPerBeat={band.secondsPerBeat()}
          onSeek={handleSeek}
        />
      )}
      <StockTray datasets={datasets} irs={irs} beat={trayBeat} />
      {error !== null && (
        <p className="toast" role="alert" onClick={() => setError(null)}>
          {error}
        </p>
      )}
    </main>
  )
}
