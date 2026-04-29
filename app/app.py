"""
Macro Research Terminal — Streamlit app
Launch: streamlit run app/app.py
"""

import streamlit as st
import sys
import os

# Add project root and app dir to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app_dir = os.path.dirname(os.path.abspath(__file__))
for p in [project_root, app_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Macro Research Terminal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ──────────────────────────────────────────────────────
st.sidebar.title("Macro Research Terminal")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["🔍 Data Explorer", "🛢️ Commodity Monitor", "📈 Regression Tool", "📝 Notes Drafter"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption("Data: FRED · ECB · Eurostat · BIS · IMF · OECD · EIA · World Bank")

# ── Page routing ─────────────────────────────────────────────────
if page == "🔍 Data Explorer":
    from pages import data_explorer
    data_explorer.render()
elif page == "🛢️ Commodity Monitor":
    from pages import commodity_monitor
    commodity_monitor.render()
elif page == "📈 Regression Tool":
    from pages import regression_tool
    regression_tool.render()
elif page == "📝 Notes Drafter":
    from pages import notes_drafter
    notes_drafter.render()
