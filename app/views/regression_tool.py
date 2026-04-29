"""Regression Tool — OLS with HAC standard errors."""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from data_layer import fred_get, ecb_get, transform


PRESET_REGRESSIONS = {
    "Oil ~ DXY + Rates + VIX": {
        "y": ("DCOILBRENTEU", "brent", "level"),
        "x": [("DTWEXBGS", "dxy", "level"), ("DGS10", "us10y", "level")],
        "desc": "Does the dollar and rate environment explain oil prices?",
    },
    "CPI ~ M2 + Unemployment": {
        "y": ("CPIAUCSL", "cpi", "yoy"),
        "x": [("M2SL", "m2", "yoy"), ("UNRATE", "urate", "level")],
        "desc": "Monetarist vs. Phillips curve drivers of inflation.",
    },
    "Gold ~ Real Rates + DXY": {
        "y": ("GOLDAMGBD228NLBM", "gold", "yoy"),
        "x": [("DFII10", "real10y", "level"), ("DTWEXBGS", "dxy", "yoy")],
        "desc": "Gold as a real-rate and dollar hedge.",
    },
}


def render():
    st.markdown("## Regression")
    st.caption("OLS with Newey-West (HAC) standard errors — build a dataset, specify your model, inspect diagnostics.")

    tab1, tab2 = st.tabs(["BUILD YOUR OWN", "PRESETS"])

    with tab1:
        _render_custom()

    with tab2:
        _render_presets()


def _render_custom():
    # ── Variable builder ────────────────────────────────────────
    st.markdown('<p class="section-header">1 · Add Variables</p>', unsafe_allow_html=True)
    st.caption("Add FRED series to build a regression dataset. Each series becomes a column.")

    if "reg_data" not in st.session_state:
        st.session_state["reg_data"] = pd.DataFrame()
    if "reg_series" not in st.session_state:
        st.session_state["reg_series"] = []

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        series_id = st.text_input("FRED Series ID", placeholder="e.g. UNRATE, CPIAUCSL")
    with col2:
        col_name = st.text_input("Column name", placeholder="e.g. unemployment")
    with col3:
        tx = st.selectbox("Transform", ["level", "yoy", "mom", "diff", "log_diff"], key="reg_tx")
    with col4:
        start = st.text_input("Start", "2000-01-01", key="reg_start")

    bc1, bc2 = st.columns([1, 1])
    with bc1:
        if st.button("➕ Add Variable", use_container_width=True):
            if series_id and col_name:
                with st.spinner(f"Fetching {series_id}..."):
                    try:
                        df = fred_get(series_id, start=start)
                        if tx != "level":
                            df = transform(df, tx)
                        df = df[["date", "value"]].rename(columns={"value": col_name})
                        df["date"] = pd.to_datetime(df["date"])

                        if st.session_state["reg_data"].empty:
                            st.session_state["reg_data"] = df
                        else:
                            st.session_state["reg_data"] = pd.merge(
                                st.session_state["reg_data"], df, on="date", how="outer"
                            ).sort_values("date")

                        st.session_state["reg_series"].append(col_name)
                        st.success(f"Added '{col_name}' ({series_id}, {tx})")
                    except Exception as e:
                        st.error(f"Error: {e}")
    with bc2:
        if st.button("🗑️ Clear all variables", use_container_width=True):
            st.session_state["reg_data"] = pd.DataFrame()
            st.session_state["reg_series"] = []
            st.rerun()

    # ── Show current dataset ────────────────────────────────────
    reg_df = st.session_state["reg_data"]
    if not reg_df.empty:
        st.markdown(f"**Variables loaded:** {', '.join(st.session_state['reg_series'])}")
        with st.expander("📋 Preview dataset"):
            st.dataframe(reg_df.dropna().tail(20), use_container_width=True, hide_index=True)

        _run_regression(reg_df)
    else:
        st.info("Add variables using the form above to get started.")


def _render_presets():
    st.markdown('<p class="section-header">Preset Regressions</p>', unsafe_allow_html=True)
    st.caption("Quick-fire common macro regressions.")

    selected = st.selectbox("Select preset", list(PRESET_REGRESSIONS.keys()))
    preset = PRESET_REGRESSIONS[selected]
    st.caption(preset["desc"])

    start = st.text_input("Start date", "2005-01-01", key="preset_reg_start")

    if st.button("🔬 Run Preset", type="primary", use_container_width=True):
        with st.spinner("Fetching data & running regression..."):
            try:
                # Fetch dependent variable
                y_id, y_name, y_tx = preset["y"]
                df_y = fred_get(y_id, start=start)
                if y_tx != "level":
                    df_y = transform(df_y, y_tx)
                df_y = df_y[["date", "value"]].rename(columns={"value": y_name})
                df_y["date"] = pd.to_datetime(df_y["date"])

                merged = df_y
                x_names = []
                for x_id, x_name, x_tx in preset["x"]:
                    df_x = fred_get(x_id, start=start)
                    if x_tx != "level":
                        df_x = transform(df_x, x_tx)
                    df_x = df_x[["date", "value"]].rename(columns={"value": x_name})
                    df_x["date"] = pd.to_datetime(df_x["date"])
                    merged = pd.merge(merged, df_x, on="date", how="outer").sort_values("date")
                    x_names.append(x_name)

                _run_regression(merged, y_override=y_name, x_override=x_names)
            except Exception as e:
                st.error(f"Error: {e}")


