# Song algorithm: design

## Intent

The band sounds mechanical: every note the same length, melodies that creep, a bass stuck on one
note, a dry mix. Make it sound like a song while the data still decides the music. Nothing is
forced outright: no fixed chord progression and no fixed song form. The only fixed things are the
key (C major), the pool of six chords, the tempo and the 16-bar length.

Each stock chooses its own chords, so instruments carrying stocks that move together agree and
instruments carrying stocks that diverge clash. That is the project's headline idea ("hear how
assets move together"), produced by the data with no correlation maths.

## Goals

1. Melody notes vary in length, driven by the stock.
2. Melody has real jumps, not only repeats and neighbour steps.
3. Bass never sits on one note for long.
4. A produced sound: EQ, reverb, light filtering, controlled master level.
5. Ornaments (grace notes, mordents, trills, short runs) on the lead synth and the guitar.
6. Two new chord instruments: a strummed acoustic guitar and a second synth playing large chords.

## Non-goals

Band-level correlation maths; any song form (`ABAB CBAB` is dropped); 2008 data, scenarios and
captions; the raw/musical slider; changing how the drums choose their hits; the teammate's
`legacy/` scripts; datasets much longer than the song (see "Time grid").

## Anti-goals

- Randomness that changes between loads. The same data must always give the same song.
- Notes outside C major.
- A fixed progression or form sneaking back in as a "default".
- Low-end mud from bass, guitar and the second synth's low root sounding together.

## Approaches (how the data picks chords)

1. **Bar return picks a chord on a bright-to-dark line, per stock (chosen).** Tested on the five
   Q1 2020 stocks over 16 bars with a fixed +/-6% scale: SPY and AAPL sit 0.8 steps apart on the
   line before the crash and 0.2 during it; SPY and TLT go from 0.5 to 2.0; SPY and GLD from 0.8
   to 1.8. Chords change on 9 to 12 of 15 bar lines. Steps on the line are a stand-in for clash
   and have not been checked by ear.
2. Price level picks the chord root. Rejected: two stocks would clash because of where each sits
   in its own range, not because they move differently.
3. One chord for the whole band from the average of all stocks. Rejected: always clean, but it
   hides disagreement between stocks, and rendering would need to know the whole band.

## Decided

### Time grid

- A song is 16 bars of 4 beats: 64 beats at 120 bpm, a 32 s loop. `SONG_BARS` and
  `BEATS_PER_BAR` live in backend config.
- The IR adapter resamples each dataset onto exactly 64 beats (linear interpolation of log
  adjusted close, daily range and volume; each beat keeps the nearest source date). Q1 2020 is 62
  days, so a beat is still about a day.
- Every rendered part is exactly 64 beats long, wherever its last note ends. The frontend loop
  must not depend on the last note.
- Guard: a dataset with more rows than 2 x the beat count raises a clear error. Squeezing a long
  window properly means aggregating (max high, summed volume), which is out of scope.

### IR (one row per beat, one row per bar; all values in [0, 1])

| Channel | Per | From the stock | Scale |
|---|---|---|---|
| `level` | beat | min-max of log adjusted close (unchanged; also draws the sparkline) | per stock |
| `swing` | beat | log close minus its trailing 5-beat mean, ranked | per stock |
| `activity` | beat | daily range (high - low) / close; 1.0 at `ACTIVITY_RANGE_CAP` (start 6%) | fixed |
| `intensity` | beat | volume / the stock's median volume; 1.0 at `INTENSITY_VOLUME_CAP` (start 3x) | fixed |
| `mood` | bar | log return over the bar; 0 at -`MOOD_RETURN_BOUND`, 1 at + (start 6%) | fixed |

Pitch channels are per stock so every stock gets a full melody; rhythm, loudness and mood use
fixed scales so a calm stock sounds calm next to a wild one. `IRSeries` gains `bars`. The
frontend zod schema mirrors the change. The IR stays source-agnostic.

### Harmony

- Key: C major. Chord line, bright to dark: IV, I, V, ii, vi, iii (the six diatonic triads in
  stacked-fifths order). Chord for a bar = `line[min(int((1 - mood) * 6), 5)]`.
- Every instrument takes its chords from the stock dragged onto it. Rendering stays per
  instrument; the API shape does not change.
- Note pool for a bar: the chord's notes on beats 1 and 3; the chord's notes plus C major
  pentatonic on beats 2 and 4 and on any subdivision.

### Parts

Each instrument has a `role` in backend config that selects its renderer.

