"""BIS (Bank for International Settlements) connector via SDMX REST API v1."""

import csv
import io
from typing import Optional
from src.http_utils import fetch_csv

BASE = "https://stats.bis.org/api/v1/data"


def _parse_csv(text: str) -> tuple[list[str], list[dict]]:
    """Parse CSV properly handling quoted fields with commas."""
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    records = list(reader)
    return header, records


def register(mcp):
    @mcp.tool()
    async def bis_get(
        dataset: str,
        key: str = "",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> str:
        """Fetch data from the BIS Statistical Warehouse.

        dataset: BIS dataset code. Key ones:
          'WS_CBPOL'    — Central bank policy rates
          'WS_XRU'      — US dollar exchange rates
          'WS_EER'      — Effective exchange rates (real & nominal)
          'WS_SPP'      — Residential property prices
          'WS_LONG_CPI' — Long-run consumer prices
          'WS_DSR'      — Debt service ratios
          'WS_TC'       — Total credit to non-financial sector
          'WS_DEBT_SEC2'— International debt securities

        key: SDMX series key filter. Use dots between dimensions.
             Examples:
               WS_CBPOL: 'M.US' (monthly US policy rate)
               WS_CBPOL: 'M.US+GB+XM' (US, UK, and euro area)
        start/end: e.g. '2020-01'
        """
        url = f"{BASE}/{dataset}/{key}" if key else f"{BASE}/{dataset}"
        params = {"format": "csv"}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end

        text = await fetch_csv(url, params)
        header, records = _parse_csv(text)

        if not records:
            return f"No data returned for BIS {dataset}/{key}"

        date_col = next((c for c in header if c.upper() == "TIME_PERIOD"), None)
        val_col = next((c for c in header if c.upper() == "OBS_VALUE"), None)
        ref_col = next((c for c in header if c.upper() == "REF_AREA"), None)

        if date_col and val_col:
            out = ["date,ref_area,value"] if ref_col else ["date,value"]
            for rec in records:
                if ref_col:
                    out.append(f"{rec[date_col]},{rec.get(ref_col,'')},{rec[val_col]}")
                else:
                    out.append(f"{rec[date_col]},{rec[val_col]}")
            return f"BIS {dataset}: {len(records)} observations\n" + "\n".join(out)
        else:
            out = [",".join(header)]
            for rec in records[:200]:
                out.append(",".join(rec.get(h, "") for h in header))
            return f"BIS {dataset}: {len(records)} rows (raw)\n" + "\n".join(out)

    @mcp.tool()
    async def bis_search(query: str) -> str:
        """Search for BIS datasets. Returns a guide to available datasets."""
        guide = {
            "policy rate": "**WS_CBPOL** — Central bank policy rates. Key: M.{country_code} e.g. M.US, M.GB, M.XM (euro area), M.JP",
            "exchange rate": "**WS_XRU** — USD exchange rates. **WS_EER** — Effective exchange rates (real/nominal)",
            "property": "**WS_SPP** — Residential property prices by country",
            "inflation": "**WS_LONG_CPI** — Long-run CPI series",
            "credit": "**WS_TC** — Total credit to non-financial sector",
            "debt": "**WS_DEBT_SEC2** — International debt securities. **WS_DSR** — Debt service ratios",
        }
        q = query.lower()
        matches = [v for k, v in guide.items() if any(w in q for w in k.split())]
        if matches:
            return "BIS datasets:\n" + "\n".join(f"- {m}" for m in matches)
        return "Available BIS datasets:\n" + "\n".join(f"- {v}" for v in guide.values())
