"""Spreads & Ratios — energy spreads, cross-asset ratios, curve analysis."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_layer import fred_get, transform


SPREAD_PRESETS = {
    "Brent–WTI Spread": {
        "long": ("DCOILBRENTEU", "Brent"),
        "short": ("DCOILWTICO", "WTI"),
        "unit": "$/bbl",
        "desc": "Intercontinental crude spread — widens on Atlantic Basin tightness, Midland pipeline constraints, or geopolitical risk premium.",
    },
    "2s10s Treasury Curve": {
        "long": ("DGS10", "10Y"),
        "short": ("DGS2", "2Y"),
        "unit": "%",
        "desc": "Yield curve slope — inversion historically signals recession within 12–18 months.",
    },
    "Gold/Silver Ratio": {
        "long": ("GOLDAMGBD228NLBM", "Gold"),
        "short": ("SLVPRUSD", "Silver"),
        "mode": "ratio",
        "unit": "x",
        "desc": "Risk-off barometer — rises in flight to quality, falls when industrial demand leads.",
    },
    "Real 10Y Rate (10Y – Breakeven)": {
        "long": ("DGS10", "10Y Nominal"),
        "short": ("T10YIE", "10Y Breakeven"),
        "unit": "%",
        "desc": "Real interest rate — key driver for gold, growth/value rotation, and EM flows.",
    },
    "WTI–Henry Hub Energy Ratio": {
        "long": ("DCOILWTICO", "WTI"),
        "short": ("DHHNGSP", "Henry Hub"),
        "mode": "ratio",
        "unit": "x",
        "desc": "Oil vs gas relative value — structural shifts from LNG export capacity, seasonal demand.",
    },
    "Copper/Gold Ratio": {
        "long": ("PCOPPUSDM", "Copper"),
        "short": ("GOLDAMGBD228NLBM", "Gold"),
        "mode": "ratio",
        "unit": "x",
        "desc": "Growth vs safety — copper/gold tracks global PMIs and risk appetite.",
    },
}


def render():
    st.markdown("## Spreads & Ratios")
    st.caption("Pre-built spread charts with context. Select a spread or build your own.")

    tab1, tab2 = st.tabs(["PRESETS", "CUSTOM"])

    with tab1:
        _render_presets()

    with tab2:
        _render_custom()


def _render_presets():
    col1, col2 = st.columns([1, 3])

    with col1:
        selected = st.radio(
            "Select spread",
            list(SPREAD_PRESETS.keys()),
            label_visibility="collapsed",
        )
        start = st.text_input("Start date", "2018-01-01", key="sp_start")

    with col2:
        preset = SPREAD_PRESETS[selected]
        mode = preset.get("mode", "spread")

        with st.spinner("Calculating..."):
            try:
                long_id, long_name = preset["long"]
                short_id, short_name = preset["short"]

                df_long = fred_get(long_id, start=start)
                df_short = fred_get(short_id, start=start)

                if df_long.empty or df_short.empty:
                    st.warning("Could not fetch one or both series.")
                    return

                # Merge on date
                merged = pd.merge(
                    df_long[["date", "value"]].rename(columns={"value": "long"}),
                    df_short[["date", "value"]].rename(columns={"value": "short"}),
                    on="date", how="inner",
                ).sort_values("date")

                if mode == "ratio":
                    merged["spread"] = merged["long"] / merged["short"]
                    ylabel = f"{long_name}/{short_name} ({preset['unit']})"
                else:
                    merged["spread"] = merged["long"] - merged["short"]
                    ylabel = f"{long_name} – {short_name} ({preset['unit']})"

                # ── Chart ───────────────────────────────────────
                fig = make_subplots(
                    rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.65, 0.35],
                    vertical_spacing=0.06,
                )

                # Top: the two series
                fig.add_trace(go.Scatter(
                    x=merged["date"], y=merged["long"],
                    name=long_name, mode="lines",
                    line=dict(color="#2563eb", width=2),
                ), row=1, col=1)

                fig.add_trace(go.Scatter(
                    x=merged["date"], y=merged["short"],
                    name=short_name, mode="lines",
                    line=dict(color="#dc2626", width=2),
                ), row=1, col=1)

                # Bottom: the spread
                colors = ["#16a34a" if v >= 0 else "#dc2626" for v in merged["spread"]] if mode != "ratio" else ["#2563eb"] * len(merged)

                if mode == "ratio":
                    fig.add_trace(go.Scatter(
                        x=merged["date"], y=merged["spread"],
                        name="Ratio", mode="lines",
                        line=dict(color="#8b5cf6", width=2),
                        fill="tozeroy", fillcolor="rgba(139,92,246,0.1)",
                    ), row=2, col=1)
                    # Add mean line
                    mean_val = merged["spread"].mean()
                    fig.add_hline(y=mean_val, line_dash="dash", line_color="#888",
                                  annotation_text=f"Avg: {mean_val:.1f}x",
                                  row=2, col=1)
                else:
                    fig.add_trace(go.Bar(
                        x=merged["date"], y=merged["spread"],
                        name="Spread", marker_color=colors,
                        opacity=0.7,
                    ), row=2, col=1)
                    fig.add_hline(y=0, line_dash="solid", line_color="#888", row=2, col=1)
                    mean_val = merged["spread"].mean()
                    fig.add_hline(y=mean_val, line_dash="dash", line_color="#f59e0b",
                                  annotation_text=f"Avg: {mean_val:.2f}",
                                  row=2, col=1)

                fig.update_layout(
                    title=dict(text=selected, font=dict(size=16)),
                    height=600,
                    template="plotly_white",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    margin=dict(l=50, r=20, t=60, b=30),
                    xaxis2=dict(
                        rangeselector=dict(
                            buttons=[
                                dict(count=3, label="3M", step="month"),
                                dict(count=6, label="6M", step="month"),
                                dict(count=1, label="1Y", step="year"),
                                dict(count=3, label="3Y", step="year"),
                                dict(step="all", label="ALL"),
                            ]
                        ),
                    ),
                )

                st.plotly_chart(fig, use_container_width=True)

                # ── Stats ───────────────────────────────────────
                spread_s = merged["spread"]
                current = spread_s.iloc[-1]
                avg = spread_s.mean()
                std = spread_s.std()
                z = (current - avg) / std if std > 0 else 0
                pctl = (spread_s < current).mean() * 100

                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("Current", f"{current:.2f}")
                sc2.metric("Average", f"{avg:.2f}")
                sc3.metric("Z-Score", f"{z:+.2f}")
                sc4.metric("Percentile", f"{pctl:.0f}th")

                st.caption(preset["desc"])

            except Exception as e:
                st.error(f"Error: {e}")


def _render_custom():
    st.markdown("Build a custom spread from any two FRED series.")

    col1, col2, col3 = st.columns(3)
    with col1:
        long_id = st.text_input("Long leg (FRED ID)", placeholder="e.g. DCOILBRENTEU")
    with col2:
        short_id = st.text_input("Short leg (FRED ID)", placeholder="e.g. DCOILWTICO")
    with col3:
        mode = st.selectbox("Mode", ["Spread (A–B)", "Ratio (A/B)"])

    start = st.text_input("Start date", "2018-01-01", key="custom_sp_start")

    if st.button("📐 Calculate", type="primary", use_container_width=True):
        if not long_id or not short_id:
            st.warning("Enter both series IDs.")
            return

        with st.spinner("Fetching..."):
            try:
                df_a = fred_get(long_id, start=start)
                df_b = fred_get(short_id, start=start)
                merged = pd.merge(
                    df_a[["date", "value"]].rename(columns={"value": "A"}),
                    df_b[["date", "value"]].rename(columns={"value": "B"}),
                    on="date", how="inner",
                ).sort_values("date")

                if "Ratio" in mode:
                    merged["result"] = merged["A"] / merged["B"]
                    title = f"{long_id} / {short_id}"
                else:
                    merged["result"] = merged["A"] - merged["B"]
                    title = f"{long_id} – {short_id}"

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=merged["date"], y=merged["result"],
                    mode="lines", line=dict(color="#2563eb", width=2),
                    fill="tozeroy", fillcolor="rgba(37,99,235,0.08)",
                ))
                avg = merged["result"].mean()
                fig.add_hline(y=avg, line_dash="dash", line_color="#f59e0b",
                              annotation_text=f"Avg: {avg:.2f}")

                fig.update_layout(
                    title=title, height=450, template="plotly_white",
                    hovermode="x unified", margin=dict(l=50, r=20, t=50, b=30),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Stats
                s = merged["result"]
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Current", f"{s.iloc[-1]:.2f}")
                mc2.metric("Average", f"{avg:.2f}")
                mc3.metric("Z-Score", f"{(s.iloc[-1] - avg) / s.std():+.2f}" if s.std() > 0 else "—")
                mc4.metric("Percentile", f"{(s < s.iloc[-1]).mean() * 100:.0f}th")

            except Exception as e:
                st.error(f"Error: {e}")
