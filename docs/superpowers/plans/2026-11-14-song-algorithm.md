# Song Algorithm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each stock's part sound like a song (varied note lengths, melodic jumps, a moving bass, strummed guitar and big synth chords, ornaments, a produced mix) while the data still chooses every chord and note.

**Architecture:** The IR adapter resamples each dataset onto a 64-beat grid and adds `swing` (per beat) and `mood` (per bar). `mood` picks one of six C-major chords per bar, per stock. Each instrument has a `role` that selects a renderer (drum, lead, bass, pad, guitar); all renderers return `Note` lists encoded by the existing MIDI writer. The frontend routes each instrument through its own EQ/reverb channel into a compressed, limited master.

**Tech Stack:** Python 3.13 / FastAPI / pandas / mido / pytest; Vite + React 19 + TS strict + Tone.js 15 + smplr 1.1 + zod.

**Spec:** `docs/superpowers/specs/2026-11-14-song-algorithm-design.md`

## Global Constraints

- Key C major only. Chord pool, bright to dark: IV, I, V, ii, vi, iii. No fixed progression, no song form.
- Song = 16 bars x 4 beats = 64 beats at 120 bpm. Every rendered part is exactly 64 beats.
- Same stock + same instrument = identical MIDI bytes on every render. No `hash()`, no unseeded randomness.
- Pitch channels (`level`, `swing`) are scaled per stock; `activity`, `intensity`, `mood` use fixed scales.
- All tunables in `backend/src/market_band/config.py` / `frontend/src/config.ts`. Nothing fetched from the internet at runtime; samples are self-hosted.
- Zero warnings: `uv run pytest && uv run ruff check . && uv run mypy src tests`; `npm run lint && npm run build`.
- No new tooling: the frontend has no test runner, so frontend tasks are verified by lint, build and a browser run.
- Functions under 60 lines, at least two guards in non-trivial functions, docstrings everywhere.

## Review Focus

- Same-pitch notes that overlap (a ringing strum under the next strum, a tied note under a re-strike): the earlier note-off must not cut the later note. Pinned in Task 5.
- A flat stock (constant price, zero volume): must give a valid neutral song, not NaN or a divide-by-zero. Pinned in Task 2 and Task 7.
- A dataset shorter than 64 rows is stretched; one longer than 128 rows fails with a clear message. Pinned in Task 2.
- An instrument id with no mix preset or sound preset: fails loudly at band creation, not silently dry. Pinned in Task 1.
- The loop seam: the last beat's run leads into beat 1, and a second drop on a playing instrument keeps the loop at 64 beats. Pinned in Task 3 (wrap) and Task 2 (browser check).

---

### Task 1: Mix (EQ, reverb, master compressor and limiter)

**Files:** Create `frontend/src/audio/mix.ts`. Modify `frontend/src/audio/band.ts`, `frontend/src/config.ts`.

**Interfaces:**
- Produces (`config.ts`):
  ```ts
  export interface MixPreset {
    readonly highpassHz: number // 0 = no high-pass
    readonly eqDb: { readonly low: number; readonly mid: number; readonly high: number }
    readonly reverbSend: number // 0-1
  }
  export const MIX_PRESETS: Readonly<Record<string, MixPreset>> // keyed by instrument id
  export const REVERB_DECAY_S = 2.2
  export const COMPRESSOR = { thresholdDb: -18, ratio: 3 } as const
  export const LIMITER_DB = -1
  ```
  Starting presets (highpassHz, low/mid/high dB, send): kick 0, +2/0/0, 0.02; snare 120, 0/0/+1, 0.15; hihat 400, 0/0/+1, 0.08; synth 150, -2/0/+2, 0.30; bass 0, +1/-1/-2, 0.03.
- Produces (`mix.ts`):
  ```ts
  export interface Mix { readonly ready: Promise<void>; input(instrumentId: string): AudioNode; dispose(): void }
  export function createMix(context: AudioContext, instrumentIds: readonly string[], masterVolumeDb: number): Mix
  ```

