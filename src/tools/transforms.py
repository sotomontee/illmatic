"""Time-series transformations."""

import io
import pandas as pd


def register(mcp):
    @mcp.tool()
    async def ts_transform(
        csv_data: str,
        method: str = "yoy",
        window: int = 12,
        date_col: str = "date",
        value_col: str = "value",
    ) -> str:
        """Apply a transformation to time-series CSV data.

        csv_data: CSV string (as returned by any *_get tool)
        method: transformation to apply:
          'yoy'          — Year-over-year percent change
          'mom'          — Month-over-month percent change
          'log_diff'     — Log difference (≈ continuous return)
          'zscore'       — Z-score (standardize to mean=0, std=1)
          'rolling_mean' — Rolling mean (window param)
          'rolling_std'  — Rolling std deviation (window param)
          'diff'         — First difference
          'level'        — No transform (passthrough, useful for alignment)
          'index_100'    — Rebase to 100 at first observation
        window: rolling window size (for rolling_mean/rolling_std), default 12
        date_col: name of date column, default 'date'
        value_col: name of value column, default 'value'

        Returns transformed CSV data.
        """
        # Strip any header line that's not CSV
        lines = csv_data.strip().split("\n")
        csv_start = 0
        for i, line in enumerate(lines):
            if date_col in line.lower() or "," in line:
                csv_start = i
                break
        clean_csv = "\n".join(lines[csv_start:])

        df = pd.read_csv(io.StringIO(clean_csv))

        # Find columns flexibly
        dcol = next((c for c in df.columns if c.lower() == date_col.lower()), df.columns[0])
        vcol = next((c for c in df.columns if c.lower() == value_col.lower()), df.columns[-1])

        df[dcol] = pd.to_datetime(df[dcol])
        df[vcol] = pd.to_numeric(df[vcol], errors="coerce")
        df = df.sort_values(dcol).dropna(subset=[vcol])

        s = df[vcol]

        if method == "yoy":
            df["transformed"] = s.pct_change(12) * 100
        elif method == "mom":
            df["transformed"] = s.pct_change(1) * 100
        elif method == "log_diff":
            import numpy as np
            df["transformed"] = np.log(s).diff()
        elif method == "zscore":
            df["transformed"] = (s - s.mean()) / s.std()
        elif method == "rolling_mean":
            df["transformed"] = s.rolling(window).mean()
        elif method == "rolling_std":
            df["transformed"] = s.rolling(window).std()
        elif method == "diff":
            df["transformed"] = s.diff()
        elif method == "index_100":
            df["transformed"] = (s / s.iloc[0]) * 100
        elif method == "level":
            df["transformed"] = s
        else:
            return f"Unknown method: {method}"

        df = df.dropna(subset=["transformed"])
        out = df[[dcol, "transformed"]].rename(columns={"transformed": "value"})
        result = out.to_csv(index=False)
        return f"Transformed ({method}): {len(out)} rows\n{result}"
