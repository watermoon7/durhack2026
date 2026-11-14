# DurHack 2026: Market Band

## Concept

Turn data into music. Each data series (a stock, a crypto coin, an FX pair, an index) becomes a member of a band and plays an instrument. The user drags members onto a stage to build an ensemble, then hears how the data played together over time sounds.

- **Notes, volume, rhythm and sound** come from the data: returns set the pitch, volume sets the loudness, volatility sets the rhythm, drawdown sets the key.
- **How the instruments sound together is the insight.** Assets that move together play in harmony; assets that diverge clash. In a crisis, correlations go to 1, and you hear the band lock into unison.
- **Scenarios** replay historical events with a preset band and timed captions (e.g. 2008 crisis, COVID crash, Swiss franc unpeg).

Markets are the core. Other noisy data (weather, solar wind) is a stretch goal only.

## What makes it new

Turning data into sound has existed for decades (MarketBuzz, TwoTone, NASA Chandra, Crawford's climate string quartet). What we haven't found elsewhere:
1. A band of financial assets that the user picks and arranges.
2. Harmony between instruments that encodes how the assets move together.

Lead the pitch with this, not with "data as sound".

## Target challenges

- **Marshall Wace: New Worlds** (primary). A new way to experience data. Judged on creativity, technical complexity and presentation.
- **SGX FX: Trading Market Storm** (secondary, "Early warning" track). A background risk sound that grows more clashing as market stress rises, so traders can monitor without watching every screen. Use SGX's FX data. Cite MarketBuzz: sound improved monitoring when the eyes were busy.
- **DurHack theme:** "Explore art, music and tech!"

## Approach

- Browser-only app, no backend. Tone.js for audio, Tonal.js for scales and chords.
- Python preprocessing script turns raw data into static JSON. Nothing fetched live during the demo.
- 1 trading day = 1 beat (~1 year ≈ 2 min at 120 bpm).
- Notes snap to a scale so it sounds musical, with a musical ↔ raw slider to show what the snapping changes.
- A playhead over price charts so judges see what they hear.

## Milestones

- **M0: Lock decisions.** Stack, mapping principles, data sources, headline scenario.
- **M1: First sound.** One dataset → one instrument, in key. Go/no-go check: does it sound good?
- **M2: The band.** Several instruments, drag-and-drop stage, shared clock, mute/solo.
- **M3: Meaningful mapping.** Correlation → harmony, volatility → rhythm, drawdown → key. Synced charts.
- **M4: Scenarios.** Preset bands plus event captions. Polish 2008 before adding more.
- **M5: Challenge layer.** SGX risk sound on FX data. Extra data domains only if time allows.
- **M6: Pitch.** Demo script around the "correlations go to 1" moment, recorded fallback, headphones, Devpost write-up.
