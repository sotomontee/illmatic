"""ECB Statistical Data Warehouse connector (SDMX REST API)."""

from typing import Optional
from src.http_utils import fetch_csv

BASE = "https://data-api.ecb.europa.eu/service/data"


async def _fetch_sdmx(dataset: str, key: str, params: dict) -> list[dict]:
    """Fetch from ECB SDMX API, parse CSV response into records."""
    url = f"{BASE}/{dataset}/{key}"
    text = await fetch_csv(url, params)
    lines = text.strip().split("\n")
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
    async def ecb_get(
        dataset: str,
        key: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> str:
        """Fetch data from the ECB Statistical Data Warehouse.

        dataset: ECB dataset code, e.g. 'EXR' (exchange rates), 'ICP' (HICP inflation),
                 'BSI' (balance sheets), 'MIR' (interest rates), 'FM' (financial markets)
        key: SDMX series key, e.g. 'D.USD.EUR.SP00.A' for daily USD/EUR spot rate,
             or 'M.U2.N.000000.4.ANR' for euro area HICP YoY
        start/end: period like '2020-01' or '2020' (optional)

        Tip: use dots for dimensions, + for OR within a dimension.
        Example keys:
          EXR — D.USD.EUR.SP00.A (daily USD/EUR)
          ICP — M.U2.N.000000.4.ANR (monthly euro area HICP annual rate)
          MIR — M.U2.B.A2A.A.R.A.2240.EUR.N (new business loans rate)
        """
        params = {}
        if start:
            params["startPeriod"] = start
        if end:
            params["endPeriod"] = end
        params["detail"] = "dataonly"

        records = await _fetch_sdmx(dataset, key, params)
        if not records:
            return f"No data returned for ECB {dataset}/{key}"

        date_col = next((c for c in records[0] if "PERIOD" in c.upper() or "TIME" in c.upper()), None)
        val_col = next((c for c in records[0] if "OBS_VALUE" in c.upper()), None)

        if not date_col or not val_col:
            lines = [",".join(records[0].keys())]
            for rec in records:
                lines.append(",".join(rec.values()))
            return f"ECB {dataset}/{key}: {len(records)} rows (raw)\n" + "\n".join(lines)

        lines = ["date,value"]
        for rec in records:
            lines.append(f"{rec[date_col]},{rec[val_col]}")
        return f"ECB {dataset}/{key}: {len(records)} observations\n" + "\n".join(lines)

    @mcp.tool()
    async def ecb_search(query: str) -> str:
        """Search for ECB data series. Provides guidance on common datasets and key structures."""
        guide = {
            "exchange rate": (
                "Dataset: EXR\nKey pattern: {freq}.{currency}.EUR.SP00.A\n"
                "Examples:\n  D.USD.EUR.SP00.A — daily USD/EUR spot\n"
                "  M.GBP.EUR.SP00.A — monthly GBP/EUR\n"
                "  D.CHF+JPY.EUR.SP00.A — daily CHF and JPY vs EUR"
            ),
            "inflation": (
                "Dataset: ICP\nKey pattern: M.{area}.N.{item}.4.ANR\n"
                "Examples:\n  M.U2.N.000000.4.ANR — euro area headline HICP YoY\n"
                "  M.U2.N.XEF000.4.ANR — euro area core HICP (ex energy+food)\n"
                "  M.DE.N.000000.4.ANR — Germany HICP YoY"
            ),
            "interest rate": (
                "Dataset: FM (policy rates), MIR (bank rates)\n"
                "FM examples:\n  D.U2.EUR.4F.KR.MRR_FR.LEV — ECB main refi rate\n"
                "  D.U2.EUR.4F.KR.DFR.LEV — deposit facility rate\n"
                "MIR examples:\n  M.U2.B.A2A.A.R.A.2240.EUR.N — new business loans"
            ),
            "money supply": (
                "Dataset: BSI\nKey pattern: M.U2.N.V.M30.X.I.U2.2300.Z01.E\n"
                "This is M3 for the euro area."
            ),
            "gdp": (
                "Dataset: MNA (national accounts) — available via Eurostat connector\n"
                "ECB hosts limited national accounts; use eurostat_get for GDP data."
            ),
        }
        q = query.lower()
        matches = []
        for keyword, info in guide.items():
            if any(w in q for w in keyword.split()):
                matches.append(f"## {keyword.title()}\n{info}")
        if matches:
            return "\n\n".join(matches)
        return (
            "No exact match. Available guides: exchange rate, inflation, "
            "interest rate, money supply, gdp.\nTry ecb_get with a specific "
            "dataset and key, or use ecb_search with one of the keywords above."
        )
