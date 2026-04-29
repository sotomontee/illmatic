"""Research Assistant — Claude-powered macro analyst with live data access."""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from data_layer import fred_get, fred_search, ecb_get, bis_get, imf_commodities, transform, _get_secret


# ── Tool definitions for Claude ─────────────────────────────────
TOOLS = [
    {
        "name": "fred_get",
        "description": "Fetch a time series from FRED (Federal Reserve Economic Data). Returns date/value pairs. Common series: DCOILBRENTEU (Brent), DCOILWTICO (WTI), DHHNGSP (Henry Hub), GOLDAMGBD228NLBM (Gold), CPIAUCSL (CPI), UNRATE (Unemployment), FEDFUNDS (Fed Funds), DGS10 (10Y Yield), DGS2 (2Y Yield), DTWEXBGS (DXY), M2SL (M2), INDPRO (Industrial Production), PCOPPUSDM (Copper), SLVPRUSD (Silver).",
        "input_schema": {
            "type": "object",
            "properties": {
                "series_id": {"type": "string", "description": "FRED series ID, e.g. DCOILBRENTEU"},
                "start": {"type": "string", "description": "Start date YYYY-MM-DD, e.g. 2020-01-01"},
                "end": {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
            },
            "required": ["series_id"],
        },
    },
    {
        "name": "fred_search",
        "description": "Search FRED for series by keyword. Returns series IDs, titles, frequency, and units. Use this when you don't know the exact series ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query, e.g. 'crude oil price'"},
                "limit": {"type": "integer", "description": "Max results (default 8)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ecb_get",
        "description": "Fetch data from ECB Statistical Data Warehouse. Common: ICP/M.U2.N.000000.4.ANR (EA HICP), EXR/D.USD.EUR.SP00.A (EUR/USD), FM/D.U2.EUR.4F.KR.DFR.LEV (ECB deposit rate).",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "description": "ECB dataset code, e.g. ICP, EXR, FM"},
                "key": {"type": "string", "description": "Series key, e.g. M.U2.N.000000.4.ANR"},
                "start": {"type": "string", "description": "Start period YYYY-MM (optional)"},
                "end": {"type": "string", "description": "End period YYYY-MM (optional)"},
            },
            "required": ["dataset", "key"],
        },
    },
    {
        "name": "imf_commodities",
        "description": "Fetch commodity prices from IMF PCPS database. Codes: POILBRE (Brent), POILWTI (WTI), PNGAS (NatGas), PCOAL (Coal), PGOLD (Gold), PSILVER (Silver), PCOPP (Copper), PALUM (Aluminum), PIRON (Iron Ore), PWHEAMT (Wheat), PMAIZMT (Corn), PSOYB (Soybeans), PSUGA (Sugar), PCOFFOTM (Coffee), PCOCO (Cocoa). Use + to combine: POILBRE+POILWTI",
        "input_schema": {
            "type": "object",
            "properties": {
                "commodities": {"type": "string", "description": "Commodity codes joined by +, e.g. POILBRE+POILWTI+PNGAS"},
                "start": {"type": "string", "description": "Start year YYYY (optional)"},
                "end": {"type": "string", "description": "End year YYYY (optional)"},
            },
            "required": ["commodities"],
        },
    },
    {
        "name": "transform_data",
        "description": "Apply a time-series transformation to the last fetched dataset. Methods: yoy (year-over-year %), mom (month-over-month %), log_diff, zscore, rolling_mean, diff, index_100.",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["yoy", "mom", "log_diff", "zscore", "rolling_mean", "diff", "index_100"]},
            },
            "required": ["method"],
        },
    },
    {
        "name": "compute_spread",
        "description": "Compute the spread (A minus B) or ratio (A divided by B) between two FRED series.",
        "input_schema": {
            "type": "object",
            "properties": {
                "series_a": {"type": "string", "description": "FRED series ID for the long leg"},
                "series_b": {"type": "string", "description": "FRED series ID for the short leg"},
                "mode": {"type": "string", "enum": ["spread", "ratio"], "description": "spread = A-B, ratio = A/B"},
                "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
            },
            "required": ["series_a", "series_b", "mode"],
        },
    },
    {
        "name": "run_regression",
        "description": "Run OLS regression with HAC standard errors between FRED series. Returns coefficients, t-stats, p-values, R-squared.",
        "input_schema": {
            "type": "object",
            "properties": {
                "y_series": {"type": "string", "description": "Dependent variable FRED series ID"},
                "x_series": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of independent variable FRED series IDs",
                },
                "y_transform": {"type": "string", "enum": ["level", "yoy", "mom", "diff", "log_diff"], "description": "Transform for Y (default: level)"},
                "x_transform": {"type": "string", "enum": ["level", "yoy", "mom", "diff", "log_diff"], "description": "Transform for all X vars (default: level)"},
                "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "hac_lags": {"type": "integer", "description": "HAC lags (default 6)"},
            },
            "required": ["y_series", "x_series"],
        },
    },
]

