"""OLS regression with HAC standard errors."""

import io
import pandas as pd
import numpy as np


def register(mcp):
    @mcp.tool()
    async def ols(
        csv_data: str,
        y_col: str,
        x_cols: str,
        hac_lags: int = 6,
        date_col: str = "date",
    ) -> str:
        """Run OLS regression with Newey-West (HAC) standard errors.

        csv_data: CSV string with all variables in columns
        y_col: name of the dependent variable column
        x_cols: comma-separated names of independent variable columns
        hac_lags: number of lags for HAC standard errors (default 6)
        date_col: name of date column (used for sorting, then dropped)

        Returns regression summary: coefficients, t-stats, p-values, R².
        """
        import statsmodels.api as sm

        # Parse CSV
        lines = csv_data.strip().split("\n")
        csv_start = 0
        for i, line in enumerate(lines):
            if "," in line and any(c.isalpha() for c in line):
                csv_start = i
                break
        clean_csv = "\n".join(lines[csv_start:])
        df = pd.read_csv(io.StringIO(clean_csv))

        # Sort by date if present
        dcol = next((c for c in df.columns if c.lower() == date_col.lower()), None)
        if dcol:
            df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
            df = df.sort_values(dcol)
            df = df.drop(columns=[dcol])

        # Numeric conversion
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna()

        y = df[y_col]
        x_names = [c.strip() for c in x_cols.split(",")]
        X = sm.add_constant(df[x_names])

        model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})

        # Format output
        lines_out = [
            f"OLS Regression — {y_col} ~ {' + '.join(x_names)}",
            f"N = {int(model.nobs)}, R² = {model.rsquared:.4f}, Adj R² = {model.rsquared_adj:.4f}",
            f"HAC standard errors (Newey-West, {hac_lags} lags)",
            "",
            f"{'Variable':<20} {'Coef':>10} {'Std Err':>10} {'t':>8} {'P>|t|':>8}",
            "-" * 60,
        ]
        for name, coef, se, t, p in zip(
            model.params.index, model.params, model.bse, model.tvalues, model.pvalues
        ):
            lines_out.append(f"{name:<20} {coef:>10.4f} {se:>10.4f} {t:>8.2f} {p:>8.4f}")

        lines_out.extend([
            "",
            f"F-statistic: {model.fvalue:.2f} (p = {model.f_pvalue:.4f})",
            f"Durbin-Watson: {sm.stats.stattools.durbin_watson(model.resid):.3f}",
        ])

        return "\n".join(lines_out)