- **Lead synth (`lead`).**
  - Pitch: `position = clip(smoothed level + (swing - 0.5) * MELODY_SWING_WEIGHT, 0, 1)`, with
    level smoothed over 5 beats. Map position across the instrument's range and snap to the
    nearest note in the bar's pool. The smoothed level keeps the chart's shape (a crash
    descends); swing supplies the jumps.
  - Lengths: `activity` picks a rhythm pattern per beat (hold; two halves; dotted; four quarters).
    Extra notes inside a beat walk through the pool toward the next beat's pitch instead of
    repeating. A calm beat on the same pitch as the note before it extends that note, up to 4
    beats.
- **Bass (`bass`).** Works around the root of its stock's chord: root on beat 1; `swing` moves it
  to the fifth or octave on other beats; `activity` picks one or two notes per beat, with calm
  beats tied into longer notes; a scale step into the next root on beat 4 when the chord
  changes. `BASS_MAX_REPEATS` (start 3) caps consecutive notes on one pitch; at the cap it moves
  to the next chord note.
- **Second synth (`pad`).** One voicing per bar, built up from a low root in octave 2: root,
  octave above, fifth above that, root again (a fourth above), then the triad's third on top.
  C major: C2 C3 G3 C4 E4. A minor: A2 A3 E4 A4 C5. `activity` sets how often the chord is
  re-struck within the bar (once, twice, every beat); `intensity` sets velocity.
- **Acoustic guitar (`guitar`).** Five- or six-note voicing of the bar's chord in guitar range.
  Strums are written into the MIDI: note starts staggered by `STRUM_GAP_BEATS`, low to high on
  downstrokes, high to low and thinner on upstrokes. `activity` picks the pattern (one ringing
  downstroke; a downstroke per beat; down-up eighths); `intensity` sets velocity.
- **Drums.** Unchanged logic. They now follow the fixed-scale `activity`, so they thin out in calm
  stretches and fill in during busy ones.

### Ornaments (lead synth and guitar)

- Where: on beats where `activity` is at or above `ORNAMENT_TRIGGER`, at least
  `ORNAMENT_MIN_GAP_BEATS` after the previous one. Placement comes from the data, so ornaments
  mark the busy days.
- Which: chosen by a random generator seeded from a stable hash of source and instrument (not
  Python's `hash()`, which changes per process). Lead: grace note, mordent, trill, or a short run
  into the next beat's note. Guitar: a rolled (arpeggiated) chord or a hammer-on into the top
  note, replacing that beat's strum. All notes come from the bar's pool.

### Sound (frontend, Tone.js, all values in `config.ts`)

- Each instrument gets its own channel: high-pass (off for kick and bass), 3-band EQ, then a dry
  path and a send to one shared reverb. Master: gentle compressor, then a limiter.
- The existing per-note low-pass (velocity sets brightness) stays.
- The second synth's low root is kept, with EQ carving space between it, the bass and the guitar.

### New stage pieces and samples

- Two new pieces in the stage SVG with their own art, outlines and tags: an acoustic guitar and
  a second synth. Outlines must not overlap existing pieces.
- Samples, self-hosted from the same Musyng Kite source as the existing ones, credited in
  `public/soundfonts/README.md`: steel-string acoustic guitar; warm pad.

### Success criteria

Measured on the five demo stocks unless stated:

- Lead: at most 30% of consecutive notes repeat the previous pitch; 20% to 50% move by two or
  more pool steps; at least three distinct note lengths per stock. (Today: 36-66% repeats,
  10-18% jumps, one length per beat pattern.)
- Bass: never more than `BASS_MAX_REPEATS` consecutive notes on one pitch.
- Second synth: every chord is exactly root, +12, +19, +24, +27 or +28 semitones.
- Every part is 64 beats; every note is in C major and inside its instrument's range.
- Rendering the same stock and instrument twice gives identical bytes.
- Backend: pytest, ruff and mypy strict clean. Frontend: oxlint and `tsc` clean.
- Final judge is Will's ears. None of the above proves it sounds good.

### Build order (each step is audible on its own)

1. Sound: channels, EQ, reverb, master compressor and limiter.
2. Time grid and IR: 64 beats, `swing`, `mood`, fixed-scale `activity` and `intensity`.
3. Harmony and lead: chords per bar, new pitch rule, note lengths.
4. Bass.
5. Second synth and guitar: renderers, stage pieces, samples.
6. Ornaments.

Update the project `CLAUDE.md` "Approach" section when the mapping changes.

## Left to the builder

- Module split of the backend algorithm (suggested: harmony, one module per role, ornaments,
  MIDI encoding, a thin dispatcher).
- Exact rhythm patterns, activity thresholds, guitar voicings, strum gap, ornament shapes.
- Starting values for every tunable named above; all go in config and are tuned by ear.
- EQ, reverb and compressor settings; stage geometry and art for the two new pieces.
- How the frontend learns the 64-beat loop length (for example an end-of-track marker at beat 64).
