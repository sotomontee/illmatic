"""
claude-macro-mcp  ·  MCP server for macro-economic research
Data sources: FRED, ECB SDW, Eurostat, BIS, IMF, OECD, EIA, World Bank Commodities
Analytics: transforms, OLS, plotting, note drafting
"""

import asyncio
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP(
    "claude-macro-mcp",
    instructions="Macro-economic data & analytics MCP server for research. Data sources: FRED, ECB, Eurostat, BIS, IMF, OECD, EIA, World Bank. Tools: transforms, OLS regression, plotting, note drafting.",
)

# ── Data connectors ──────────────────────────────────────────────
from src.connectors.fred import register as register_fred
from src.connectors.ecb import register as register_ecb
from src.connectors.eurostat import register as register_eurostat
from src.connectors.bis import register as register_bis
from src.connectors.imf import register as register_imf
from src.connectors.oecd import register as register_oecd
from src.connectors.eia import register as register_eia
from src.connectors.worldbank import register as register_worldbank

register_fred(mcp)
register_ecb(mcp)
register_eurostat(mcp)
register_bis(mcp)
register_imf(mcp)
register_oecd(mcp)
register_eia(mcp)
register_worldbank(mcp)

# ── Analytics tools ──────────────────────────────────────────────
from src.tools.transforms import register as register_transforms
from src.tools.regression import register as register_regression
from src.tools.plotting import register as register_plotting
from src.tools.notes import register as register_notes

register_transforms(mcp)
register_regression(mcp)
register_plotting(mcp)
register_notes(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
