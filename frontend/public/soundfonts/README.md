# Instrument samples

Self-hosted so the demo never fetches audio from the internet. Played by [smplr](https://github.com/danigb/smplr).

| Path | Source | Licence |
| --- | --- | --- |
| `soundfonts/electric_bass_finger-mp3.js`, `soundfonts/acoustic_grand_piano-mp3.js`, `soundfonts/acoustic_guitar_steel-mp3.js`, `soundfonts/pad_2_warm-mp3.js`, `soundfonts/distortion_guitar-mp3.js`, `soundfonts/electric_bass_pick-mp3.js`, `soundfonts/rock_organ-mp3.js` | Musyng Kite soundfont, MIDI.js build from [gleitz/midi-js-soundfonts](https://github.com/gleitz/midi-js-soundfonts) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| `drums/TR-808/` (kick `bd2550`, snare `sd5050`, closed hi-hat `ch`) | [smpldsnds/drum-machines](https://github.com/smpldsnds/drum-machines) | Public domain |
| `drums/LM-2/` (LinnDrum: `kick`, `snare-m`, `hhclosed`, `crash`, `tom-hh`, `tom-h`, `tom-m`, `tom-l`) | [smpldsnds/drum-machines](https://github.com/smpldsnds/drum-machines) | Public domain |

Both `dm.json` manifests are trimmed to the samples the band uses; smplr loads every sample a manifest lists. smplr loads samples from the manifest's own folder and ignores its `baseUrl`, so they are served locally.
