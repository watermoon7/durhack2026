"""One-off download of raw OHLCV data into ``data/raw``.

Run once before the demo (``uv run market-band-fetch``). The API only ever reads the
cached CSVs, so nothing is fetched over the network while the demo is running.
"""

import sys

import pandas as pd
import yfinance as yf

from market_band.config import DATASETS, PERIOD_END, PERIOD_START, RAW_DATA_DIR, DatasetConfig

YF_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def fetch_dataset(dataset: DatasetConfig) -> pd.DataFrame:
    """Download one ticker's daily OHLCV for the demo period as a tidy frame."""
    assert dataset.ticker, "dataset must name a ticker"
    history: pd.DataFrame = yf.Ticker(dataset.ticker).history(
        start=PERIOD_START, end=PERIOD_END, interval="1d", auto_adjust=False
    )
    if history.empty:
        raise RuntimeError(f"yfinance returned no rows for {dataset.ticker}")
    missing = set(YF_COLUMNS) - set(history.columns)
    if missing:
        raise RuntimeError(f"{dataset.ticker}: yfinance response lacks columns {sorted(missing)}")

    frame = history[list(YF_COLUMNS)].rename(columns=YF_COLUMNS)
    frame.index = pd.DatetimeIndex(frame.index).strftime("%Y-%m-%d")
    frame.index.name = "date"
    return frame


def main() -> None:
    """Fetch every configured dataset and write it to ``data/raw/<id>.csv``."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for dataset in DATASETS:
        try:
            frame = fetch_dataset(dataset)
        except RuntimeError as error:
            failures.append(str(error))
            continue
        path = RAW_DATA_DIR / f"{dataset.id}.csv"
        frame.to_csv(path)
        print(f"{dataset.ticker}: {len(frame)} rows -> {path}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
