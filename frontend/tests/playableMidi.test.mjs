import test from 'node:test'
import assert from 'node:assert/strict'
import * as MidiPackage from '@tonejs/midi'
import { normalisePlayableMidi } from '../src/audio/playableMidi.js'

const Midi = MidiPackage.Midi ?? MidiPackage.default?.Midi
function vlq(n) {
  const out = [n & 127]
  while (n >>= 7) out.unshift((n & 127) | 128)
  return out
}
function uint32(n) { return [(n >>> 24)&255, (n >>> 16)&255, (n >>> 8)&255, n&255] }
function fixture(program = 81, channel = 1) {
  const label = [...new TextEncoder().encode('selected_part')]
  const events = [0,255,81,3,7,161,32,
    0,176|channel,7,35, 0,176|channel,10,64]
  if (program !== null) events.push(0,192|channel,program)
  events.push(0,255,3,label.length,...label,
    0,144|channel,60,80,...vlq(480),128|channel,60,0,...vlq(114720),255,47,0)
  return new Uint8Array([77,84,104,100,0,0,0,6,0,0,0,1,1,224,
    77,84,114,107,...uint32(events.length),...events])
}

test('real parser can create setup-only tracks from a single physical MIDI track', () => {
  const midi = new Midi(fixture())
  assert.ok(midi.tracks.length > 1)
  assert.equal(midi.tracks.filter(t => t.notes.length > 0).length, 1)
  const header = midi.header
  normalisePlayableMidi(midi)
  assert.equal(midi.tracks.length, 1)
  assert.equal(midi.tracks[0].notes[0].midi, 60)
  assert.equal(midi.tracks[0].notes[0].ticks, 0)
  assert.equal(midi.tracks[0].notes[0].durationTicks, 480)
  assert.equal(midi.header, header)
  assert.equal(midi.header.tempos[0].bpm, 120)
  assert.equal(normalisePlayableMidi(midi), midi)
})

test('all seven instrument program/channel configurations remain playable', () => {
  for (const [program,channel] of [[33,0],[null,9],[81,1],[89,2],[24,3],[80,4],[26,5]]) {
    const midi = normalisePlayableMidi(new Midi(fixture(program,channel)))
    assert.equal(midi.tracks.length, 1)
    assert.equal(midi.tracks[0].notes.length, 1)
  }
})

test('reject zero or multiple genuinely note-bearing parts', () => {
  assert.throws(() => normalisePlayableMidi(new Midi()), /found 0/)
  const midi = new Midi()
  midi.addTrack().addNote({midi:60,ticks:0,durationTicks:480})
  midi.addTrack().addNote({midi:64,ticks:0,durationTicks:480})
  assert.throws(() => normalisePlayableMidi(midi), /found 2/)
})
