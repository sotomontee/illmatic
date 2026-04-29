# claude-macro-mcp — Installation Guide

## What this is

An MCP server that gives Claude direct access to macro-economic and commodity data. Once installed, you can ask Claude things like:

- "Pull euro area HICP since 2020 and plot it"
- "Compare Brent crude and WTI prices over the last 5 years"
- "Get the Fed, ECB, and BoE policy rates since 2022 and chart them together"
- "Run a regression of unemployment on inflation using FRED data"

## Data sources (8 connectors)

| Source | API key needed? | What it covers |
|--------|----------------|----------------|
| FRED | Yes (free) | US macro — CPI, GDP, unemployment, rates, commodity prices |
| ECB SDW | No | Euro area — HICP, exchange rates, interest rates, money supply |
| Eurostat | No | EU statistics — GDP, unemployment, inflation, trade |
| BIS | No | Cross-country — policy rates, credit, property prices, debt |
| IMF | No | Global — IFS, commodity prices (PCPS), balance of payments |
| OECD | No | OECD countries — leading indicators, CPI, national accounts |
| EIA | Yes (free) | US energy — oil, gas, coal, electricity, STEO forecasts |
| World Bank | No | Commodity prices (pink sheet) — metals, agriculture, energy |

## Analytics tools (4)

- **ts_transform** — YoY, MoM, log diff, z-score, rolling stats, rebase to 100
- **ols** — OLS regression with Newey-West (HAC) standard errors
- **plot_series** — Time-series line charts to PNG
- **draft_note** — Markdown research note template

## Step 1: Get API keys

### FRED (required)
1. Go to https://fred.stlouisfed.org/docs/api/api_key.html
2. Create a free account and request an API key
3. Takes about 2 minutes

### EIA (optional, for energy data)
1. Go to https://www.eia.gov/opendata/register.php
2. Register for a free key
3. Takes about 2 minutes

## Step 2: Set up the project

Open a terminal (PowerShell or CMD) and run:

```powershell
cd C:\Users\javip\OneDrive\Escritorio\CLAUDE COWORK\claude-macro-mcp

# Copy the env template and add your keys
copy .env.template .env
# Then edit .env with your FRED_API_KEY (and optionally EIA_API_KEY)

# Install Python dependencies
pip install -e .
```

## Step 3: Wire it into Claude Desktop

Open (or create) the Claude Desktop config file:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Add this to the `mcpServers` section:

```json
{
  "mcpServers": {
    "claude-macro-mcp": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:\\Users\\javip\\OneDrive\\Escritorio\\CLAUDE COWORK\\claude-macro-mcp",
      "env": {
        "FRED_API_KEY": "your_key_here",
        "EIA_API_KEY": "your_key_here_optional"
      }
    }
  }
}
```

**Note:** If you already have other MCP servers configured, just add the `"claude-macro-mcp": {...}` block inside the existing `mcpServers` object.

## Step 4: Restart Claude Desktop

Close and reopen Claude Desktop. You should see the MCP tools icon (hammer) in the chat input area. Click it to verify `claude-macro-mcp` tools are listed.

## Step 5: Test it

Try these prompts:

1. **Basic data pull:** "Search FRED for US CPI series"
2. **Commodity prices:** "Get monthly Brent and WTI crude prices from IMF since 2020"
3. **Cross-source comparison:** "Pull euro area HICP from ECB and US CPI from FRED, both since 2020, compute YoY, and plot them together"
4. **Policy rates:** "Get Fed, ECB, and BoE policy rates from BIS since 2022"
5. **Energy data:** "Get WTI and Brent spot prices from EIA for the last 2 years"

## Troubleshooting

- **"FRED_API_KEY not set"** — Make sure your `.env` file exists and has the key, OR pass it via the `env` block in `claude_desktop_config.json`
- **Module not found** — Run `pip install -e .` from the project directory
- **Server not showing up** — Check that `claude_desktop_config.json` has valid JSON (no trailing commas)
- **ECB/BIS timeout** — These are free public APIs; occasional slowness is normal. Retry.
