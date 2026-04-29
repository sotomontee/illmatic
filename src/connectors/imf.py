"""IMF data connector (IFS, WEO, PCPS) via JSON REST API."""

from typing import Optional
from src.http_utils import fetch_json

BASE = "http://dataservices.imf.org/REST/SDMX_JSON.svc"


async def _fetch_imf(database: str, dimensions: str, params: dict) -> dict:
    """Fetch from IMF SDMX JSON API."""
    url = f"{BASE}/CompactData/{database}/{dimensions}"
    return await fetch_json(url, params, timeout=60)


def _parse_compact(data: dict) -> list[dict]:
    """Parse IMF CompactData JSON into flat records."""
    records = []
    try:
        dataset = data.get("CompactData", {}).get("DataSet", {})
        series_list = dataset.get("Series", [])
        if isinstance(series_list, dict):
            series_list = [series_list]
        for series in series_list:
            ref_area = series.get("@REF_AREA", "")
            indicator = series.get("@INDICATOR", "")
            obs = series.get("Obs", [])
            if isinstance(obs, dict):
                obs = [obs]
            for o in obs:
                records.append({
                    "ref_area": ref_area,
                    "indicator": indicator,
                    "date": o.get("@TIME_PERIOD", ""),
                    "value": o.get("@OBS_VALUE", ""),
                })
    except (KeyError, TypeError):
        pass
    return records


def register(mcp):
    @mcp.tool()
    async def imf_get(
        database: str,
        dimensions: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> str:
        """Fetch data from the IMF.

        database: IMF database code:
          'IFS'  — International Financial Statistics (rates, prices, money, trade)
          'PCPS' — Primary Commodity Prices (monthly — oil, gas, metals, agriculture!)
          'DOT'  — Direction of Trade
          'BOP'  — Balance of Payments

        dimensions: dot-separated dimension filter.
          For IFS:  '{freq}.{ref_area}.{indicator}'
            e.g. 'M.US.PCPI_IX' (monthly US CPI index)
            e.g. 'Q.US.NGDP_R_SA_XDC' (quarterly US real GDP)
          For PCPS: '{freq}.{commodity}'
            e.g. 'M.POILBRE' (monthly Brent crude)
            e.g. 'M.PNGAS' (monthly natural gas)
            e.g. 'M.PGOLD' (monthly gold)
            e.g. 'M.PALUM' (monthly aluminum)
          Use + for multiple: 'M.POILBRE+POILWTI+PNGAS'

        start/end: e.g. '2020'

        Common PCPS commodity codes:
          POILBRE — Brent crude     POILWTI — WTI crude
          PNGAS   — Natural gas     PCOAL   — Coal
          PGOLD   — Gold            PSILVER — Silver
          PCOPP   — Copper          PALUM   — Aluminum
          PNICK   — Nickel          PIRON   — Iron ore
          PWHEAMT — Wheat           PMAIZMT — Corn/maize
          PSOYB   — Soybeans        PSUGA   — Sugar
          PCOFFOTM— Coffee          PCOCO   — Cocoa
        """
        params = {}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end

        data = await _fetch_imf(database, dimensions, params)
        records = _parse_compact(data)

        if not records:
            return f"No data returned for IMF {database}/{dimensions}"

        has_multi = len(set(r["ref_area"] + r["indicator"] for r in records)) > 1
        if has_multi:
            lines = ["date,ref_area,indicator,value"]
            for r in records:
                lines.append(f"{r['date']},{r['ref_area']},{r['indicator']},{r['value']}")
        else:
            lines = ["date,value"]
            for r in records:
                lines.append(f"{r['date']},{r['value']}")

        return f"IMF {database}: {len(records)} observations\n" + "\n".join(lines)

    @mcp.tool()
    async def imf_commodity_prices(
        commodities: str = "POILBRE+POILWTI+PNGAS+PGOLD",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> str:
        """Quick shortcut: fetch monthly commodity prices from the IMF PCPS database.

        commodities: '+'-separated codes. Defaults to Brent, WTI, NatGas, Gold.
        Common codes:
          Energy: POILBRE, POILWTI, PNGAS, PCOAL
          Precious: PGOLD, PSILVER, PPLAT
          Base metals: PCOPP, PALUM, PNICK, PIRON, PZINC, PLEAD, PTIN
          Agriculture: PWHEAMT, PMAIZMT, PSOYB, PSUGA, PCOFFOTM, PCOCO, PCOTT
        start/end: e.g. '2020'
        """
        dims = f"M.{commodities}"
        params = {}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end

        data = await _fetch_imf("PCPS", dims, params)
        records = _parse_compact(data)

        if not records:
            return "No commodity price data returned."

        lines = ["date,commodity,value"]
        for r in records:
            lines.append(f"{r['date']},{r['indicator']},{r['value']}")
        return f"IMF Commodity Prices: {len(records)} observations\n" + "\n".join(lines)