- [ ] Implement `createMix`. Per instrument: native `GainNode` input -> `Tone.Filter` high-pass (skipped when `highpassHz` is 0) -> `Tone.EQ3` -> master bus, and `Tone.EQ3` -> `Tone.Gain(reverbSend)` -> one shared `Tone.Reverb({ decay: REVERB_DECAY_S, wet: 1 })` -> master bus. Master bus -> `Tone.Compressor` -> `Tone.Limiter(LIMITER_DB)` -> `Tone.Volume(masterVolumeDb)` -> destination. `ready` resolves with the reverb's `ready`. It must be called after `Tone.setContext`, since it builds Tone nodes. `createMix` throws `no mix preset for instrument '<id>'` for an id missing from `MIX_PRESETS`; `input()` throws on an unknown id.
- [ ] `band.ts`: replace the `master`/`bus` pair with `createMix(context, ids, MASTER_VOLUME_DB)`; each voice's destination is `mix.input(instrument.id)`; `ready` also awaits `mix.ready`; `dispose` calls `mix.dispose()`.
- [ ] `npm run lint && npm run build` -> clean.
- [ ] Browser run: drop SPY on all five pieces, press play, wait 6 s. Expect: no console errors, no toast, pieces light up. Re-measure the master peak with the full band and update the `MASTER_VOLUME_DB` comment.
- [ ] Commit.

### Task 2: 64-beat grid and the new IR

**Files:** Modify `backend/src/market_band/config.py`, `ir.py`, `algorithm.py`, `backend/tests/test_pipeline.py`, `frontend/src/api.ts`, `frontend/src/audio/band.ts`. Create `backend/tests/helpers.py`, `backend/tests/test_song.py`.

