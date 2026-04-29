"""EIA (U.S. Energy Information Administration) connector."""

import os
import httpx
from typing import Optional

BASE = "https://api.eia.gov/v2"


def _key() -> str:
    k = os.environ.get("EIA_API_KEY", "")
    if not k:
        raise RuntimeError(
            "EIA_API_KEY not set in .env. "
            "Get a free key at https://www.eia.gov/opendata/register.php"
        )
    return k


def register(mcp):
    @mcp.tool()
    async def eia_get(
        route: str,
        frequency: str = "monthly",
        series: Optional[str] = None,
        facets: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        sort_col: str = "period",
        sort_dir: str = "desc",
        limit: int = 5000,
    ) -> str:
        """Fetch energy data from the EIA API v2.

        route: API route path (without /v2 prefix). Key routes:
          'petroleum/pri/spt'         — Spot prices (WTI, Brent, heating oil, jet fuel)
          'petroleum/pri/fut'         — Futures prices
          'petroleum/sum/snd'         — Supply & disposition (stocks, production, imports)
          'petroleum/crd/crpdn'       — Crude oil production
          'natural-gas/pri/sum'       — Natural gas prices (Henry Hub)
          'natural-gas/sum/snd'       — Natural gas supply & disposition
          'natural-gas/stor/wkly'     — Weekly gas storage
          'coal/shipments'            — Coal shipments
          'electricity/retail-sales'  — Electricity retail sales & prices
          'total-energy/data'         — Monthly Energy Review
          'co2-emissions'             — CO2 emissions from energy
          'steo'                      — Short-Term Energy Outlook (forecasts!)

        frequency: 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
        series: specific series ID filter (optional)
        facets: JSON-like filter string for dimensions, e.g. 'product=EPCBRENT' (optional)
        start/end: period filter, e.g. '2020-01'
        limit: max records (default 5000)

        Common petroleum product codes:
          EPCBRENT — Brent crude   EPCWTI — WTI crude
          EPJK     — Jet fuel      EPMRU  — Regular gasoline
          EPD2F    — No. 2 heating oil / diesel
        """
        url = f"{BASE}/{route}/data/"
        params = {
            "api_key": _key(),
            "frequency": frequency,
            "sort[0][column]": sort_col,
            "sort[0][direction]": sort_dir,
            "length": limit,
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        # Parse facets if provided
        if facets:
            for part in facets.split(","):
                if "=" in part:
                    fk, fv = part.strip().split("=", 1)
                    params[f"facets[{fk}][]"] = fv

        if series:
            params["facets[series][]"] = series

        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        response = data.get("response", {})
        records = response.get("data", [])

        if not records:
            return f"No data returned for EIA {route}"

        # Build CSV from the first record's keys
        keys = list(records[0].keys())
        # Prioritize useful columns
        priority = ["period", "value", "product-name", "product", "series",
                     "area-name", "process-name", "units"]
        cols = [k for k in priority if k in keys]
        # Add remaining
        for k in keys:
            if k not in cols:
                cols.append(k)
        cols = cols[:8]  # Cap columns for readability

        lines = [",".join(cols)]
        for rec in records:
            lines.append(",".join(str(rec.get(c, "")) for c in cols))

        total = response.get("total", len(records))
        return f"EIA {route}: {len(records)} of {total} records\n" + "\n".join(lines)

    @mcp.tool()
    async def eia_search(query: str) -> str:
        """Guide to EIA API routes and common queries.

        Since the EIA API is route-based, this provides a reference for
        finding the right route for your data needs."""
        guides = {
            "crude": (
                "**Crude Oil**\n"
                "  Spot prices: eia_get('petroleum/pri/spt', facets='product=EPCWTI') or 'product=EPCBRENT'\n"
                "  Futures: eia_get('petroleum/pri/fut')\n"
                "  Production: eia_get('petroleum/crd/crpdn')\n"
                "  Stocks: eia_get('petroleum/stoc/wstk')"
            ),
            "oil": (
                "**Oil**\n"
                "  Same as crude — use petroleum/pri/spt for spot prices\n"
                "  Supply & demand balance: eia_get('petroleum/sum/snd')"
            ),
            "natural gas": (
                "**Natural Gas**\n"
                "  Prices: eia_get('natural-gas/pri/sum') — includes Henry Hub\n"
                "  Storage: eia_get('natural-gas/stor/wkly') — weekly underground storage\n"
                "  Production: eia_get('natural-gas/prod/sum')\n"
                "  Supply/demand: eia_get('natural-gas/sum/snd')"
            ),
            "gas": (
                "**Gas** — see 'natural gas' above, or petroleum/pri/spt for gasoline"
            ),
            "coal": (
                "**Coal**\n"
                "  Shipments: eia_get('coal/shipments')\n"
                "  Production: eia_get('coal/production/quarterly')"
            ),
            "electricity": (
                "**Electricity**\n"
                "  Retail sales & prices: eia_get('electricity/retail-sales')\n"
                "  Generation: eia_get('electricity/electric-power-operational-data')"
            ),
            "carbon": (
                "**CO2 Emissions**\n"
                "  eia_get('co2-emissions/co2-emissions-aggregates')"
            ),
            "forecast": (
                "**Short-Term Energy Outlook (forecasts)**\n"
                "  eia_get('steo', series='PAPR_WORLD') — world oil production forecast\n"
                "  eia_get('steo', series='BREPUUS') — Brent price forecast"
            ),
        }
        q = query.lower()
        matches = []
        for kw, info in guides.items():
            if any(w in q for w in kw.split()):
                matches.append(info)
        if matches:
            return "\n\n".join(matches)
        return "Available categories: crude/oil, natural gas, coal, electricity, carbon/emissions, forecast (STEO)"
