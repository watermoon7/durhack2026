# Stock data to musical-event CSV

Run from the repository:
```sh
pip install -r requirements-stock-music.txt
python Stock_Data_to_Metrics.py
python Stock_Data_to_Metrics.py --input data/other.csv --output data/other_events.csv --symbols AAPL MSFT --start 2008-10-01 --end 2008-11-01
```

Input schema: timestamp,symbol,open,high,low,close,volume. Multiple symbols are processed separately. If symbol is omitted it is UNKNOWN. Date is accepted instead of timestamp. Use consistently adjusted or unadjusted OHLCV, not mixed prices. Supply source CSVs yourself; this script does not download market data.

Edit CONFIG for paths, source interval, tempo, beats per input candle, instruments, candle rules and mapping bounds. Daily=1D, Monday-start weeks=W-MON, month-start=MS; minute examples=1min/5min/1h. For minute input also set base_interval to 1min. Calendar bins use UTC, so convert exchange session boundaries yourself if needed. Never request a shorter candle than the source. Aggregation is first open, maximum high, minimum low, last close, summed volume. Partial first/last weeks/months are included, not extrapolated.

Metrics: return_pct=(close/open)-1 maps to pitch; range_pct=(high-low)/open maps to 1/2/4/8 repeated notes per candle; relative_volume maps to velocity 35..127. Relative volume compares volume per source bar with the mean of up to 20 PREVIOUS candles on the same symbol/track; first candle or zero baseline defaults to 1. Missing index activity is not replaced with ETF volume. Return and range fields contain fractions (0.01 means 1%). Pitch uses within-candle open-to-close return, so overnight gaps are not represented as returns. Bounds clip outliers; edit metrics(), CONFIG metric selectors, and build_events() for different mappings. No key/scale quantisation yet.

All tracks use a common source-timestamp axis: two beats per observed base timestamp by default; weekends/overnights are compressed out. Missing rows are not filled. Longer candles span their constituent source timestamps. Output has one row per note, with instrument, MIDI-number pitch, velocity, start/duration in beats and seconds, original OHLCV, source_count and metrics. Repeated notes duplicate their candle metrics: do not sum their volume as if independent candles. Instrument labels are metadata, not rendered sound. This is offline descriptive sonification; weekly/monthly notes use the full candle and are not real-time forecasts.

## Sample provenance
23 daily S&P 500 index (^GSPC) OHLCV rows, 2008-10-01 through 2008-10-31, transcribed from https://www.statmuse.com/money/ask/sandp-500-prices-oct-2008 on 2026-11-14; several crash dates cross-checked against Yahoo Finance historical search results. Source warns daily data may be incomplete. This is source-reported index volume, not trading volume of an investable index security. Prices are index points, not dollars. Sample covers October turmoil, not the entire financial crisis. No synthetic minute data.

Default sample produces 23 daily, five weekly (edge weeks partial), and one monthly candle; 116 note events over a 46-beat timeline (27.6 seconds at 100 BPM). Monthly relative-volume baseline is unavailable with one month, so defaults to 1; extend the dataset for varying monthly activity. Run the script to create data/stock_music_events.csv. No audio/MIDI output.
