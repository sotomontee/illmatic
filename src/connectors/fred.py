"""FRED (Federal Reserve Economic Data) connector."""

import os
import httpx
from typing import Optional

BASE = "https://api.stlouisfed.org/fred"


def _key() -> str:
    k = os.environ.get("FRED_API_KEY", "")
    if not k:
        raise RuntimeError("FRED_API_KEY not set in .env")
    return k


async def _get(endpoint: str, params: dict) -> dict:
    params["api_key"] = _key()
    params["file_type"] = "json"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{BASE}/{endpoint}", params=params)
        r.raise_for_status()
        return r.json()


def register(mcp):
    @mcp.tool()
    async def fred_search(query: str, limit: int = 10) -> str:
        """Search FRED for series matching a query.
        Returns series ID, title, frequency, units, and date range."""
        data = await _get("series/search", {
            "search_text": query,
            "limit": limit,
            "order_by": "popularity",
            "sort_order": "desc",
        })
        rows = []
        for s in data.get("seriess", []):
            rows.append(
                f"- **{s['id']}**: {s['title']}  "
                f"({s['frequency_short']}, {s['units_short']}, "
                f"{s['observation_start']}→{s['observation_end']})"
            )
        return "\n".join(rows) if rows else "No series found."

    @mcp.tool()
    async def fred_get(
        series_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        freq: Optional[str] = None,
    ) -> str:
        """Fetch observations for a FRED series.
        series_id: e.g. 'CPIAUCSL', 'UNRATE', 'GDP'
        start/end: YYYY-MM-DD (optional)
        freq: aggregation frequency — d/w/bw/m/q/sa/a (optional)
        Returns CSV-formatted date,value rows."""
        params: dict = {"series_id": series_id}
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        if freq:
            params["frequency"] = freq
        data = await _get("series/observations", params)
        obs = data.get("observations", [])
        lines = ["date,value"]
        for o in obs:
            v = o["value"]
            if v != ".":
                lines.append(f"{o['date']},{v}")
        return f"FRED {series_id}: {len(lines)-1} observations\n" + "\n".join(lines)
