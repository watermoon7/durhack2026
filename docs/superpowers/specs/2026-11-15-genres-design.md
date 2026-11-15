# Genres: design

## Intent

A dropdown on the stage picks the band's genre. Two genres for now, more later:

- **Default**: today's band, unchanged.
- **Rock**: distorted guitar playing power chords, pick bass, rock organ in place of the pad
  synth, LinnDrum (LM-2) drums with a crash after busy bars and tom fills on busy beats.

The stage art stays the same for every genre (Will's decision): no new drawings.

## Goals

1. One dropdown, top-left of the stage, listing every genre; Default is selected on load.
2. Changing genre while playing re-renders every assigned part and swaps the sounds without
   stopping the transport. A short silence while new samples load is acceptable.
3. Adding a genre later is one entry in backend config plus one in frontend config.

## Non-goals

New stage art; per-genre tempo or song form; genre-specific melody or bass rules; a rock lead
sound (the synth piece keeps its current sound in Rock).

## Anti-goals

- Anything fetched from the internet during the demo: LM-2 samples are self-hosted like TR-808.
- A genre that silently falls back to Default sounds (a missing preset must fail loudly).
- Default changing in any way: its MIDI must stay byte-identical to today's.

## Approaches

1. **Backend writes the parts per genre, frontend picks the sounds per genre (chosen).** Power
   chords and drum fills change the notes, so the backend must know the genre; the sounds are
   samples, which only the frontend loads.
2. Frontend-only genre (swap samples, same MIDI). Rejected: no power chords, crashes or toms,
   which Will approved as part of Rock.
3. Backend also owns the sound names and serves them. Rejected: sounds are a frontend concern
   today (CLAUDE.md: ranges in the backend, sounds in the frontend); moving them is churn.

## Decided

### Backend

- `GenreConfig(id, name)` in config; `GENRES = (default "Default", rock "Rock")`.
- `GET /api/genres` lists them. `GET /api/midi` gains `genre` (default `"default"`; unknown -> 404).
- `render_notes(ir, instrument, genre)`; the genre changes only:
  - **guitar**: Rock voices power chords: root, fifth, octave (`r, r + 7, r + 12`, root in the
    octave from E2). Strum patterns and ornaments unchanged.
  - **snare piece**: Rock adds a tom fill on beat 4 of a bar when that beat's activity is at or
    above `ORNAMENT_TRIGGER`: four sixteenths, high tom to low tom, replacing the snare hits.
  - **hi-hat piece**: Rock adds a crash on beat 1 of a bar when the previous bar's mean activity
    is at or above `ORNAMENT_TRIGGER`, on top of the hi-hat hits.
  - Everything else, and all of Default, is unchanged.
- Drum accents use General MIDI note numbers (crash 49; toms 50, 48, 47, 45), outside the drum
  tuning ranges. The key-and-range test exempts these accent notes on drum parts.

### Frontend

- Sound and mix presets become per genre: `GENRE_SOUNDS[genre][instrument]` and
  `GENRE_MIX[genre][instrument]`. Default holds today's values exactly.
- Rock sounds: guitar `distortion_guitar`, bass `electric_bass_pick`, pad `rock_organ`, synth and
  drums as below; Musyng Kite, self-hosted, credited in the samples README.
- Drum presets gain an accent map from MIDI note to sample name; an accent plays its own sample
  untuned, every other note plays the main sample with the existing tuning. Rock drums use LM-2:
  kick `kick`, snare `snare-m`, hi-hat `hhclosed`, accents `crash`, `tom-hh`, `tom-h`, `tom-m`,
  `tom-l`. The LM-2 manifest is trimmed to these, like TR-808's.
- The genre list comes from `/api/genres`; a genre with no frontend preset fails loudly.
- The dropdown is a native `<select>` (keyboard accessible), styled to the stage palette.

### Success criteria

- Default MIDI for every instrument and demo stock is byte-identical before and after.
- Rock guitar chords are exactly `(0, 7, 12)` above their root; Rock drum parts contain crashes
  and toms only where the rules above say.
- Switching genre while playing: no console errors, every assigned piece keeps its stock, the
  loop stays 64 beats, notes keep sounding after the new samples load.
- No request leaves localhost while the app runs (checked in the browser).
- pytest, ruff, mypy, oxlint and the build clean.

## Left to the builder

Exact Rock mix values (start: guitar high-pass 120 Hz, low -3, mid +2, send 0.10; organ send
0.25; drums dry), dropdown styling and position details, how the band swaps voices in place.
