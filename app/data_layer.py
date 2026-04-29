"""
Synchronous wrapper around the async connectors for Streamlit.
All functions return pandas DataFrames.
"""

import asyncio
import io
import pandas as pd
import os
import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not required on Streamlit Cloud


def _get_secret(key: str) -> str:
    """Get a secret from Streamlit secrets (cloud) or environment (.env local)."""
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key, "")


def _run(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _csv_to_df(csv_text: str, date_col: str = "date", value_col: str = "value") -> pd.DataFrame:
    """Parse CSV text into a DataFrame with proper types."""
    # Skip header lines that aren't CSV
    lines = csv_text.strip().split("\n")
    csv_start = 0
    for i, line in enumerate(lines):
        if "," in line and any(c.isalpha() for c in line):
            csv_start = i
            break
    clean = "\n".join(lines[csv_start:])
    df = pd.read_csv(io.StringIO(clean))

    # Find and parse date column
    dcol = next((c for c in df.columns if "date" in c.lower() or "period" in c.lower() or "time" in c.lower()), df.columns[0])
    df[dcol] = pd.to_datetime(df[dcol], errors="coerce")

    # Numeric value columns
    for col in df.columns:
        if col != dcol:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[dcol])
    return df.sort_values(dcol).reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════
# FRED
# ══════════════════════════════════════════════════════════════════

def fred_search(query: str, limit: int = 10) -> pd.DataFrame:
    """Search FRED for series."""
    async def _search():
        key = _get_secret("FRED_API_KEY")
        if not key:
            raise ValueError("FRED_API_KEY not set — add to .env (local) or Streamlit secrets (cloud)")
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get("https://api.stlouisfed.org/fred/series/search", params={
                "search_text": query, "limit": limit,
                "order_by": "popularity", "sort_order": "desc",
                "api_key": key, "file_type": "json",
            })
            r.raise_for_status()
            data = r.json()
        rows = []
        for s in data.get("seriess", []):
            rows.append({
                "id": s["id"], "title": s["title"],
                "freq": s.get("frequency_short", ""),
                "units": s.get("units_short", ""),
                "start": s.get("observation_start", ""),
                "end": s.get("observation_end", ""),
            })
        return pd.DataFrame(rows)
    return _run(_search())


def fred_get(series_id: str, start: str = None, end: str = None) -> pd.DataFrame:
    """Fetch FRED series data."""
    async def _fetch():
        key = _get_secret("FRED_API_KEY")
        if not key:
            raise ValueError("FRED_API_KEY not set — add to .env (local) or Streamlit secrets (cloud)")
        params = {"series_id": series_id, "api_key": key, "file_type": "json"}
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get("https://api.stlouisfed.org/fred/series/observations", params=params)
            r.raise_for_status()
            data = r.json()
        rows = []
        for o in data.get("observations", []):
            if o["value"] != ".":
                rows.append({"date": o["date"], "value": float(o["value"])})
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["series"] = series_id
        return df
    return _run(_fetch())


# ══════════════════════════════════════════════════════════════════
# ECB
# ══════════════════════════════════════════════════════════════════

def ecb_get(dataset: str, key: str, start: str = None, end: str = None) -> pd.DataFrame:
    """Fetch ECB SDW data."""
    async def _fetch():
        url = f"https://data-api.ecb.europa.eu/service/data/{dataset}/{key}"
        params = {"detail": "dataonly"}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as c:
            r = await c.get(url, params=params, headers={"Accept": "text/csv"})
            r.raise_for_status()
            text = r.text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return pd.DataFrame()
        header = lines[0].split(",")
        records = []
        for line in lines[1:]:
            vals = line.split(",")
            if len(vals) == len(header):
                records.append(dict(zip(header, vals)))
        df = pd.DataFrame(records)
        # Standardize columns
        date_col = next((c for c in df.columns if "TIME_PERIOD" in c.upper()), None)
        val_col = next((c for c in df.columns if "OBS_VALUE" in c.upper()), None)
        if date_col and val_col:
            result = pd.DataFrame({"date": df[date_col], "value": pd.to_numeric(df[val_col], errors="coerce")})
            result["date"] = pd.to_datetime(result["date"], errors="coerce")
            result["series"] = f"{dataset}/{key}"
            return result.dropna()
        return df
    return _run(_fetch())


