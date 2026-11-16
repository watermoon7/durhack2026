/** Typed client for the Market Band backend. Every response is schema-validated. */

import { Midi } from '@tonejs/midi'
import { z } from 'zod'
import { API_BASE_URL } from './config'

const DatasetSchema = z.object({
  id: z.string(),
  ticker: z.string(),
  name: z.string(),
  period: z.string(),
})

const InstrumentSchema = z.object({
  id: z.string(),
  name: z.string(),
  root_midi: z.number().int(),
  octaves: z.number().int().positive(),
})

const GenreSchema = z.object({ id: z.string().min(1), name: z.string().min(1) })

const ScenarioSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  period: z.string(),
  tickers: z.array(z.string()).min(1),
})

const unit = z.number().min(0).max(1)

const IRBeatSchema = z.object({
  date: z.string(),
  level: unit,
  swing: unit,
  activity: unit,
  intensity: unit,
})

const IRSeriesSchema = z.object({
  source: z.string(),
  beats: z.array(IRBeatSchema).min(1),
  bars: z.array(z.object({ mood: unit })).min(1),
})

export type Dataset = z.infer<typeof DatasetSchema>
export type Instrument = z.infer<typeof InstrumentSchema>
export type IRSeries = z.infer<typeof IRSeriesSchema>
export type Genre = z.infer<typeof GenreSchema>
export type Scenario = z.infer<typeof ScenarioSchema>

/** API prefix for a scenario's band, or the default Q1 2020 band when no scenario is given. */
function bandBase(scenarioId?: string): string {
  if (scenarioId === undefined) return '/api'
  if (scenarioId === '') throw new Error('scenarioId must not be empty')
  return `/api/scenarios/${encodeURIComponent(scenarioId)}`
}

/** Fetch a path from the backend, throwing on any non-2xx status. */
async function request(path: string): Promise<Response> {
  if (!path.startsWith('/api/')) throw new Error(`refusing non-API path: ${path}`)
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`${path} -> HTTP ${response.status}: ${await response.text()}`)
  }
  return response
}

/** Fetch and validate a JSON endpoint. */
async function getJson<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  const response = await request(path)
  const parsed = schema.safeParse(await response.json())
  if (!parsed.success) throw new Error(`${path}: unexpected response shape: ${parsed.error.message}`)
  return parsed.data
}

/** List the historical scenarios for the menu, in menu order. */
export function fetchScenarios(): Promise<Scenario[]> {
  return getJson('/api/scenarios', z.array(ScenarioSchema).min(1))
}

/** List the datasets that can be dragged onto instruments (a scenario's band, if given). */
export function fetchDatasets(scenarioId?: string): Promise<Dataset[]> {
  return getJson(`${bandBase(scenarioId)}/datasets`, z.array(DatasetSchema))
}

/** List the band's instruments. */
export function fetchInstruments(): Promise<Instrument[]> {
  return getJson('/api/instruments', z.array(InstrumentSchema))
}

/** List the genres the band can play in; the first is the default. */
export function fetchGenres(): Promise<Genre[]> {
  return getJson('/api/genres', z.array(GenreSchema).min(1))
}

/** Fetch the IR series for a dataset (drives the chart). */
export function fetchIR(datasetId: string, scenarioId?: string): Promise<IRSeries> {
  if (datasetId === '') throw new Error('datasetId is required')
  return getJson(`${bandBase(scenarioId)}/datasets/${encodeURIComponent(datasetId)}/ir`, IRSeriesSchema)
}

/** URL of the rendered .mid file for a dataset on an instrument in a genre. */
export function midiUrl(datasetId: string, instrumentId: string, genre: string, scenarioId?: string): string {
  if (datasetId === '' || instrumentId === '' || genre === '') throw new Error('all ids are required')
  const query = new URLSearchParams({ dataset_id: datasetId, instrument_id: instrumentId, genre })
  return `${API_BASE_URL}${bandBase(scenarioId)}/midi?${query.toString()}`
}

/** Fetch and parse the .mid file for a dataset on an instrument in a genre. */
export async function fetchMidi(
  datasetId: string,
  instrumentId: string,
  genre: string,
  scenarioId?: string,
): Promise<Midi> {
  const path = midiUrl(datasetId, instrumentId, genre, scenarioId).slice(API_BASE_URL.length)
  const response = await request(path)
  const midi = new Midi(await response.arrayBuffer())
  if (midi.tracks.length === 0) throw new Error(`${path}: MIDI file has no tracks`)
  return midi
}
