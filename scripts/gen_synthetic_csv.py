"""Generate a synthetic CSV for load/render performance testing.

Usage:
    python scripts/gen_synthetic_csv.py output.csv --rows 1000000 --cols 6
    python scripts/gen_synthetic_csv.py output.csv --rows 1000000 --cols 6 --str-cols 4
"""

from __future__ import annotations

import argparse

import numpy as np
import polars as pl


def generate(rows: int, cols: int, str_cols: int = 0, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    data: dict[str, np.ndarray] = {"t": np.arange(rows, dtype=np.float64)}
    for i in range(cols):
        data[f"series_{i}"] = np.cumsum(rng.normal(scale=1.0, size=rows))
    # Non-numeric columns, for exercising/measuring the load path's handling
    # of text data (e.g. an ID or label column) that can never be plotted --
    # see ColumnStore.numeric_column_names() and loader.py's load_csv().
    for i in range(str_cols):
        data[f"label_{i}"] = np.array([f"row-{i}-{n:08d}" for n in range(rows)])
    return pl.DataFrame(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="Output CSV path")
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--cols", type=int, default=6)
    parser.add_argument("--str-cols", type=int, default=0, help="Number of non-numeric (text) columns to add")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    df = generate(args.rows, args.cols, args.str_cols, args.seed)
    df.write_csv(args.output)
    print(f"Wrote {args.rows:,} rows x {args.cols} series columns x {args.str_cols} text columns to {args.output}")


if __name__ == "__main__":
    main()