def _run_regression(reg_df, y_override=None, x_override=None):
    """Run OLS regression on the provided dataframe."""
    st.markdown('<p class="section-header">2 · Specify Model</p>', unsafe_allow_html=True)
    numeric_cols = [c for c in reg_df.columns if c != "date"]

    if len(numeric_cols) < 2:
        st.info("Add at least 2 variables to run a regression.")
        return

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        default_y = numeric_cols.index(y_override) if y_override and y_override in numeric_cols else 0
        y_var = st.selectbox("Dependent variable (Y)", numeric_cols, index=default_y)
    with col_b:
        default_x = x_override if x_override else []
        available_x = [c for c in numeric_cols if c != y_var]
        x_vars = st.multiselect("Independent variables (X)", available_x, default=[x for x in default_x if x in available_x])
    with col_c:
        hac_lags = st.number_input("HAC lags", min_value=0, max_value=24, value=6)

    if x_vars and st.button("🔬 Run Regression", type="primary", use_container_width=True, key="run_reg_main"):
        with st.spinner("Running OLS..."):
            try:
                import statsmodels.api as sm

                clean = reg_df[["date", y_var] + x_vars].dropna()
                y = clean[y_var]
                X = sm.add_constant(clean[x_vars])

                model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})

                # ── Results ──────────────────────────────────
                st.markdown('<p class="section-header">3 · Results</p>', unsafe_allow_html=True)

                met1, met2, met3, met4 = st.columns(4)
                met1.metric("R²", f"{model.rsquared:.4f}")
                met2.metric("Adj R²", f"{model.rsquared_adj:.4f}")
                met3.metric("N", f"{int(model.nobs)}")
                met4.metric("F-stat", f"{model.fvalue:.2f}")

                # Coefficients table
                coef_df = pd.DataFrame({
                    "Variable": model.params.index,
                    "Coefficient": model.params.values,
                    "Std Error (HAC)": model.bse.values,
                    "t-stat": model.tvalues.values,
                    "p-value": model.pvalues.values,
                })
                coef_df["Sig"] = coef_df["p-value"].apply(
                    lambda p: "***" if p < 0.01 else ("**" if p < 0.05 else ("*" if p < 0.1 else ""))
                )
                st.dataframe(coef_df.style.format({
                    "Coefficient": "{:.4f}", "Std Error (HAC)": "{:.4f}",
                    "t-stat": "{:.2f}", "p-value": "{:.4f}",
                }), use_container_width=True, hide_index=True)

                # ── Diagnostics ──────────────────────────────
                st.markdown('<p class="section-header">4 · Diagnostics</p>', unsafe_allow_html=True)

                resid_df = pd.DataFrame({
                    "date": clean["date"].values,
                    "residual": model.resid.values,
                    "fitted": model.fittedvalues.values,
                })

                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    fig_resid = px.scatter(resid_df, x="fitted", y="residual",
                                            title="Residuals vs Fitted",
                                            template="plotly_white")
                    fig_resid.add_hline(y=0, line_dash="dash", line_color="red")
                    fig_resid.update_layout(height=350, margin=dict(l=40, r=20, t=50, b=30))
                    st.plotly_chart(fig_resid, use_container_width=True)

                with col_r2:
                    fig_ts = px.line(resid_df, x="date", y="residual",
                                      title="Residuals over Time",
                                      template="plotly_white")
                    fig_ts.add_hline(y=0, line_dash="dash", line_color="red")
                    fig_ts.update_traces(line_color="#2563eb")
                    fig_ts.update_layout(height=350, margin=dict(l=40, r=20, t=50, b=30))
                    st.plotly_chart(fig_ts, use_container_width=True)

                # Durbin-Watson
                dw = sm.stats.stattools.durbin_watson(model.resid)
                st.caption(f"Durbin-Watson: {dw:.3f} · HAC lags: {hac_lags}")

                # Actual vs Fitted
                with st.expander("📈 Actual vs Fitted"):
                    avf = pd.DataFrame({
                        "date": clean["date"].values,
                        "Actual": y.values,
                        "Fitted": model.fittedvalues.values,
                    })
                    fig_avf = go.Figure()
                    fig_avf.add_trace(go.Scatter(x=avf["date"], y=avf["Actual"],
                                                  name="Actual", mode="lines",
                                                  line=dict(color="#2563eb", width=2)))
                    fig_avf.add_trace(go.Scatter(x=avf["date"], y=avf["Fitted"],
                                                  name="Fitted", mode="lines",
                                                  line=dict(color="#dc2626", width=1.5, dash="dot")))
                    fig_avf.update_layout(height=350, template="plotly_white",
                                           hovermode="x unified",
                                           margin=dict(l=40, r=20, t=30, b=30))
                    st.plotly_chart(fig_avf, use_container_width=True)

            except Exception as e:
                st.error(f"Regression failed: {e}")
