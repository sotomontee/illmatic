"""Commodity Monitor — dashboard for energy, metals, and agriculture prices."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_layer import imf_commodities, fred_get, transform


COMMODITY_GROUPS = {
    "Energy": {
        "codes": "POILBRE+POILWTI+PNGAS+PCOAL",
        "names": {"POILBRE": "Brent Crude", "POILWTI": "WTI Crude", "PNGAS": "Natural Gas", "PCOAL": "Coal"},
    },
    "Precious Metals": {
        "codes": "PGOLD+PSILVER+PPLAT",
        "names": {"PGOLD": "Gold", "PSILVER": "Silver", "PPLAT": "Platinum"},
    },
    "Base Metals": {
        "codes": "PCOPP+PALUM+PNICK+PIRON+PZINC",
        "names": {"PCOPP": "Copper", "PALUM": "Aluminum", "PNICK": "Nickel", "PIRON": "Iron Ore", "PZINC": "Zinc"},
    },
    "Agriculture": {
        "codes": "PWHEAMT+PMAIZMT+PSOYB+PSUGA+PCOFFOTM+PCOCO",
        "names": {"PWHEAMT": "Wheat", "PMAIZMT": "Corn", "PSOYB": "Soybeans", "PSUGA": "Sugar", "PCOFFOTM": "Coffee", "PCOCO": "Cocoa"},
    },
}


def render():
    st.markdown("## Commodities")

    col1, col2, col3 = st.columns(3)
    with col1:
        group = st.selectbox("Commodity Group", list(COMMODITY_GROUPS.keys()))
    with col2:
        start_year = st.text_input("Start Year", "2018")
    with col3:
        tx = st.selectbox("View", ["level", "yoy", "index_100", "mom", "rolling_mean"])

    group_info = COMMODITY_GROUPS[group]

    if st.button("📥 Load Prices", type="primary", use_container_width=True):
        with st.spinner(f"Fetching {group} prices from IMF..."):
            try:
                df = imf_commodities(group_info["codes"], start=start_year)
                if df.empty:
                    st.warning("No data returned. IMF API may be temporarily unavailable.")
                    st.info("Try the Data Explorer with FRED commodity series instead.")
                    return

                df["series"] = df["series"].map(group_info["names"]).fillna(df["series"])

                if tx != "level":
                    parts = []
                    for name, grp in df.groupby("series"):
                        grp = grp.sort_values("date").reset_index(drop=True)
                        grp = transform(grp, tx)
                        parts.append(grp)
                    df = pd.concat(parts, ignore_index=True)

                fig = px.line(df, x="date", y="value", color="series",
                              title=f"{group} Prices ({tx})", template="plotly_white")
                fig.update_layout(
                    xaxis_title="", yaxis_title="", hovermode="x unified", height=550,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=40, r=20, t=70, b=30),
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown('<p class="section-header">Summary Statistics</p>', unsafe_allow_html=True)
                stats_rows = []
                for name, grp in df.groupby("series"):
                    s = grp["value"]
                    stats_rows.append({
                        "Commodity": name,
                        "Latest": f"{s.iloc[-1]:.2f}" if len(s) > 0 else "—",
                        "1Y Ago": f"{s.iloc[-13]:.2f}" if len(s) > 12 else "—",
                        "1Y Chg %": f"{((s.iloc[-1] / s.iloc[-13]) - 1) * 100:.1f}%" if len(s) > 12 else "—",
                        "Min": f"{s.min():.2f}",
                        "Max": f"{s.max():.2f}",
                        "Avg": f"{s.mean():.2f}",
                    })
                st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)

                if df["series"].nunique() > 1:
                    with st.expander("📊 Correlation Matrix"):
                        pivot = df.pivot_table(index="date", columns="series", values="value")
                        corr = pivot.pct_change().dropna().corr()
                        fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                                              zmin=-1, zmax=1, title="Return Correlations")
                        fig_corr.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))
                        st.plotly_chart(fig_corr, use_container_width=True)

                csv = df.to_csv(index=False)
                st.download_button("⬇️ Download CSV", csv, f"commodities_{group.lower()}.csv", "text/csv")

                st.session_state["last_data"] = df
                st.session_state["last_label"] = f"{group} Commodities"

            except Exception as e:
                st.error(f"Error: {e}")
