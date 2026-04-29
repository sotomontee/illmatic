"""OECD.Stat connector via SDMX REST API."""

import httpx
from typing import Optional

BASE = "https://sdmx.oecd.org/public/rest/data"

# Key OECD datasets:
# MEI     — Main Economic Indicators
# QNA     — Quarterly National Accounts
# PRICES_CPI — Consumer Price Indices
# KEI     — Key Economic Indicators
# SNA_TABLE1 — GDP and components
# STLABOUR   — Short-term Labour Market Statistics
# FIN_IND    — Financial Indicators


def register(mcp):
    @mcp.tool()
    async def oecd_get(
        dataset: str,
        key: str = "",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> str:
        """Fetch data from OECD.Stat.

        dataset: OECD dataset code:
          'MEI'         — Main Economic Indicators (CLI, BCI, CCI)
          'QNA'         — Quarterly National Accounts
          'PRICES_CPI'  — Consumer Price Indices
          'KEI'         — Key Economic Indicators
          'SNA_TABLE1'  — Annual national accounts (GDP)
          'STLABOUR'    — Labour market
          'FIN_IND'     — Financial indicators (rates, yields)
          'DP_LIVE'     — OECD Data Portal live data

        key: SDMX filter. Format varies by dataset.
          For PRICES_CPI: '{country}.{subject}.{measure}.{freq}'
            e.g. 'USA.CPALTT01.GY.M' (US CPI all items, growth rate YoY, monthly)
            e.g. 'GBR+DEU+FRA.CPALTT01.GY.M' (UK, Germany, France CPI)
          For MEI: '{country}.{subject}.{measure}.{freq}'
            e.g. 'USA.CLI.AMPLITUD.M' (US Composite Leading Indicator)

        start/end: e.g. '2020-01'

        Country codes: USA, GBR, DEU, FRA, JPN, CAN, ITA, ESP, AUS, KOR, MEX, etc.
        """
        url = f"{BASE}/OECD.SDD.STES,DSD_{dataset}@DF_{dataset}/{key}" if key else f"{BASE}/OECD.SDD.STES,DSD_{dataset}@DF_{dataset}"

        # Try the simpler v1-style URL first, fall back to v2
        urls_to_try = [
            f"https://stats.oecd.org/SDMX-JSON/data/{dataset}/{key}/all",
            f"{BASE}/OECD,{dataset}/{key}",
        ]

        params = {}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end

        headers = {"Accept": "text/csv"}

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
            # Try CSV from the new API
            csv_url = f"https://sdmx.oecd.org/public/rest/data/OECD,DF_{dataset}/{key}"
            r = await c.get(csv_url, params=params, headers=headers)

            if r.status_code != 200:
                # Fallback: try older API
                json_url = f"https://stats.oecd.org/SDMX-JSON/data/{dataset}/{key}/all"
                r = await c.get(json_url, params=params)
                if r.status_code != 200:
                    return f"Could not fetch OECD {dataset}/{key} (status {r.status_code}). Try a different dataset or key format."

                # Parse JSON response
                try:
                    jdata = r.json()
                    return f"OECD {dataset}: received JSON data. Raw structure keys: {list(jdata.keys())[:5]}"
                except Exception:
                    return f"OECD {dataset}: unexpected response format"

            # Parse CSV
            lines = r.text.strip().split("\n")
            if len(lines) < 2:
                return f"No data returned for OECD {dataset}/{key}"

            header = lines[0].split(",")
            records = []
            for line in lines[1:]:
                vals = line.split(",")
                if len(vals) == len(header):
                    records.append(dict(zip(header, vals)))

            date_col = next((c for c in header if "PERIOD" in c.upper() or "TIME" in c.upper()), None)
            val_col = next((c for c in header if "OBS_VALUE" in c.upper()), None)
            ref_col = next((c for c in header if "REF_AREA" in c.upper()), None)

            if date_col and val_col:
                out = ["date,ref_area,value"] if ref_col else ["date,value"]
                for rec in records:
                    if ref_col:
                        out.append(f"{rec[date_col]},{rec.get(ref_col,'')},{rec[val_col]}")
                    else:
                        out.append(f"{rec[date_col]},{rec[val_col]}")
                return f"OECD {dataset}: {len(records)} observations\n" + "\n".join(out)
            else:
                out = [",".join(header)]
                for rec in records[:200]:
                    out.append(",".join(rec.values()))
                return f"OECD {dataset}: {len(records)} rows\n" + "\n".join(out)
