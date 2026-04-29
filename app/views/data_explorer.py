"""Data Explorer — multi-series overlay charts with transforms."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_layer import fred_search, fred_get, ecb_get, bis_get, imf_commodities, transform


QUICK_ADD = {
    "Brent Crude": ("FRED", "DCOILBRENTEU"),
    "WTI Crude": ("FRED", "DCOILWTICO"),
    "Henry Hub Gas": ("FRED", "DHHNGSP"),
    "Gold": ("FRED", "GOLDAMGBD228NLBM"),
    "Copper": ("FRED", "PCOPPUSDM"),
    "US CPI": ("FRED", "CPIAUCSL"),
    "Core CPI": ("FRED", "CPILFESL"),
    "Unemployment": ("FRED", "UNRATE"),
    "Fed Funds": ("FRED", "FEDFUNDS"),
    "10Y Yield": ("FRED", "DGS10"),
    "2Y Yield": ("FRED", "DGS2"),
    "DXY": ("FRED", "DTWEXBGS"),
    "M2 Supply": ("FRED", "M2SL"),
    "Industrial Prod.": ("FRED", "INDPRO"),
    "EUR/USD": ("ECB", "EXR|D.USD.EUR.SP00.A"),
    "EA HICP": ("ECB", "ICP|M.U2.N.000000.4.ANR"),
}

COLORS = ["#2563eb", "#dc2626", "#16a34a", "#f59e0b", "#8b5cf6",
          "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"]


def render():
    st.markdown("## Data Explorer")

    # ── Workspace state ─────────────────────────────────────────
    if "workspace_series" not in st.session_state:
        st.session_state["workspace_series"] = []

    # ── Add series ──────────────────────────────────────────────
    st.markdown('<p class="section-header">Add Series</p>', unsafe_allow_html=True)

    tab_quick, tab_search, tab_manual = st.tabs(["QUICK ADD", "FRED SEARCH", "MANUAL"])

    with tab_quick:
        cols = st.columns(4)
        for i, (name, (src, sid)) in enumerate(QUICK_ADD.items()):
            with cols[i % 4]:
                if st.button(name, key=f"qa_{name}", use_container_width=True):
                    _add_series(name, src, sid)

    with tab_search:
        query = st.text_input("Search FRED", placeholder="e.g. crude oil price")
        if query:
            with st.spinner("Searching..."):
                try:
                    results = fred_search(query, limit=8)
                    if not results.empty:
                        for _, row in results.iterrows():
                            col_a, col_b = st.columns([4, 1])
                            with col_a:
                                st.markdown(f"**{row['id']}** — {row['title']} ({row['freq']}, {row['units']})")
                            with col_b:
                                if st.button("Add", key=f"add_{row['id']}"):
                                    _add_series(row["id"], "FRED", row["id"])
                except Exception as e:
                    st.error(f"Search error: {e}")

    with tab_manual:
        mc1, mc2, mc3 = st.columns([1, 1, 2])
        with mc1:
            m_source = st.selectbox("Source", ["FRED", "ECB", "BIS"])
        with mc2:
            m_label = st.text_input("Label", placeholder="e.g. Brent")
        with mc3:
            if m_source == "FRED":
                m_id = st.text_input("Series ID", placeholder="e.g. DCOILBRENTEU")
            elif m_source == "ECB":
                m_id = st.text_input("Dataset|Key", placeholder="e.g. ICP|M.U2.N.000000.4.ANR")
            else:
                m_id = st.text_input("Dataset|Key", placeholder="e.g. WS_CBPOL|M.US")

        if st.button("➕ Add to workspace"):
            if m_id:
                _add_series(m_label or m_id, m_source, m_id)

    # ── Current workspace ───────────────────────────────────────
    ws = st.session_state["workspace_series"]
    if ws:
        st.markdown('<p class="section-header">Workspace</p>', unsafe_allow_html=True)

        # Show active series as tags
        tag_cols = st.columns(min(len(ws) + 1, 8))
        for i, s in enumerate(ws):
            with tag_cols[i % 7]:
                color = COLORS[i % len(COLORS)]
                st.markdown(
                    f'<span style="background:{color}; color:white; padding:3px 10px; '
                    f'border-radius:12px; font-size:0.75rem; font-weight:600;">'
                    f'{s["label"]}</span>',
                    unsafe_allow_html=True,
                )
        with tag_cols[-1]:
            if st.button("🗑️ Clear all"):
                st.session_state["workspace_series"] = []
                st.rerun()

        # ── Controls ────────────────────────────────────────────
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            start = st.text_input("Start", "2018-01-01", key="ws_start")
        with cc2:
            end = st.text_input("End", "", key="ws_end")
        with cc3:
            tx = st.selectbox("Transform", [
                "level", "yoy", "mom", "index_100", "log_diff",
                "zscore", "rolling_mean", "diff"
            ])
        with cc4:
            dual_axis = st.checkbox("Dual Y-axis", value=len(ws) == 2)

        # ── Fetch & Plot ────────────────────────────────────────
        if st.button("📊 Plot", type="primary", use_container_width=True):
            with st.spinner("Fetching data..."):
                all_dfs = []
                for s in ws:
                    try:
                        df = _fetch_series(s, start, end)
                        if tx != "level":
                            df = transform(df, tx)
                        df["label"] = s["label"]
                        all_dfs.append(df)
                    except Exception as e:
                        st.warning(f"Failed to fetch {s['label']}: {e}")

                if not all_dfs:
                    st.error("No data fetched.")
                    return

                # ── Build chart ─────────────────────────────────
                fig = go.Figure() if not dual_axis else _make_dual_axis()

                for i, df in enumerate(all_dfs):
                    color = COLORS[i % len(COLORS)]
                    yaxis = "y2" if dual_axis and i == 1 else "y"

                    fig.add_trace(go.Scatter(
                        x=df["date"], y=df["value"],
                        name=df["label"].iloc[0],
                        mode="lines",
                        line=dict(color=color, width=2),
                        yaxis=yaxis,
                        hovertemplate=f"{df['label'].iloc[0]}: %{{y:.2f}}<extra></extra>",
                    ))

                title = " vs ".join(s["label"] for s in ws)
                if tx != "level":
                    title += f" ({tx})"

                layout_kwargs = dict(
                    title=dict(text=title, font=dict(size=15)),
                    height=550,
                    template="plotly_white",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    margin=dict(l=50, r=50 if dual_axis else 20, t=60, b=30),
                    xaxis=dict(
                        rangeselector=dict(
                            buttons=[
                                dict(count=3, label="3M", step="month"),
                                dict(count=6, label="6M", step="month"),
                                dict(count=1, label="1Y", step="year"),
                                dict(count=3, label="3Y", step="year"),
                                dict(count=5, label="5Y", step="year"),
                                dict(step="all", label="ALL"),
                            ]
                        ),
                        rangeslider=dict(visible=False),
                    ),
                )

                if dual_axis and len(all_dfs) >= 2:
                    layout_kwargs["yaxis"] = dict(title=ws[0]["label"], titlefont=dict(color=COLORS[0]))
                    layout_kwargs["yaxis2"] = dict(
                        title=ws[1]["label"], titlefont=dict(color=COLORS[1]),
                        overlaying="y", side="right",
                    )

                fig.update_layout(**layout_kwargs)
                st.plotly_chart(fig, use_container_width=True)

                # ── Correlation (if multiple) ───────────────────
                if len(all_dfs) >= 2:
                    with st.expander("📊 Statistics & Correlation"):
                        # Merge all on date
                        merged = all_dfs[0][["date", "value"]].rename(columns={"value": ws[0]["label"]})
                        for i, df in enumerate(all_dfs[1:], 1):
                            right = df[["date", "value"]].rename(columns={"value": ws[i]["label"]})
                            merged = pd.merge(merged, right, on="date", how="inner")

                        numeric_cols = [c for c in merged.columns if c != "date"]
                        corr = merged[numeric_cols].corr()
                        st.dataframe(corr.style.format("{:.3f}"), use_container_width=True)

                # ── Data table ──────────────────────────────────
                combined = pd.concat(all_dfs, ignore_index=True)
                with st.expander("📋 Data table"):
                    st.dataframe(combined, use_container_width=True)

                csv = combined.to_csv(index=False)
                st.download_button("⬇️ Download CSV", csv, "workspace_data.csv", "text/csv")

                # Store for other pages
                st.session_state["last_data"] = combined
                st.session_state["last_label"] = title

    else:
        st.info("Add series using Quick Add, FRED Search, or Manual entry above.")


def _add_series(label: str, source: str, series_id: str):
    """Add a series to the workspace."""
    ws = st.session_state.get("workspace_series", [])
    # Avoid duplicates
    if not any(s["id"] == series_id for s in ws):
        ws.append({"label": label, "source": source, "id": series_id})
        st.session_state["workspace_series"] = ws


def _fetch_series(s: dict, start: str, end: str) -> pd.DataFrame:
    """Fetch a series based on its source."""
    source = s["source"]
    sid = s["id"]

    if source == "FRED":
        return fred_get(sid, start=start or None, end=end or None)
    elif source == "ECB":
        parts = sid.split("|")
        dataset, key = parts[0], parts[1]
        return ecb_get(dataset, key, start=start[:7] if start else None, end=end[:7] if end else None)
    elif source == "BIS":
        parts = sid.split("|")
        dataset, key = parts[0], parts[1]
        return bis_get(dataset, key, start=start[:7] if start else None, end=end[:7] if end else None)
    else:
        raise ValueError(f"Unknown source: {source}")


def _make_dual_axis():
    """Create a figure configured for dual Y-axes."""
    return go.Figure()
