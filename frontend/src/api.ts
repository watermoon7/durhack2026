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

const IRBeatSchema = z.object({
  date: z.string(),
  level: z.number().min(0).max(1),
  activity: z.number().min(0).max(1),
  intensity: z.number().min(0).max(1),
})

const IRSeriesSchema = z.object({
  source: z.string(),
  beats: z.array(IRBeatSchema).min(1),
})

export type Dataset = z.infer<typeof DatasetSchema>
export type Instrument = z.infer<typeof InstrumentSchema>
export type IRSeries = z.infer<typeof IRSeriesSchema>

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
const jsonRequests = new Map<string, Promise<unknown>>()

async function getJson<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  let pending = jsonRequests.get(path)
  if (!pending) {
    pending = request(path).then((response) => response.json() as Promise<unknown>)
    jsonRequests.set(path, pending)
    void pending.catch(() => jsonRequests.delete(path))
  }
  const parsed = schema.safeParse(await pending)
  if (!parsed.success) {
    jsonRequests.delete(path)
    throw new Error(`${path}: unexpected response shape: ${parsed.error.message}`)
  }
  return parsed.data
}

/** List the datasets that can be dragged onto instruments. */
export function fetchDatasets(eventId?: string): Promise<Dataset[]> {
  return getJson(`${eventBase(eventId)}/datasets`, z.array(DatasetSchema))
}

/** List the band's instruments. */
export function fetchInstruments(): Promise<Instrument[]> {
  return getJson('/api/instruments', z.array(InstrumentSchema))
}

/** Fetch the IR series for a dataset (drives the chart). */
export function fetchIR(datasetId: string, eventId?: string): Promise<IRSeries> {
  if (datasetId === '') throw new Error('datasetId is required')
  return getJson(`${eventBase(eventId)}/datasets/${encodeURIComponent(datasetId)}/ir`, IRSeriesSchema)
}

/** URL of the rendered .mid file for a dataset on an instrument (also used for download). */
export function midiUrl(datasetId: string, instrumentId: string, eventId?: string): string {
  if (datasetId === '' || instrumentId === '') throw new Error('both ids are required')
  const query = new URLSearchParams({ dataset_id: datasetId, instrument_id: instrumentId })
  return `${API_BASE_URL}${eventBase(eventId)}/midi?${query.toString()}`
}

/** Fetch and parse the .mid file for a dataset on an instrument. */
export async function fetchMidi(datasetId: string, instrumentId: string, eventId?: string): Promise<Midi> {
  const path = midiUrl(datasetId, instrumentId, eventId).slice(API_BASE_URL.length)
  const response = await request(path)
  const midi = new Midi(await response.arrayBuffer())
  if (midi.tracks.length === 0) throw new Error(`${path}: MIDI file has no tracks`)
  return midi
}

const EventSchema = z.object({
  id: z.string(), name: z.string(), start: z.string(), end: z.string(), symbol: z.string(),
})
export type MarketEvent = z.infer<typeof EventSchema>
export function fetchEvents(): Promise<MarketEvent[]> {
  return getJson('/api/events', z.array(EventSchema))
}
function eventBase(eventId?: string): string {
  return eventId ? `/api/events/${encodeURIComponent(eventId)}` : '/api'
}
