"""Plotting tools — line charts for time series."""

import io
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def register(mcp):
    @mcp.tool()
    async def plot_series(
        csv_data: str,
        title: str = "Time Series",
        ylabel: str = "",
        filename: str = "chart.png",
        date_col: str = "date",
        value_col: str = "value",
        group_col: str = "",
        figsize_w: float = 12,
        figsize_h: float = 6,
    ) -> str:
        """Plot one or more time series from CSV data to a PNG file.

        csv_data: CSV string with date and value columns
        title: chart title
        ylabel: y-axis label
        filename: output filename (saved to ./out/)
        date_col: name of date column
        value_col: name of value column
        group_col: if set, split into multiple lines by this column
                   (e.g. 'ref_area' or 'commodity' or 'indicator')
        figsize_w/figsize_h: figure dimensions in inches

        Returns the path to the saved PNG.
        """
        # Parse CSV
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
        vcol = next((c for c in df.columns if c.lower() == value_col.lower()), None)
        if vcol is None:
            vcol = [c for c in df.columns if c != dcol][0] if len(df.columns) > 1 else df.columns[-1]

        df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
        df[vcol] = pd.to_numeric(df[vcol], errors="coerce")
        df = df.dropna(subset=[dcol, vcol])

        fig, ax = plt.subplots(figsize=(figsize_w, figsize_h))

        gcol = None
        if group_col:
            gcol = next((c for c in df.columns if c.lower() == group_col.lower()), None)

        if gcol:
            for name, grp in df.groupby(gcol):
                grp = grp.sort_values(dcol)
                ax.plot(grp[dcol], grp[vcol], label=str(name), linewidth=1.5)
            ax.legend(loc="best", framealpha=0.9)
        else:
            df = df.sort_values(dcol)
            ax.plot(df[dcol], df[vcol], linewidth=1.5, color="#2563eb")

        ax.set_title(title, fontsize=14, fontweight="bold")
        if ylabel:
            ax.set_ylabel(ylabel)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        fig.autofmt_xdate()
        ax.grid(True, alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        out_dir = os.path.join(os.getcwd(), "out")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, filename)
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return f"Chart saved: {path} ({os.path.getsize(path) // 1024} KB)"
