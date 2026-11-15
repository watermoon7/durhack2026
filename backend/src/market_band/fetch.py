"""One-off download of raw OHLCV data into ``data/raw``.

Run once before the demo. The API only ever reads the cached CSVs, so nothing is fetched
over the network while the demo is running.

- ``uv run market-band-fetch``            demo datasets over the demo period
- ``uv run market-band-fetch-scenarios``  every scenario's band over its event window
"""

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

from market_band.config import (
    DATASETS,
    MAX_START_GAP_DAYS,
    PERIOD_END,
    PERIOD_START,
    RAW_DATA_DIR,
    SCENARIO_DATA_DIR,
    SCENARIOS,
    DatasetConfig,
)

YF_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def fetch_dataset(dataset: DatasetConfig, start: str, end: str) -> pd.DataFrame:
    """Download one ticker's daily OHLCV for ``[start, end)`` as a tidy frame."""
    assert dataset.ticker, "dataset must name a ticker"
    assert start < end, f"empty window {start}..{end}"
    history: pd.DataFrame = yf.Ticker(dataset.ticker).history(
        start=start, end=end, interval="1d", auto_adjust=False
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


def check_coverage(dataset: DatasetConfig, frame: pd.DataFrame, start: str) -> None:
    """Fail if the series starts late (asset not yet listed) or volume is unexpectedly absent."""
    assert not frame.empty, "frame must have rows"
    first_row = pd.Timestamp(str(frame.index[0]))
    gap_days = (first_row - pd.Timestamp(start)).days
    if gap_days > MAX_START_GAP_DAYS:
        raise RuntimeError(
            f"{dataset.ticker}: first row {first_row.date()} is {gap_days} days after {start}"
        )
    if dataset.has_volume and not (frame["volume"] > 0).any():
        raise RuntimeError(f"{dataset.ticker}: volume is all zero; set has_volume=False")


def fetch_to_csv(dataset: DatasetConfig, start: str, end: str, path: Path) -> None:
    """Fetch one dataset over ``[start, end)``, validate it and write it to ``path``."""
    assert path.suffix == ".csv", f"expected a .csv path, got {path}"
    frame = fetch_dataset(dataset, start, end)
    check_coverage(dataset, frame, start)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path)
    print(f"{dataset.ticker}: {len(frame)} rows {frame.index[0]}..{frame.index[-1]} -> {path}")


def report_failures(failures: list[str]) -> None:
    """Print collected failures and exit non-zero if there were any."""
    if failures:
        print("\n".join(failures), file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Fetch every demo dataset and write it to ``data/raw/<id>.csv``."""
    failures: list[str] = []
    for dataset in DATASETS:
        try:
            fetch_to_csv(dataset, PERIOD_START, PERIOD_END, RAW_DATA_DIR / f"{dataset.id}.csv")
        except RuntimeError as error:
            failures.append(str(error))
    report_failures(failures)


def main_scenarios() -> None:
    """Fetch every scenario's band to ``data/raw/scenarios/<scenario>/<id>.csv``."""
    failures: list[str] = []
    for scenario in SCENARIOS:
        print(f"== {scenario.id} ({scenario.start}..{scenario.end})")
        for dataset in scenario.datasets:
            path = SCENARIO_DATA_DIR / scenario.id / f"{dataset.id}.csv"
            try:
                fetch_to_csv(dataset, scenario.start, scenario.end, path)
            except RuntimeError as error:
                failures.append(f"{scenario.id}: {error}")
    report_failures(failures)


if __name__ == "__main__":
    main()
