/** Ignore setup-only parser tracks, but never silently mix two musical parts. */
export function normalisePlayableMidi(midi) {
  const parsedCount = midi.tracks.length
  const playable = midi.tracks.filter(track => track.notes.length > 0)
  if (playable.length !== 1) {
    throw new Error(`Expected one note-bearing instrument part; found ${playable.length} in ${parsedCount} parsed tracks`)
  }
  midi.tracks = playable
  return midi
}
