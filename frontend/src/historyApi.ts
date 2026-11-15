import { Midi } from '@tonejs/midi'
import { z } from 'zod'
import { API_BASE_URL } from './config'
import { normalisePlayableMidi } from './audio/playableMidi.js'

const DatasetSchema = z.object({
  id: z.string(), ticker: z.string(), name: z.string(), period: z.string(),
  period_id: z.string(), simulated_fraction: z.number().min(0).max(1),
  run: z.string(), calibration_pairs: z.union([z.string(), z.number()]).nullish(),
})
const PeriodSchema = z.object({
  id: z.string(), name: z.string(), kind: z.string(), market: z.string(),
  start: z.string(), end: z.string(), available: z.number(), expected: z.number(), complete: z.boolean(),
})
const CatalogueSchema = z.object({
  periods: z.array(PeriodSchema), datasets: z.array(DatasetSchema),
  diagnostics: z.object({
    scanned_manifests: z.number(), issues: z.array(z.string()), message: z.string(),
    previous_run_issues: z.array(z.string()).optional(),
  }),
})
const InstrumentSchema = z.object({ id: z.string(), name: z.string(), root_midi: z.number().int(), octaves: z.number().int() })
const IRSchema = z.object({ source: z.string(), beats: z.array(z.object({
  date: z.string(), level: z.number().min(0).max(1), activity: z.number().min(0).max(1), intensity: z.number().min(0).max(1),
})).min(1) })
export type Dataset = z.infer<typeof DatasetSchema>
export type Catalogue = z.infer<typeof CatalogueSchema>
export type Instrument = z.infer<typeof InstrumentSchema>
export type IRSeries = z.infer<typeof IRSchema>
async function request(path: string): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}/api/history${path}`)
  if (!response.ok) throw new Error(`Historical API ${response.status}: ${await response.text()}`)
  return response
}
export async function fetchCatalogue(): Promise<Catalogue> {
  const data = CatalogueSchema.parse(await (await request('/catalogue')).json())
  const available = new Set(data.datasets.map(d => `${d.period_id}/${d.ticker}`))
  const current: string[] = []
  const previous = [...(data.diagnostics.previous_run_issues ?? [])]
  for (const issue of data.diagnostics.issues) {
    const separator = issue.indexOf(': ')
    const pair = separator < 0 ? '' : issue.slice(0, separator)
    if (available.has(pair)) previous.push(issue)
    else current.push(issue)
  }
  data.diagnostics.issues = current
  data.diagnostics.previous_run_issues = [...new Set(previous)]
  if (previous.length > 0) {
    data.diagnostics.message += ` ${data.diagnostics.previous_run_issues.length} stored reports from other attempts have an available playable replacement; they are not current missing-asset errors. Original reports remain in /api/history/catalogue and generation manifests. This does not certify historical OHLC quality.`
  }
  return data
}
export async function fetchInstruments(): Promise<Instrument[]> {
  return z.array(InstrumentSchema).parse(await (await request('/instruments')).json())
}
export async function fetchIR(id: string): Promise<IRSeries> {
  return IRSchema.parse(await (await request(`/datasets/${encodeURIComponent(id)}/ir`)).json())
}
export async function fetchMidi(dataset: string, instrument: string): Promise<Midi> {
  const query = new URLSearchParams({ dataset_id: dataset, instrument_id: instrument })
  const midi = new Midi(await (await request(`/midi?${query.toString()}`)).arrayBuffer())
  return normalisePlayableMidi(midi)
}
