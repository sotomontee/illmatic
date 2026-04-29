"""Dashboard — the first thing you see when you open Illmatic."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_layer import fred_get, ecb_get, bis_get, imf_commodities
from datetime import datetime, timedelta


# ── Watchlist config ────────────────────────────────────────────
ENERGY_WATCHLIST = {
    "Brent": "DCOILBRENTEU",
    "WTI": "DCOILWTICO",
    "Henry Hub": "DHHNGSP",
    "RBOB Gas": "DGASREGCOASTW",
}

MACRO_WATCHLIST = {
    "Fed Funds": "FEDFUNDS",
    "10Y Yield": "DGS10",
    "2Y Yield": "DGS2",
    "DXY": "DTWEXBGS",
}

METALS_WATCHLIST = {
    "Gold": "GOLDAMGBD228NLBM",
    "Silver": "SLVPRUSD",
    "Copper": "PCOPPUSDM",
}


def _get_latest_with_change(series_id: str, label: str) -> dict:
    """Get latest value and 1-period change for a FRED series."""
    try:
        six_months_ago = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        df = fred_get(series_id, start=six_months_ago)
        if df.empty or len(df) < 2:
            return {"label": label, "value": None, "delta": None}
        latest = df.iloc[-1]["value"]
        prev = df.iloc[-2]["value"]
        delta = latest - prev
        pct = (delta / prev) * 100 if prev != 0 else 0
        return {"label": label, "value": latest, "delta": delta, "pct": pct, "df": df}
    except Exception:
        return {"label": label, "value": None, "delta": None}


def _mini_sparkline(df: pd.DataFrame, color: str = "#2563eb") -> go.Figure:
    """Create a tiny sparkline chart."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["value"],
        mode="lines", line=dict(color=color, width=1.5),
        fill="tozeroy", fillcolor=f"rgba(37,99,235,0.08)",
        hovertemplate="%{x|%b %d}: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=120, margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )
    return fig


def render():
    # ── Header ──────────────────────────────────────────────────
    col_title, col_date = st.columns([3, 1])
    with col_title:
        st.markdown("## Dashboard")
    with col_date:
        st.markdown(
            f'<p style="text-align:right; color:#888; padding-top:12px; font-size:0.85rem;">'
            f'{datetime.now().strftime("%A, %B %d %Y · %H:%M")}</p>',
            unsafe_allow_html=True,
        )

    # ── Energy prices (top row) ─────────────────────────────────
    st.markdown('<p class="section-header">Energy</p>', unsafe_allow_html=True)

    energy_data = {}
    with st.spinner("Loading energy prices..."):
        for label, sid in ENERGY_WATCHLIST.items():
            energy_data[label] = _get_latest_with_change(sid, label)

    cols = st.columns(len(ENERGY_WATCHLIST))
    for col, (label, data) in zip(cols, energy_data.items()):
        with col:
            if data["value"] is not None:
                delta_str = f"{data['pct']:+.1f}%"
                st.metric(label, f"${data['value']:.2f}", delta_str)
                if "df" in data:
                    # Last 90 days for sparkline
                    recent = data["df"].tail(90)
                    color = "#16a34a" if data["delta"] >= 0 else "#dc2626"
                    st.plotly_chart(_mini_sparkline(recent, color), use_container_width=True, key=f"spark_{label}")
            else:
                st.metric(label, "—", "")

    # ── Macro indicators ────────────────────────────────────────
    st.markdown('<p class="section-header">Rates & FX</p>', unsafe_allow_html=True)

    macro_data = {}
    with st.spinner("Loading macro indicators..."):
        for label, sid in MACRO_WATCHLIST.items():
            macro_data[label] = _get_latest_with_change(sid, label)

    cols2 = st.columns(len(MACRO_WATCHLIST))
    for col, (label, data) in zip(cols2, macro_data.items()):
        with col:
            if data["value"] is not None:
                delta_str = f"{data['delta']:+.3f}" if abs(data['delta']) < 1 else f"{data['delta']:+.2f}"
                fmt = f"{data['value']:.2f}%" if "Yield" in label or "Fed" in label else f"{data['value']:.1f}"
                st.metric(label, fmt, delta_str)
                if "df" in data:
                    recent = data["df"].tail(90)
                    color = "#16a34a" if data["delta"] >= 0 else "#dc2626"
                    st.plotly_chart(_mini_sparkline(recent, color), use_container_width=True, key=f"spark_m_{label}")
            else:
                st.metric(label, "—", "")

    # ── Metals ──────────────────────────────────────────────────
    st.markdown('<p class="section-header">Metals</p>', unsafe_allow_html=True)

    metals_data = {}
    with st.spinner("Loading metals..."):
        for label, sid in METALS_WATCHLIST.items():
            metals_data[label] = _get_latest_with_change(sid, label)

    cols3 = st.columns(len(METALS_WATCHLIST) + 1)  # +1 for spacing
    for col, (label, data) in zip(cols3, metals_data.items()):
        with col:
            if data["value"] is not None:
                delta_str = f"{data['pct']:+.1f}%"
                st.metric(label, f"${data['value']:.2f}", delta_str)
                if "df" in data:
                    recent = data["df"].tail(90)
                    color = "#16a34a" if data["delta"] >= 0 else "#dc2626"
                    st.plotly_chart(_mini_sparkline(recent, color), use_container_width=True, key=f"spark_met_{label}")
            else:
                st.metric(label, "—", "")

    # ── Energy chart (main panel) ───────────────────────────────
    st.markdown('<p class="section-header">Energy — 6 Month View</p>', unsafe_allow_html=True)

    # Build overlay chart from energy data
    fig = go.Figure()
    colors = {"Brent": "#2563eb", "WTI": "#16a34a", "Henry Hub": "#f59e0b", "RBOB Gas": "#8b5cf6"}

    for label, data in energy_data.items():
        if data.get("df") is not None and not data["df"].empty:
            df = data["df"].tail(180)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["value"],
                name=label, mode="lines",
                line=dict(color=colors.get(label, "#888"), width=2),
                hovertemplate=f"{label}: $%{{y:.2f}}<extra></extra>",
            ))

    fig.update_layout(
        height=450,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=50, r=20, t=10, b=30),
        yaxis_title="USD",
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(step="all", label="ALL"),
                ]
            ),
            rangeslider=dict(visible=False),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Key spreads snapshot ────────────────────────────────────
    st.markdown('<p class="section-header">Key Spreads</p>', unsafe_allow_html=True)

    brent = energy_data.get("Brent", {})
    wti = energy_data.get("WTI", {})

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        if brent.get("value") and wti.get("value"):
            spread = brent["value"] - wti["value"]
            st.metric("Brent-WTI Spread", f"${spread:.2f}", "")
        else:
            st.metric("Brent-WTI Spread", "—", "")

    ff = macro_data.get("Fed Funds", {})
    with sc2:
        t10 = macro_data.get("10Y Yield", {})
        t2 = macro_data.get("2Y Yield", {})
        if t10.get("value") and t2.get("value"):
            curve = t10["value"] - t2["value"]
            st.metric("2s10s Spread", f"{curve:.2f}%", "")
        else:
            st.metric("2s10s Spread", "—", "")

    with sc3:
        gold = metals_data.get("Gold", {})
        silver = metals_data.get("Silver", {})
        if gold.get("value") and silver.get("value") and silver["value"] > 0:
            ratio = gold["value"] / silver["value"]
            st.metric("Gold/Silver Ratio", f"{ratio:.1f}x", "")
        else:
            st.metric("Gold/Silver Ratio", "—", "")
