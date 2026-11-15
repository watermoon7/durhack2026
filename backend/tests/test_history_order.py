"""Regressions for actual generator ordering and live per-asset discovery."""
import json
import runpy
import struct
from pathlib import Path
from market_band import history


def fixture_midi():
    music = runpy.run_path(str(Path(__file__).resolve().parents[2]/"legacy/Local_Markets_Seven_Tracks.py"))
    end = 240*480
    pieces = [music["midi_track"]([(0,0,b"\xff\x51\x03\x07\xa1\x20")],end)]
    for name,(_,channel,program,*_) in music["TRACKS"].items():
        label = name.encode()
        messages = [(0,0,b"\xff\x03"+music["vlq"](len(label))+label),
                    (0,0,bytes([0xB0|channel,10,64])),
                    (0,2,bytes([0x90|channel,60,80])),(480,1,bytes([0x80|channel,60,0]))]
        if program is not None:
            messages.append((0,0,bytes([0xC0|channel,program])))
        pieces.append(music["midi_track"](messages,end))
    return b"MThd"+struct.pack(">IHHH",6,1,len(pieces),480)+b"".join(pieces)


def test_generator_channel_events_can_precede_name():
    chunks = history.split_midi(fixture_midi())
    for name in history.TRACKS:
        track = history.track_data(chunks,name)
        assert history.track_name(track)==name.encode()
        assert not track.startswith(b"\x00\xff\x03")


def test_completed_asset_visible_before_final_manifest(tmp_path):
    config = {"periods":[dict(id="example",kind="crash",market="US",start="2020-01-01",end="2020-04-01")]}
    (tmp_path/"local_market_periods.json").write_text(json.dumps(config))
    folder = tmp_path/"data/local_markets_v4/complete_test/example/AAPL"
    folder.mkdir(parents=True)
    binary = fixture_midi()
    (folder/"song.mid").write_bytes(binary)
    (folder/"metrics.csv").write_text("track,onset,close,source_end,volatility,relative_volume\n")
    (folder/"metadata.json").write_text(json.dumps(dict(period="example",symbol="AAPL",status="GENERATED",simulated_fraction=1.)))
    result = history.catalogue(tmp_path)
    assert len(result["datasets"])==1
    assert result["periods"][0]["available"]==1
    assert (folder/"song.mid").read_bytes()==binary
    output = history.instrument_midi(folder/"song.mid","guitar")
    assert struct.unpack(">HHH",output[8:14])==(0,1,480)
