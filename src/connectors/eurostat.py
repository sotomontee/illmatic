"""Eurostat connector via JSON API."""

import httpx
from typing import Optional

BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"


async def _fetch(dataset: str, key: str, params: dict) -> list[dict]:
    """Fetch from Eurostat SDMX REST API in CSV format."""
    url = f"{BASE}/{dataset}/{key}"
    headers = {"Accept": "text/csv"}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(url, params=params, headers=headers)
        r.raise_for_status()
        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            return []
        header = lines[0].split(",")
        records = []
        for line in lines[1:]:
            vals = line.split(",")
            if len(vals) == len(header):
                records.append(dict(zip(header, vals)))
        return records


def register(mcp):
    @mcp.tool()
    async def eurostat_get(
        dataset: str,
        key: str = "",
        start: Optional[str] = None,
        end: Optional[str] = None,
        geo: Optional[str] = None,
    ) -> str:
        """Fetch data from Eurostat.

        dataset: Eurostat dataset code, e.g.:
          'prc_hicp_manr' — HICP monthly annual rate (inflation)
          'namq_10_gdp'  — quarterly GDP
          'une_rt_m'     — monthly unemployment rate
          'irt_st_m'     — money market interest rates
          'nama_10_gdp'  — annual GDP
          'prc_ppp_ind'  — purchasing power parities
          'ei_bsci_m_r2' — business/consumer surveys

        key: SDMX dimension filter (optional, use dots between dims).
             Leave empty for all, or filter like 'M.CP00.EU27_2020'
        start/end: period filter, e.g. '2020-01'
        geo: shortcut to filter by country code (e.g. 'DE', 'FR', 'EU27_2020')
        """
        params = {"format": "TSV"}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end

        # Build the URL for Eurostat's bulk download API instead
        # since the SDMX endpoint can be finicky
        bulk_url = (
            f"https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
            f"{dataset}/{key}"
        )
        headers = {"Accept": "text/csv"}
        filter_params: dict = {}
        if start:
            filter_params["startPeriod"] = start
        if end:
            filter_params["endPeriod"] = end

        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(bulk_url, params=filter_params, headers=headers)
            r.raise_for_status()
            lines = r.text.strip().split("\n")

        if len(lines) < 2:
            return f"No data returned for Eurostat {dataset}/{key}"

        header = lines[0].split(",")
        records = []
        for line in lines[1:]:
            vals = line.split(",")
            if len(vals) == len(header):
                rec = dict(zip(header, vals))
                # Filter by geo if specified
                geo_col = next((c for c in rec if c.upper() in ("GEO", "REF_AREA")), None)
                if geo and geo_col and rec[geo_col].strip().upper() != geo.upper():
                    continue
                records.append(rec)

        if not records:
            return f"No matching data for Eurostat {dataset}/{key} (geo={geo})"

        # Find date and value columns
        date_col = next((c for c in header if "PERIOD" in c.upper() or "TIME" in c.upper()), None)
        val_col = next((c for c in header if "OBS_VALUE" in c.upper()), None)

        if date_col and val_col:
            out_lines = ["date,value"]
            for rec in records:
                out_lines.append(f"{rec[date_col]},{rec[val_col]}")
            return f"Eurostat {dataset}: {len(records)} observations\n" + "\n".join(out_lines)
        else:
            # Return raw CSV
            out_lines = [",".join(header)]
            for rec in records:
                out_lines.append(",".join(rec.values()))
            return f"Eurostat {dataset}: {len(records)} rows\n" + "\n".join(out_lines[:200])

    @mcp.tool()
    async def eurostat_search(query: str, limit: int = 10) -> str:
        """Search for Eurostat datasets matching a query.
        Uses the Eurostat table of contents API."""
        url = "https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc"
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(url, params={"lang": "en"}, headers={"Accept": "application/json"})
            r.raise_for_status()
            toc = r.json()

        q_lower = query.lower()
        matches = []
        items = toc if isinstance(toc, list) else toc.get("items", toc.get("link", {}).get("item", []))

        def search_items(items_list, depth=0):
            if depth > 3 or len(matches) >= limit:
                return
            if not isinstance(items_list, list):
                return
            for item in items_list:
                if len(matches) >= limit:
                    return
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", item.get("label", "")))
                code = str(item.get("code", item.get("id", "")))
                if q_lower in title.lower() or q_lower in code.lower():
                    matches.append(f"- **{code}**: {title}")
                children = item.get("children", item.get("item", []))
                if children:
                    search_items(children, depth + 1)

        search_items(items)
        if matches:
            return f"Eurostat datasets matching '{query}':\n" + "\n".join(matches)
        # Fallback: suggest common ones
        return (
            f"No direct match for '{query}'. Common datasets:\n"
            "- **prc_hicp_manr** — HICP monthly annual rate\n"
            "- **namq_10_gdp** — quarterly GDP\n"
            "- **une_rt_m** — monthly unemployment\n"
            "- **irt_st_m** — money market rates\n"
            "- **ei_bsci_m_r2** — business/consumer surveys"
        )