**Interfaces:**
- Produces (`config.py`): `SONG_BARS = 16`, `BEATS_PER_BAR = 4`, `SONG_BEATS = 64`, `MAX_RESAMPLE_RATIO = 2.0`, `SWING_WINDOW_BEATS = 5`, `ACTIVITY_RANGE_CAP = 0.09`, `INTENSITY_VOLUME_CAP = 3.0`, `MOOD_RETURN_BOUND = 0.06`.
  (The spec's starting cap for activity was 6% linear. Measured ranges on the demo stocks run from 0.4% to 22%, so this plan uses a square-root curve with a 9% cap for better resolution on calm days. Still a fixed scale.)
- Produces (`ir.py`):
  ```python
  class IRBeat(BaseModel): date: str; level: float; swing: float; activity: float; intensity: float  # all [0, 1]
  class IRBar(BaseModel): mood: float  # [0, 1], 0 = dark, 1 = bright
  class IRSeries(BaseModel): source: str; beats: list[IRBeat]; bars: list[IRBar]
  def resample_frame(frame: pd.DataFrame, beats: int) -> pd.DataFrame  # columns date, log_close, range, volume
  def stock_to_ir(source: str, frame: pd.DataFrame, beats: int = SONG_BEATS) -> IRSeries
  ```
- Produces (`algorithm.py`): `notes_to_midi(notes: list[Note], track_name: str, beats: int = SONG_BEATS) -> bytes`, with `end_of_track` at tick `beats * TICKS_PER_BEAT`. `render_midi` passes `beats=len(ir.beats)`. Every renderer, here and in later tasks, takes its length from `len(ir.beats)` and `len(ir.bars)`, never from `SONG_BEATS`, so short test IRs work.
- Produces (`tests/helpers.py`): `make_frame(closes, volumes) -> pd.DataFrame` (moved from `test_pipeline.py`); `ir_with_activity(values: list[float]) -> IRSeries` (one beat per value, `level`, `swing`, `intensity` and every bar's `mood` at 0.5).
- Formulas: `resample_frame` interpolates linearly at `linspace(0, rows - 1, beats)`; `date` is the nearest row. `level = min_max(log_close)`. `swing = percentile_rank(round(log_close - log_close.rolling(SWING_WINDOW_BEATS, min_periods=1).mean(), 9))` (rounded so float noise on a flat series still ranks as flat). `activity = sqrt(clip(range / ACTIVITY_RANGE_CAP, 0, 1))`. `intensity = clip(volume / median(volume) / INTENSITY_VOLUME_CAP, 0, 1)`, or `NEUTRAL` when the median is 0. Bar return `r = log_close[last beat of bar] - log_close[last beat of previous bar]` (bar 0 starts at its own first beat); `mood = clip(r / MOOD_RETURN_BOUND, -1, 1) / 2 + 0.5`.

- [ ] Write failing tests in `test_song.py`:
  ```python
  def test_demo_ir_is_64_beats_16_bars():  # for every DATASETS entry, via api.build_ir
      assert len(ir.beats) == 64 and len(ir.bars) == 16
      assert all(0.0 <= v <= 1.0 for b in ir.beats for v in (b.level, b.swing, b.activity, b.intensity))
  def test_mood_follows_bar_return():
      ir = stock_to_ir("T", make_frame([100, 100, 100, 100, 100, 90, 80, 70], [1] * 8), beats=8)
      assert [b.mood for b in ir.bars] == [0.5, 0.0]
  def test_activity_and_intensity_use_fixed_scales():
      ir = stock_to_ir("T", make_frame([100, 100, 100, 100], [10, 10, 10, 40]), beats=4)
      assert ir.beats[0].activity == pytest.approx((0.02 / 0.09) ** 0.5)  # make_frame range is 2%
      assert [b.intensity for b in ir.beats] == pytest.approx([1 / 3, 1 / 3, 1 / 3, 1.0])
  def test_flat_stock_is_neutral_not_nan():
      ir = stock_to_ir("T", make_frame([50.0] * 10, [0.0] * 10))
      assert len(ir.beats) == 64 and all(b.level == b.swing == b.intensity == 0.5 for b in ir.beats)
      assert all(b.mood == 0.5 for b in ir.bars)
  def test_too_long_dataset_is_rejected():
      with pytest.raises(ValueError, match="rows"): stock_to_ir("T", make_frame([100.0] * 9, [1.0] * 9), beats=4)
  def test_beats_must_fill_whole_bars():
      with pytest.raises(ValueError, match="bar"): stock_to_ir("T", make_frame([100.0] * 6, [1.0] * 6), beats=6)
  def test_midi_is_exactly_song_length():  # for every INSTRUMENTS entry on dataset spy
      track = mido.MidiFile(file=io.BytesIO(render_midi(ir, instrument))).tracks[0]
      assert sum(m.time for m in track) == SONG_BEATS * TICKS_PER_BEAT
  ```
- [ ] Run -> fail. Implement. Rewrite `test_ir_channels_are_normalised_and_level_follows_price` in `test_pipeline.py` to pass `beats=4` and assert only `level` (`levels[2] == 0.0`, `levels[1] == 1.0`); `notes_to_midi` raises `ValueError` when a note ends after `beats`.
- [ ] Frontend: `IRBeatSchema` gains `swing`; `IRSeriesSchema` gains `bars: z.array(z.object({ mood: z.number().min(0).max(1) }))`. In `band.ts` `load`, loop length = `Math.ceil((track.endOfTrackTicks ?? lastTick) / midi.header.ppq)`.
- [ ] Backend checks and frontend lint/build -> clean.
- [ ] Browser run: drop SPY on the synth, press play, then drop AAPL on the same synth while playing. Expect the progress ring to complete one lap in 32 s both times and no doubled notes.
- [ ] Commit.

### Task 3: Harmony and the lead

**Files:** Create `backend/src/market_band/notes.py`, `harmony.py`, `lead.py`. Modify `algorithm.py`, `config.py`, `tests/test_song.py`, `tests/test_pipeline.py` (imports only).

**Interfaces:**
- Consumes: `IRSeries`, `SONG_BEATS`, `BEATS_PER_BAR` (Task 2).
- Produces (`config.py`): `Role = Literal["drum", "lead", "bass", "pad", "guitar"]`; `InstrumentConfig(id, name, root_midi, octaves, role: Role, subdivisions: tuple[int, ...] = (), offset_beats: float = 0.0)`; kick/snare/hihat `role="drum"`, synth `role="lead"`, bass `role="bass"`; `MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)`; `CHORD_LINE = (3, 0, 4, 1, 5, 2)` (scale degrees of the roots of IV, I, V, ii, vi, iii); `LEVEL_SMOOTH_BEATS = 5`; `MELODY_SWING_WEIGHT = 0.6`; `LEAD_PATTERNS = ((1.0,), (0.5, 0.5), (0.75, 0.25), (0.25, 0.25, 0.25, 0.25))`; `MAX_TIE_BEATS = 4`.
- Produces (`notes.py`): `Note` and `intensity_to_velocity` moved here unchanged (`algorithm.py` re-imports them).
- Produces (`harmony.py`):
  ```python
  @dataclass(frozen=True)
  class Chord: degree: int; pitch_classes: tuple[int, int, int]; minor: bool  # root, third, fifth
  def chord_for_mood(mood: float) -> Chord            # CHORD_LINE[min(int((1 - mood) * 6), 5)]
  def bar_chords(ir: IRSeries) -> tuple[Chord, ...]   # one per bar
  def pool_notes(chord: Chord, low: int, high: int, strong: bool) -> tuple[int, ...]  # ascending MIDI notes
  def nearest_note(pool: tuple[int, ...], target: float) -> int  # ties resolve downward
  ```
- Produces (`lead.py`): `lead_pitches(ir, instrument) -> list[int]` (one per beat); `render_lead(ir, instrument) -> list[Note]`.
- Produces (`algorithm.py`): `render_notes(ir: IRSeries, instrument: InstrumentConfig) -> list[Note]` dispatching on `instrument.role`; `drum` uses the existing `ir_to_notes`; `bass`, `pad`, `guitar` fall back to `ir_to_notes` until their tasks land. `render_midi` calls `render_notes`.

- [ ] Write failing tests:
  ```python
  def test_mood_picks_chords_on_the_bright_to_dark_line():
      assert chord_for_mood(1.0) == Chord(3, (5, 9, 0), False)   # IV
      assert chord_for_mood(0.51) == Chord(4, (7, 11, 2), False)  # V
      assert chord_for_mood(0.5) == Chord(1, (2, 5, 9), True)    # ii
      assert chord_for_mood(0.0) == Chord(2, (4, 7, 11), True)   # iii
  def test_pool_is_chord_on_strong_beats_and_adds_pentatonic_on_weak():
      one = chord_for_mood(0.75)  # I
      assert pool_notes(one, 60, 72, strong=True) == (60, 64, 67, 72)
      assert pool_notes(one, 60, 72, strong=False) == (60, 62, 64, 67, 69, 72)
  @pytest.mark.parametrize("dataset", DATASETS)
  def test_lead_moves_like_a_melody(dataset):
      notes = render_notes(build_ir(dataset.id), LEAD)
      moves = [abs(b.midi - a.midi) for a, b in zip(notes, notes[1:])]
      assert sum(m == 0 for m in moves) / len(moves) <= 0.30
      assert 0.20 <= sum(m >= 4 for m in moves) / len(moves) <= 0.50   # 4+ semitones = two pool steps
      assert len({round(n.duration_beats, 3) for n in notes}) >= 3
  def test_lead_stays_in_key_range_and_song(dataset):  # parametrized as above
      assert all(n.midi % 12 in MAJOR_SCALE and LEAD.root_midi <= n.midi <= LEAD.root_midi + 12 * LEAD.octaves for n in notes)
      assert max(n.start_beat + n.duration_beats for n in notes) <= SONG_BEATS
  def test_render_is_deterministic():  # every instrument, dataset spy
      assert render_midi(ir, instrument) == render_midi(ir, instrument)
  ```
- [ ] Run -> fail. Implement `harmony.py` and `notes.py`. The `KEYS` and `bad` fixtures in `test_pipeline.py` gain `role="drum"`; `LEAD`, `BASS`, `PAD`, `GUITAR` in `test_song.py` are looked up from `INSTRUMENTS` by id (`synth`, `bass`, `pad`, `guitar`).
- [ ] Implement `lead.py`:
  1. `smooth` = centred rolling mean of `level` over `LEVEL_SMOOTH_BEATS` (`min_periods=1`). `position = clip(smooth + (swing - 0.5) * MELODY_SWING_WEIGHT, 0, 1)`; `target = low + position * (high - low)` over the instrument's range.
  2. Beat pitch = `nearest_note(pool, target)`, pool strong on bar beats 1 and 3.
  3. Pattern = `LEAD_PATTERNS[min(int(activity * 4), 3)]`. A `(1.0,)` beat on the same pitch as the note before it, when that note is under `MAX_TIE_BEATS` long and ends at this beat, extends it by one beat. Otherwise emit the pattern: first note on the beat pitch, each later note one weak-pool step toward the next beat's pitch (beat 64's "next" is beat 1).
  4. Duration = pattern fraction x `NOTE_LEGATO`; velocity from `intensity`.
- [ ] Run. If the three melody thresholds fail, tune `MELODY_SWING_WEIGHT` only. If no single value passes all five stocks after two attempts, stop and report the numbers.
- [ ] Full backend checks -> clean. Browser run: SPY on the synth; listen. Commit.

### Task 4: Bass

**Files:** Create `backend/src/market_band/bass.py`. Modify `algorithm.py` (dispatch), `config.py`, `tests/test_song.py`.

**Interfaces:**
- Consumes: `bar_chords`, `Chord`, `Note`, `intensity_to_velocity`.
- Produces: `BASS_MAX_REPEATS = 3`; `render_bass(ir: IRSeries, instrument: InstrumentConfig) -> list[Note]`.

- [ ] Write failing tests (parametrized over `DATASETS`):
  ```python
  def test_bass_never_repeats_a_pitch_more_than_three_times(dataset):
      run = longest = 1
      for a, b in zip(notes, notes[1:]):
          run = run + 1 if a.midi == b.midi else 1
          longest = max(longest, run)
      assert longest <= BASS_MAX_REPEATS
  def test_bass_opens_each_bar_on_its_chord(dataset):
      for bar, chord in enumerate(bar_chords(ir)):
          at_bar = max((n for n in notes if n.start_beat <= bar * 4), key=lambda n: n.start_beat)
          assert at_bar.midi % 12 in chord.pitch_classes  # a tied note may carry over the bar line
  def test_bass_stays_in_key_and_range(dataset): ...  # as the lead test, with BASS
  ```
- [ ] Run -> fail. Implement:
  - Chord notes: `root` = the chord root's pitch class in `[root_midi, root_midi + 12)`; `fifth = root + 7`; `octave = root + 12`.
  - Bar beat 1: root. Other beats: `swing < 1/3` root, `< 2/3` fifth, else octave. Bar beat 4 before a different chord: the C-major scale note one step below the next bar's root, or one step above when below would leave the instrument's range.
  - `activity >= 0.5`: two eighth notes, the second on the next chord note up (root -> fifth -> octave -> root). `activity < 0.25` on the same pitch as the note before: extend it (up to `MAX_TIE_BEATS`).
  - A note that would be the fourth in a row on one pitch moves to the next chord note up instead.
- [ ] Run -> pass. Full backend checks -> clean. Browser run: SPY on bass and synth; listen. Commit.

### Task 5: Second synth and guitar renderers

**Files:** Create `backend/src/market_band/chords.py`. Modify `notes.py`, `algorithm.py` (dispatch), `config.py`, `tests/test_song.py`.

**Interfaces:**
- Produces (`config.py`): `INSTRUMENTS` gains `InstrumentConfig(id="pad", name="Pad", root_midi=36, octaves=3, role="pad")` and `InstrumentConfig(id="guitar", name="Guitar", root_midi=36, octaves=4, role="guitar")`; `PAD_LOW_MIDI = 36`; `GUITAR_LOW_MIDI = 40`; `STRUM_GAP_BEATS = 0.04`; `UPSTROKE_VELOCITY_SCALE = 0.7`.
- Produces (`notes.py`): `trim_overlaps(notes: list[Note]) -> list[Note]` (a note still sounding when the same pitch starts again is shortened to end at that start).
- Produces (`chords.py`): `pad_voicing(chord: Chord) -> tuple[int, ...]`; `render_pad(ir, instrument) -> list[Note]`; `guitar_voicing(chord: Chord) -> tuple[int, ...]`; `render_guitar(ir, instrument) -> list[Note]`.

- [ ] Write failing tests:
  ```python
  def test_pad_voicing_is_root_octave_fifth_root_third():
      assert pad_voicing(chord_for_mood(0.75)) == (36, 48, 55, 60, 64)   # C major: C2 C3 G3 C4 E4
      assert pad_voicing(chord_for_mood(0.2)) == (45, 57, 64, 69, 72)    # A minor: A2 A3 E4 A4 C5
  def test_every_pad_chord_uses_the_voicing(dataset):  # parametrized
      for start, group in groupby(sorted(notes, key=...), key=lambda n: n.start_beat):
          pitches = sorted(n.midi for n in group)
          assert tuple(p - pitches[0] for p in pitches) in {(0, 12, 19, 24, 27), (0, 12, 19, 24, 28)}
  def test_guitar_voicing_matches_open_chords():
      assert guitar_voicing(chord_for_mood(0.0)) == (40, 47, 52, 55, 59, 64)  # E minor: E B E G B E
      assert guitar_voicing(chord_for_mood(0.75)) == (48, 55, 60, 64, 67, 72)  # C major
  def test_strum_staggers_low_to_high():
      first = sorted(render_guitar(ir_with_activity([0.1] * 8), GUITAR), key=lambda n: n.start_beat)[:6]
      assert [n.midi for n in first] == sorted(n.midi for n in first)
      assert first[1].start_beat - first[0].start_beat == pytest.approx(STRUM_GAP_BEATS)
  def test_no_same_pitch_overlap_in_any_part(dataset):  # every INSTRUMENTS entry
      for pitch notes sorted by start: assert a.start_beat + a.duration_beats <= b.start_beat
  def test_every_part_stays_in_key_and_range(dataset):  # every INSTRUMENTS entry
      assert all(n.midi % 12 in MAJOR_SCALE and i.root_midi <= n.midi <= i.root_midi + 12 * i.octaves for n in notes)
  def test_trim_overlaps_shortens_the_earlier_note():
      assert trim_overlaps([Note(0, 4, 60, 90), Note(2, 1, 60, 90)])[0].duration_beats == 2
  ```
- [ ] Run -> fail. Implement:
  - `pad_voicing`: `r = PAD_LOW_MIDI + root pitch class`; `(r, r + 12, r + 19, r + 24, r + 24 + (3 if minor else 4))`.
  - `render_pad`: per bar, mean `activity` `< 1/3` one strike held 4 beats, `< 2/3` two strikes of 2 beats, else four of 1 beat; velocity from the mean `intensity` of the beats each strike covers; duration x `NOTE_LEGATO`.
  - `guitar_voicing`: `r` = root pitch class in `[GUITAR_LOW_MIDI, GUITAR_LOW_MIDI + 12)`; `(r, r + 7, r + 12, r + 12 + third, r + 19, r + 24)`, third = 3 or 4.
  - `render_guitar`: per beat, `activity < 1/3` a downstroke on bar beats 1 and 3 only, ringing 2 beats; `< 2/3` a downstroke every beat; else a downstroke on the beat and an upstroke half a beat later. Downstroke: all six notes low to high, note `i` delayed `i * STRUM_GAP_BEATS`. Upstroke: top four notes high to low, velocity x `UPSTROKE_VELOCITY_SCALE`. Pass the result through `trim_overlaps`.
- [ ] Run -> pass, including `test_api_serves_midi_for_every_instrument` for `pad` and `guitar`. Full backend checks -> clean. Commit.

### Task 6: Stage pieces and samples for the second synth and guitar

**Files:** Add `frontend/public/soundfonts/acoustic_guitar_steel-mp3.js`, `pad_2_warm-mp3.js`. Modify `frontend/public/soundfonts/README.md`, `frontend/src/config.ts`, `src/stage/art.tsx`, `src/stage/layout.ts`, `src/stage/Stage.tsx`.

**Interfaces:**
- Consumes: backend instrument ids `pad`, `guitar` (Task 5); `MixPreset` (Task 1).
- Produces: `SOUND_PRESETS.pad` (volume 80) and `.guitar` (volume 100), both `kind: 'pitched'`; `MIX_PRESETS.pad` = 90 Hz, -3/0/-1 dB, send 0.45; `MIX_PRESETS.guitar` = 110 Hz, -2/0/+2 dB, send 0.25; `PadArt`, `GuitarArt`; `PLACEMENTS.pad`, `PLACEMENTS.guitar`.

- [ ] Download both files from `https://gleitz.github.io/midi-js-soundfonts/MusyngKite/<name>-mp3.js` and add them to the Musyng Kite row of the README.
- [ ] Add presets, art and placements. Starting geometry: guitar outline `rect x=830 y=44 width=140 height=432 rx=28`, tag at (900, 500); pad outline `rect x=530 y=250 width=270 height=120 rx=14`, tag at (665, 228). Add one light pool per new piece. Art follows the existing style: a natural-wood acoustic guitar with a round sound hole; a second keyboard visibly different from the lead synth.
- [ ] `npm run lint && npm run build` -> clean.
- [ ] Browser run at 1280x900: seven pieces visible, no outline overlaps another piece or the play button (check the screenshot); both sample files return 200; drop SPY on all seven, play 8 s, no console errors, no toast. Listen for low-end mud and adjust the pad, bass and guitar EQ.
- [ ] Commit.

### Task 7: Ornaments

**Files:** Create `backend/src/market_band/ornaments.py`. Modify `lead.py`, `chords.py`, `config.py`, `tests/test_song.py`, `CLAUDE.md`, `README.md`.

**Interfaces:**
- Consumes: `lead_pitches`, `pool_notes`, `guitar_voicing`, `Note`.
- Produces (`config.py`): `ORNAMENT_TRIGGER = 0.75`, `ORNAMENT_MIN_GAP_BEATS = 4`.
- Produces (`ornaments.py`):
  ```python
  def stable_rng(source: str, instrument_id: str) -> random.Random  # seed = zlib.crc32(f"{source}:{instrument_id}".encode())
  def ornament_beats(ir: IRSeries) -> tuple[int, ...]
  def lead_ornament(rng: random.Random, beat: int, pitch: int, next_pitch: int, pool: tuple[int, ...], velocity: int) -> list[Note]
  def guitar_ornament(rng: random.Random, beat: int, voicing: tuple[int, ...], velocity: int) -> list[Note]
  ```

- [ ] Write failing tests:
  ```python
  def test_ornaments_land_on_busy_beats_with_a_gap():
      assert ornament_beats(ir_with_activity([0.8] * 8)) == (0, 4)
      assert ornament_beats(ir_with_activity([0.7] * 8)) == ()
  def test_lead_ornament_stays_in_its_beat_and_pool():  # 50 seeds
      notes = lead_ornament(random.Random(seed), 5, 64, 67, pool, 90)
      assert all(5 <= n.start_beat and n.start_beat + n.duration_beats <= 6 and n.midi in pool for n in notes)
  def test_guitar_ornament_uses_only_the_voicing():  # 50 seeds, same bounds, n.midi in voicing
  def test_stable_rng_is_seeded_from_crc32_not_hash():
      assert stable_rng("SPY", "synth").random() == random.Random(zlib.crc32(b"SPY:synth")).random()
  def test_flat_stock_renders_for_every_instrument():
      flat_ir = stock_to_ir("T", make_frame([50.0] * 10, [0.0] * 10))
      for instrument in INSTRUMENTS: assert render_midi(flat_ir, instrument)[:4] == b"MThd"
  ```
  The Task 3 melody thresholds and Task 5 overlap test stay in the suite and must still pass.
- [ ] Run -> fail. Implement. Lead kinds, chosen by `rng.choice`: grace (pool note below for 1/8 beat, then the pitch), mordent (pitch, upper pool neighbour, pitch: 1/8, 1/8, 3/4), trill (pitch and upper neighbour alternating, eight notes of 1/8), run (four notes of 1/4 walking the pool toward `next_pitch`). Guitar kinds: roll (voicing low to high, 1/6 beat apart, each ringing to the end of the beat), hammer (the voicing with its top note preceded by the note below it for 1/8 beat). `render_lead` and `render_guitar` replace an ornament beat's notes with the ornament; a tied note is ended before it.
- [ ] Run -> pass. Full backend and frontend checks -> clean.
- [ ] Update the "Approach" bullets in `CLAUDE.md` and the mapping table in `README.md` to the new IR channels, chord rule, roles and 64-beat timing. Remove the resolved "MIDI clip format" open decision.
- [ ] Browser run: SPY on all seven, then a mixed band (SPY, AAPL, TSLA, GLD, TLT spread across pieces); listen to both. Commit.