SYSTEM_PROMPT = """You are a senior macro research analyst embedded in Illmatic, a commodity and macro research terminal.
You have access to live data from FRED, ECB, BIS, and IMF.

Your style:
- Concise, data-driven, no fluff
- Lead with the number, then the interpretation
- When asked about a market or indicator, pull the data first, then analyze
- Reference specific levels, changes, and historical context
- Think like a commodity hedge fund analyst — what matters is positioning, relative value, and regime shifts
- Use spreads and ratios to frame cross-asset relationships
- When relevant, note what the data implies for policy, flows, or risk appetite

When you fetch data, summarize the key statistics (latest value, recent change, trend) rather than dumping raw numbers.
If a question is ambiguous, pull the most likely relevant data and ask if they want to go deeper.

The user is Javier Pradere, a macro/commodities researcher."""


def _execute_tool(name: str, inputs: dict) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if name == "fred_get":
            df = fred_get(inputs["series_id"], start=inputs.get("start"), end=inputs.get("end"))
            if df.empty:
                return "No data returned for this series."
            # Store for potential transform
            st.session_state["_assistant_last_df"] = df
            # Return summary + tail
            latest = df.iloc[-1]
            stats = {
                "series": inputs["series_id"],
                "latest_date": str(latest["date"].date()) if hasattr(latest["date"], "date") else str(latest["date"]),
                "latest_value": round(float(latest["value"]), 4),
                "observations": len(df),
                "min": round(float(df["value"].min()), 4),
                "max": round(float(df["value"].max()), 4),
                "mean": round(float(df["value"].mean()), 4),
            }
            if len(df) > 1:
                prev = df.iloc[-2]["value"]
                stats["prev_value"] = round(float(prev), 4)
                stats["change"] = round(float(latest["value"] - prev), 4)
                if prev != 0:
                    stats["change_pct"] = round(float((latest["value"] / prev - 1) * 100), 2)
            if len(df) > 12:
                yr_ago = df.iloc[-13]["value"]
                if yr_ago != 0:
                    stats["yoy_change_pct"] = round(float((latest["value"] / yr_ago - 1) * 100), 2)
            # Last 5 observations
            tail = df.tail(5)[["date", "value"]].to_dict(orient="records")
            for r in tail:
                r["date"] = str(r["date"])[:10]
                r["value"] = round(r["value"], 4)
            stats["recent_data"] = tail
            return json.dumps(stats)

        elif name == "fred_search":
            df = fred_search(inputs["query"], limit=inputs.get("limit", 8))
            if df.empty:
                return "No results found."
            return df.to_json(orient="records")

        elif name == "ecb_get":
            df = ecb_get(inputs["dataset"], inputs["key"],
                         start=inputs.get("start"), end=inputs.get("end"))
            if df.empty:
                return "No data returned."
            st.session_state["_assistant_last_df"] = df
            latest = df.iloc[-1]
            return json.dumps({
                "series": f"{inputs['dataset']}/{inputs['key']}",
                "latest_date": str(latest["date"])[:10],
                "latest_value": round(float(latest["value"]), 4),
                "observations": len(df),
                "recent_data": [{"date": str(r["date"])[:10], "value": round(r["value"], 4)}
                                for _, r in df.tail(5).iterrows()],
            })

        elif name == "imf_commodities":
            df = imf_commodities(inputs["commodities"],
                                  start=inputs.get("start"), end=inputs.get("end"))
            if df.empty:
                return "No data returned from IMF."
            st.session_state["_assistant_last_df"] = df
            # Summary per series
            summaries = []
            for s, grp in df.groupby("series"):
                latest = grp.iloc[-1]
                summaries.append({
                    "commodity": s,
                    "latest_date": str(latest["date"])[:10],
                    "latest_value": round(float(latest["value"]), 2),
                    "min": round(float(grp["value"].min()), 2),
                    "max": round(float(grp["value"].max()), 2),
                })
            return json.dumps(summaries)

        elif name == "transform_data":
            df = st.session_state.get("_assistant_last_df")
            if df is None or df.empty:
                return "No data to transform. Fetch data first."
            method = inputs["method"]
            if "series" in df.columns and df["series"].nunique() > 1:
                parts = []
                for _, grp in df.groupby("series"):
                    grp = grp.sort_values("date").reset_index(drop=True)
                    parts.append(transform(grp, method))
                result = pd.concat(parts, ignore_index=True)
            else:
                result = transform(df, method)
            st.session_state["_assistant_last_df"] = result
            return json.dumps({
                "transform": method,
                "observations": len(result),
                "recent_data": [{"date": str(r["date"])[:10], "value": round(r["value"], 4)}
                                for _, r in result.tail(5).iterrows()],
            })

        elif name == "compute_spread":
            df_a = fred_get(inputs["series_a"], start=inputs.get("start"))
            df_b = fred_get(inputs["series_b"], start=inputs.get("start"))
            merged = pd.merge(
                df_a[["date", "value"]].rename(columns={"value": "A"}),
                df_b[["date", "value"]].rename(columns={"value": "B"}),
                on="date", how="inner",
            ).sort_values("date")
            if inputs["mode"] == "ratio":
                merged["result"] = merged["A"] / merged["B"]
            else:
                merged["result"] = merged["A"] - merged["B"]
            s = merged["result"]
            current = s.iloc[-1]
            avg = s.mean()
            std = s.std()
            return json.dumps({
                "mode": inputs["mode"],
                "series_a": inputs["series_a"],
                "series_b": inputs["series_b"],
                "current": round(float(current), 4),
                "average": round(float(avg), 4),
                "std": round(float(std), 4),
                "z_score": round(float((current - avg) / std), 2) if std > 0 else 0,
                "percentile": round(float((s < current).mean() * 100), 0),
                "min": round(float(s.min()), 4),
                "max": round(float(s.max()), 4),
            })

        elif name == "run_regression":
            import statsmodels.api as sm
            y_tx = inputs.get("y_transform", "level")
            x_tx = inputs.get("x_transform", "level")
            start = inputs.get("start", "2005-01-01")
            hac_lags = inputs.get("hac_lags", 6)

            df_y = fred_get(inputs["y_series"], start=start)
            if y_tx != "level":
                df_y = transform(df_y, y_tx)
            df_y = df_y[["date", "value"]].rename(columns={"value": "Y"})
            df_y["date"] = pd.to_datetime(df_y["date"])

            merged = df_y
            x_names = []
            for xid in inputs["x_series"]:
                df_x = fred_get(xid, start=start)
                if x_tx != "level":
                    df_x = transform(df_x, x_tx)
                col = xid
                df_x = df_x[["date", "value"]].rename(columns={"value": col})
                df_x["date"] = pd.to_datetime(df_x["date"])
                merged = pd.merge(merged, df_x, on="date", how="inner")
                x_names.append(col)

            clean = merged.dropna()
            y = clean["Y"]
            X = sm.add_constant(clean[x_names])
            model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})

            coefs = []
            for var in model.params.index:
                coefs.append({
                    "variable": var,
                    "coefficient": round(float(model.params[var]), 4),
                    "std_error": round(float(model.bse[var]), 4),
                    "t_stat": round(float(model.tvalues[var]), 2),
                    "p_value": round(float(model.pvalues[var]), 4),
                })

            return json.dumps({
                "r_squared": round(float(model.rsquared), 4),
                "adj_r_squared": round(float(model.rsquared_adj), 4),
                "n_obs": int(model.nobs),
                "f_stat": round(float(model.fvalue), 2),
                "durbin_watson": round(float(sm.stats.stattools.durbin_watson(model.resid)), 3),
                "coefficients": coefs,
            })

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Error: {str(e)}"