# ══════════════════════════════════════════════════════════════════
# BIS
# ══════════════════════════════════════════════════════════════════

def bis_get(dataset: str, key: str, start: str = None, end: str = None) -> pd.DataFrame:
    """Fetch BIS data."""
    async def _fetch():
        import csv as csv_mod
        url = f"https://stats.bis.org/api/v1/data/{dataset}/{key}"
        params = {"format": "csv"}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            text = r.text.replace("\r\n", "\n").replace("\r", "\n")
        reader = csv_mod.DictReader(io.StringIO(text))
        records = list(reader)
        if not records:
            return pd.DataFrame()
        rows = []
        for rec in records:
            rows.append({
                "date": rec.get("TIME_PERIOD", ""),
                "value": rec.get("OBS_VALUE", ""),
                "ref_area": rec.get("REF_AREA", ""),
            })
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["series"] = dataset + "/" + df["ref_area"]
        return df.dropna(subset=["date", "value"])
    return _run(_fetch())


# ══════════════════════════════════════════════════════════════════
# IMF Commodity Prices
# ══════════════════════════════════════════════════════════════════

def imf_commodities(commodities: str = "POILBRE+POILWTI+PNGAS+PGOLD",
                     start: str = None, end: str = None) -> pd.DataFrame:
    """Fetch IMF PCPS commodity prices."""
    async def _fetch():
        url = f"http://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/PCPS/M.{commodities}"
        params = {}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        records = []
        dataset = data.get("CompactData", {}).get("DataSet", {})
        series_list = dataset.get("Series", [])
        if isinstance(series_list, dict):
            series_list = [series_list]
        for series in series_list:
            indicator = series.get("@INDICATOR", "")
            obs = series.get("Obs", [])
            if isinstance(obs, dict):
                obs = [obs]
            for o in obs:
                records.append({
                    "date": o.get("@TIME_PERIOD", ""),
                    "value": o.get("@OBS_VALUE", ""),
                    "series": indicator,
                })
        df = pd.DataFrame(records)
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["date", "value"]).sort_values("date")
    return _run(_fetch())


# ══════════════════════════════════════════════════════════════════
# EIA
# ══════════════════════════════════════════════════════════════════

def eia_get(route: str, frequency: str = "monthly", facets: dict = None,
            start: str = None, end: str = None, limit: int = 5000) -> pd.DataFrame:
    """Fetch EIA energy data."""
    async def _fetch():
        key = _get_secret("EIA_API_KEY")
        if not key:
            raise ValueError("EIA_API_KEY not set — add to .env (local) or Streamlit secrets (cloud)")
        url = f"https://api.eia.gov/v2/{route}/data/"
        params = {
            "api_key": key, "frequency": frequency,
            "sort[0][column]": "period", "sort[0][direction]": "desc",
            "length": limit,
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if facets:
            for fk, fv in facets.items():
                params[f"facets[{fk}][]"] = fv
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        records = data.get("response", {}).get("data", [])
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        if "period" in df.columns:
            df["date"] = pd.to_datetime(df["period"], errors="coerce")
        if "value" in df.columns:
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["date", "value"]).sort_values("date") if "date" in df.columns else df
    return _run(_fetch())


# ══════════════════════════════════════════════════════════════════
# Transforms
# ══════════════════════════════════════════════════════════════════

import numpy as np

def transform(df: pd.DataFrame, method: str, window: int = 12,
              value_col: str = "value") -> pd.DataFrame:
    """Apply a time-series transformation to a DataFrame."""
    out = df.copy()
    s = out[value_col]

    if method == "yoy":
        out[value_col] = s.pct_change(12) * 100
    elif method == "mom":
        out[value_col] = s.pct_change(1) * 100
    elif method == "log_diff":
        out[value_col] = np.log(s).diff()
    elif method == "zscore":
        out[value_col] = (s - s.mean()) / s.std()
    elif method == "rolling_mean":
        out[value_col] = s.rolling(window).mean()
    elif method == "rolling_std":
        out[value_col] = s.rolling(window).std()
    elif method == "diff":
        out[value_col] = s.diff()
    elif method == "index_100":
        out[value_col] = (s / s.iloc[0]) * 100
    elif method == "level":
        pass
    else:
        raise ValueError(f"Unknown method: {method}")

    return out.dropna(subset=[value_col])
