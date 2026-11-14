/**
 * Loads the friend's pre-rendered arrangements (Market_Events_to_MIDI.py output, copied into
 * public/songs/) and splits each multi-track MIDI file into one Part per band instrument.
 * Named tracks are routed by SONG_TRACK_ROUTES; the General MIDI drum track is split by note.
 */

import { Midi, type Track } from '@tonejs/midi'
import type { Instrument } from './api'
import type { Part, PartNote } from './audio/band'
import { SONG_DRUM_NOTES, SONG_DRUM_TRACK, SONG_TRACK_ROUTES, SONGS_BASE_URL } from './config'

/** Fetch and parse one song by id. */
export async function fetchSong(songId: string): Promise<Midi> {
  if (songId === '') throw new Error('songId is required')
  const url = `${SONGS_BASE_URL}${encodeURIComponent(songId)}.mid`
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${url} -> HTTP ${response.status}`)
  const midi = new Midi(await response.arrayBuffer())
  if (midi.tracks.length === 0) throw new Error(`${url}: MIDI file has no tracks`)
  return midi
}

/** Append a note to an instrument's list, creating the list on first use. */
function addNote(notesBy: Map<string, PartNote[]>, instrumentId: string, note: PartNote): void {
  const notes = notesBy.get(instrumentId)
  if (notes === undefined) notesBy.set(instrumentId, [note])
  else notes.push(note)
}

/** Look up an instrument's root note, failing loudly if the band has no such instrument. */
function rootOf(roots: ReadonlyMap<string, number>, instrumentId: string): number {
  const root = roots.get(instrumentId)
  if (root === undefined) throw new Error(`song needs instrument '${instrumentId}', not in the band`)
  return root
}

/**
 * Split drum hits into kick / snare / hi-hat. Each hit is moved to its drum's root note, because
 * the drum voices retune by distance from the root and these hits should sound untransposed.
 */
function routeDrums(track: Track, roots: ReadonlyMap<string, number>, notesBy: Map<string, PartNote[]>): void {
  assertNonEmpty(track)
  for (const note of track.notes) {
    const drumId = SONG_DRUM_NOTES[note.midi]
    if (drumId === undefined) throw new Error(`drum note ${note.midi} has no drum voice`)
    const midi = rootOf(roots, drumId)
    addNote(notesBy, drumId, { ticks: note.ticks, durationTicks: note.durationTicks, midi, velocity: note.velocity })
  }
}

/** Guard: only tracks with notes are routed. */
function assertNonEmpty(track: Track): void {
  if (track.notes.length === 0) throw new Error(`track '${track.name}' has no notes to route`)
}

/** Split a song into one Part per instrument that plays in it. */
export function splitSong(midi: Midi, instruments: readonly Instrument[]): Map<string, Part> {
  const tempo = midi.header.tempos[0]
  if (tempo === undefined) throw new Error('song has no tempo')
  if (instruments.length === 0) throw new Error('cannot split a song for an empty band')
  const roots: ReadonlyMap<string, number> = new Map(instruments.map((i) => [i.id, i.root_midi]))
  const notesBy = new Map<string, PartNote[]>()
  for (const track of midi.tracks) {
    if (track.notes.length === 0) continue // tempo/conductor track
    if (track.name === SONG_DRUM_TRACK) {
      routeDrums(track, roots, notesBy)
      continue
    }
    const instrumentId = SONG_TRACK_ROUTES[track.name]
    if (instrumentId === undefined) throw new Error(`song track '${track.name}' has no instrument`)
    rootOf(roots, instrumentId) // guard: the instrument must exist in the band
    track.notes.forEach((note) => addNote(notesBy, instrumentId, note))
  }
  const { bpm } = tempo
  const { ppq } = midi.header
  return new Map([...notesBy].map(([id, notes]) => [id, { bpm, ppq, notes }]))
}