def render():
    st.markdown("## Research Assistant")
    st.caption("Ask questions about markets, macro, and commodities — powered by Claude with live data access.")

    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        st.warning("ANTHROPIC_API_KEY not set. Add it to your `.env` file (local) or Streamlit secrets (cloud).")
        st.code('ANTHROPIC_API_KEY = "sk-ant-..."', language="toml")
        return

    if Anthropic is None:
        st.error("The `anthropic` package is not installed. Run: `pip install anthropic`")
        return

    client = Anthropic(api_key=api_key)

    # ── Chat state ──────────────────────────────────────────────
    if "assistant_messages" not in st.session_state:
        st.session_state["assistant_messages"] = []

    # ── Display chat history ────────────────────────────────────
    for msg in st.session_state["assistant_messages"]:
        if msg["role"] == "user":
            st.chat_message("user").markdown(msg["content"])
        elif msg["role"] == "assistant":
            st.chat_message("assistant").markdown(msg["content"])

    # ── Suggested prompts ───────────────────────────────────────
    if not st.session_state["assistant_messages"]:
        st.markdown('<p class="section-header">Try asking</p>', unsafe_allow_html=True)
        suggestions = [
            "What's the current Brent-WTI spread and how does it compare to its historical average?",
            "Pull CPI and unemployment data since 2020 — is the Phillips curve relationship holding?",
            "Compare gold vs copper performance YTD. What's the ratio telling us about risk appetite?",
            "Run a regression of Brent on DXY and 10Y yields since 2015. What's driving oil prices?",
            "Give me a macro snapshot: rates, DXY, energy prices, and gold. What's the regime?",
        ]
        cols = st.columns(1)
        for suggestion in suggestions:
            if st.button(f"💡 {suggestion}", key=f"sug_{hash(suggestion)}", use_container_width=True):
                st.session_state["_pending_prompt"] = suggestion
                st.rerun()

    # ── Chat input ──────────────────────────────────────────────
    prompt = st.chat_input("Ask about markets, data, or macro themes...")

    # Handle suggested prompt click
    if "_pending_prompt" in st.session_state:
        prompt = st.session_state.pop("_pending_prompt")

    if prompt:
        # Add user message
        st.session_state["assistant_messages"].append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        # Build messages for API
        api_messages = [{"role": m["role"], "content": m["content"]}
                        for m in st.session_state["assistant_messages"]]

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=api_messages,
                )

                # Handle tool use loop
                while response.stop_reason == "tool_use":
                    # Extract tool calls
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            with st.status(f"📊 {block.name}({_short_inputs(block.input)})", expanded=False):
                                result = _execute_tool(block.name, block.input)
                                st.code(result[:500] + ("..." if len(result) > 500 else ""), language="json")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                    # Continue conversation with tool results
                    api_messages.append({"role": "assistant", "content": response.content})
                    api_messages.append({"role": "user", "content": tool_results})

                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=TOOLS,
                        messages=api_messages,
                    )

                # Extract final text
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                st.markdown(final_text)

        st.session_state["assistant_messages"].append({"role": "assistant", "content": final_text})

    # ── Clear chat ──────────────────────────────────────────────
    if st.session_state["assistant_messages"]:
        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state["assistant_messages"] = []
            st.rerun()


def _short_inputs(inputs: dict) -> str:
    """Shorten tool inputs for display."""
    parts = []
    for k, v in inputs.items():
        if isinstance(v, str) and len(v) > 30:
            v = v[:27] + "..."
        parts.append(f"{k}={v}")
    return ", ".join(parts)
