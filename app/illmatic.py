"""
I L L M A T I C
Macro & Commodity Research Terminal
"""

import streamlit as st
import sys
import os

# ── Path setup ──────────────────────────────────────────────────
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app_dir = os.path.dirname(os.path.abspath(__file__))
for p in [project_root, app_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

st.set_page_config(
    page_title="Illmatic",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    /* Clean up Streamlit defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Prevent sidebar from collapsing */
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0f1117 !important;
        padding-top: 1rem;
        min-width: 260px !important;
        width: 260px !important;
        transform: none !important;
        visibility: visible !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        background-color: #0f1117 !important;
        width: 260px !important;
    }
    [data-testid="stSidebar"] * {
        color: #e0e0e0 !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        color: #ffffff !important;
        background-color: rgba(255,255,255,0.05);
        border-radius: 4px;
    }

    /* Title bar */
    .illmatic-title {
        font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 0.35em;
        color: #ffffff;
        padding: 0.8rem 0 0.5rem 0;
        margin-bottom: 0;
    }
    .illmatic-subtitle {
        font-size: 0.7rem;
        letter-spacing: 0.15em;
        color: #888;
        margin-top: -0.5rem;
        padding-bottom: 1rem;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #6c757d !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
        font-weight: 700;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
    }

    /* Section headers */
    .section-header {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #6c757d;
        border-bottom: 2px solid #e9ecef;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }

    /* Nav styling */
    .nav-item {
        font-size: 0.85rem;
        padding: 0.5rem 0.8rem;
        margin: 2px 0;
        border-radius: 6px;
        cursor: pointer;
    }
    .nav-item:hover {
        background-color: rgba(255,255,255,0.08);
    }

    /* Plotly chart containers */
    .stPlotlyChart {
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 4px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.5rem 1.2rem;
    }

    /* Download buttons */
    .stDownloadButton button {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        color: #495057;
        font-size: 0.8rem;
    }

    /* Hide Streamlit's multipage nav */
    [data-testid="stSidebarNav"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="illmatic-title">ILLMATIC</p>', unsafe_allow_html=True)
    st.markdown('<p class="illmatic-subtitle">MACRO & COMMODITY RESEARCH</p>', unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio(
        "NAV",
        [
            "⚡ Dashboard",
            "🤖 Research Assistant",
            "📊 Data Explorer",
            "🛢️ Commodities",
            "📐 Spreads & Ratios",
            "📈 Regression",
            "📝 Notes",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    st.markdown(
        '<p style="font-size:0.65rem; letter-spacing:0.08em; color:#555;">'
        'FRED · ECB · BIS · IMF · OECD<br>EIA · EUROSTAT · WORLD BANK'
        '<br><br>POWERED BY CLAUDE</p>',
        unsafe_allow_html=True,
    )

    # ── Quick Ask (floating mini-chat) ─────────────────────────
    if page != "🤖 Research Assistant":
        with st.expander("💬 Quick Ask", expanded=False):
            from data_layer import _get_secret
            quick_key = _get_secret("ANTHROPIC_API_KEY")
            if quick_key:
                quick_q = st.text_input("Ask anything...", key="quick_ask_input", label_visibility="collapsed",
                                         placeholder="e.g. What's Brent at?")
                if quick_q:
                    try:
                        from anthropic import Anthropic
                        from views.research_assistant import SYSTEM_PROMPT, TOOLS, _execute_tool
                        client = Anthropic(api_key=quick_key)
                        with st.spinner("..."):
                            resp = client.messages.create(
                                model="claude-sonnet-4-20250514",
                                max_tokens=1024,
                                system=SYSTEM_PROMPT + "\nBe very concise — this is a quick sidebar chat. 2-3 sentences max.",
                                tools=TOOLS,
                                messages=[{"role": "user", "content": quick_q}],
                            )
                            # Handle tool use
                            while resp.stop_reason == "tool_use":
                                tool_results = []
                                for block in resp.content:
                                    if block.type == "tool_use":
                                        result = _execute_tool(block.name, block.input)
                                        tool_results.append({
                                            "type": "tool_result",
                                            "tool_use_id": block.id,
                                            "content": result,
                                        })
                                msgs = [
                                    {"role": "user", "content": quick_q},
                                    {"role": "assistant", "content": resp.content},
                                    {"role": "user", "content": tool_results},
                                ]
                                resp = client.messages.create(
                                    model="claude-sonnet-4-20250514",
                                    max_tokens=1024,
                                    system=SYSTEM_PROMPT + "\nBe very concise — this is a quick sidebar chat. 2-3 sentences max.",
                                    tools=TOOLS,
                                    messages=msgs,
                                )
                            # Show answer
                            answer = "".join(b.text for b in resp.content if hasattr(b, "text"))
                            st.markdown(answer)
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.caption("Add ANTHROPIC_API_KEY to enable.")

# ── Page routing ────────────────────────────────────────────────
if page == "⚡ Dashboard":
    from views import dashboard
    dashboard.render()
elif page == "🤖 Research Assistant":
    from views import research_assistant
    research_assistant.render()
elif page == "📊 Data Explorer":
    from views import data_explorer
    data_explorer.render()
elif page == "🛢️ Commodities":
    from views import commodity_monitor
    commodity_monitor.render()
elif page == "📐 Spreads & Ratios":
    from views import spreads
    spreads.render()
elif page == "📈 Regression":
    from views import regression_tool
    regression_tool.render()
elif page == "📝 Notes":
    from views import notes_drafter
    notes_drafter.render()
