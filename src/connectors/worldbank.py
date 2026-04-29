"""World Bank Commodity Prices (Pink Sheet) connector."""

import httpx
from typing import Optional

# The World Bank publishes monthly commodity price data (the "Pink Sheet")
# via their API and also as downloadable CSVs.
# API: https://api.worldbank.org/v2/

BASE = "https://api.worldbank.org/v2"


def register(mcp):
    @mcp.tool()
    async def worldbank_commodities(
        indicator: str = "CRUDE_BRENT",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> str:
        """Fetch World Bank commodity price data.

        indicator: commodity indicator code. Common ones:
          Energy:
            CRUDE_BRENT  — Brent crude oil ($/bbl)
            CRUDE_WTI    — WTI crude oil ($/bbl)
            NGAS_US      — Natural gas, US ($/mmbtu)
            NGAS_EUR     — Natural gas, Europe ($/mmbtu)
            NGAS_JP      — Natural gas, Japan LNG ($/mmbtu)
            COAL_AUS     — Coal, Australia ($/mt)
            COAL_SAFRICA — Coal, South Africa ($/mt)

          Precious Metals:
            GOLD         — Gold ($/troy oz)
            SILVER       — Silver ($/troy oz)
            PLATINUM     — Platinum ($/troy oz)

          Base Metals:
            ALUMINUM     — Aluminum ($/mt)
            COPPER       — Copper ($/mt)
            NICKEL       — Nickel ($/mt)
            ZINC         — Zinc ($/mt)
            LEAD         — Lead ($/mt)
            TIN          — Tin ($/mt)
            IRON_ORE     — Iron ore ($/dmt)

          Agriculture:
            WHEAT_US_HRW — Wheat, US HRW ($/mt)
            MAIZE        — Maize/corn ($/mt)
            SOYBEANS     — Soybeans ($/mt)
            RICE_05      — Rice ($/mt)
            SUGAR_WLD    — Sugar, world ($/kg)
            COFFEE_ARABIC— Coffee, Arabica ($/kg)
            COFFEE_ROBUS — Coffee, Robusta ($/kg)
            COCOA        — Cocoa ($/kg)
            COTTON_A_INDX— Cotton A index ($/kg)
            RUBBER_SGP   — Rubber ($/kg)
            PALM_OIL     — Palm oil ($/mt)

          Fertilizers:
            DAP          — DAP fertilizer ($/mt)
            UREA_EE      — Urea ($/mt)
            PHITE_ROCK   — Phosphate rock ($/mt)

        start_year/end_year: filter by year range
        """
        # Use the World Bank commodity price API
        # The indicator maps to their CMO (Commodity Markets Outlook) dataset
        url = f"{BASE}/country/WLD/indicator/COMMODITY.{indicator}"
        params = {
            "format": "json",
            "per_page": 500,
        }
        if start_year and end_year:
            params["date"] = f"{start_year}:{end_year}"
        elif start_year:
            params["date"] = f"{start_year}:2026"
        elif end_year:
            params["date"] = f"1960:{end_year}"

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
            r = await c.get(url, params=params)

            # If the commodity API doesn't work, try the pink sheet CSV
            if r.status_code != 200 or not r.text.strip():
                return await _fetch_pink_sheet(indicator, start_year, end_year)

            try:
                data = r.json()
            except Exception:
                return await _fetch_pink_sheet(indicator, start_year, end_year)

        # World Bank API returns [metadata, data_array]
        if not isinstance(data, list) or len(data) < 2 or not data[1]:
            return await _fetch_pink_sheet(indicator, start_year, end_year)

        records = data[1]
        lines = ["date,value"]
        for rec in sorted(records, key=lambda x: x.get("date", "")):
            val = rec.get("value")
            if val is not None:
                lines.append(f"{rec['date']},{val}")

        if len(lines) > 1:
            return f"World Bank {indicator}: {len(lines)-1} observations\n" + "\n".join(lines)
        return await _fetch_pink_sheet(indicator, start_year, end_year)

    @mcp.tool()
    async def worldbank_commodity_search(query: str) -> str:
        """Search for World Bank commodity indicators."""
        all_commodities = {
            "crude": ["CRUDE_BRENT", "CRUDE_WTI"],
            "oil": ["CRUDE_BRENT", "CRUDE_WTI"],
            "brent": ["CRUDE_BRENT"],
            "wti": ["CRUDE_WTI"],
            "gas": ["NGAS_US", "NGAS_EUR", "NGAS_JP"],
            "natural gas": ["NGAS_US", "NGAS_EUR", "NGAS_JP"],
            "coal": ["COAL_AUS", "COAL_SAFRICA"],
            "gold": ["GOLD"],
            "silver": ["SILVER"],
            "platinum": ["PLATINUM"],
            "aluminum": ["ALUMINUM"],
            "copper": ["COPPER"],
            "nickel": ["NICKEL"],
            "zinc": ["ZINC"],
            "iron": ["IRON_ORE"],
            "wheat": ["WHEAT_US_HRW"],
            "corn": ["MAIZE"],
            "maize": ["MAIZE"],
            "soy": ["SOYBEANS"],
            "sugar": ["SUGAR_WLD"],
            "coffee": ["COFFEE_ARABIC", "COFFEE_ROBUS"],
            "cocoa": ["COCOA"],
            "cotton": ["COTTON_A_INDX"],
            "palm": ["PALM_OIL"],
            "rubber": ["RUBBER_SGP"],
            "fertilizer": ["DAP", "UREA_EE", "PHITE_ROCK"],
            "energy": ["CRUDE_BRENT", "CRUDE_WTI", "NGAS_US", "NGAS_EUR", "COAL_AUS"],
            "metal": ["GOLD", "SILVER", "COPPER", "ALUMINUM", "NICKEL", "ZINC", "IRON_ORE"],
            "agriculture": ["WHEAT_US_HRW", "MAIZE", "SOYBEANS", "SUGAR_WLD", "COFFEE_ARABIC", "COCOA"],
        }
        q = query.lower()
        matches = set()
        for kw, codes in all_commodities.items():
            if any(w in q for w in kw.split()):
                matches.update(codes)
        if matches:
            return f"Matching indicators: {', '.join(sorted(matches))}"
        return (
            "Categories: energy (oil, gas, coal), metals (gold, copper, aluminum, iron), "
            "agriculture (wheat, corn, soy, sugar, coffee, cocoa, cotton, palm oil), "
            "fertilizers (DAP, urea)"
        )


async def _fetch_pink_sheet(indicator: str, start_year, end_year) -> str:
    """Fallback: try direct commodity price endpoint."""
    # Try the CMO API endpoint
    url = "https://api.worldbank.org/v2/sources/29/indicators"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(url, params={"format": "json", "per_page": 500})
        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, list) and len(data) > 1 and data[1]:
                    matching = [
                        d for d in data[1]
                        if indicator.upper() in str(d.get("id", "")).upper()
                        or indicator.upper() in str(d.get("name", "")).upper()
                    ]
                    if matching:
                        return (
                            f"Found indicator(s) in CMO database: "
                            + ", ".join(f"{d['id']}: {d['name']}" for d in matching[:5])
                            + "\nUse imf_commodity_prices() as a more reliable alternative."
                        )
            except Exception:
                pass
    return (
        f"Could not fetch '{indicator}' from World Bank. "
        f"Try imf_commodity_prices() instead — the IMF PCPS database is more reliable "
        f"for commodity prices."
    )
