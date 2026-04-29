"""Notes Drafter — research notes with embedded data."""

import streamlit as st
import pandas as pd
from datetime import date


NOTE_TEMPLATES = {
    "Blank": "",
    "Market Update": "## Market Overview\n\n\n## Key Moves\n\n\n## Positioning & Flows\n\n\n## Outlook\n\n",
    "Trade Idea": "## Thesis\n\n\n## Setup\n\n- Entry:\n- Target:\n- Stop:\n- Timeframe:\n\n## Rationale\n\n\n## Risks\n\n",
    "Macro Note": "## Summary\n\n\n## Data Review\n\n\n## Policy Implications\n\n\n## Market Impact\n\n\n## What to Watch\n\n",
}


def render():
    st.markdown("## Notes")
    st.caption("Draft research notes in markdown — export or copy to your workflow.")

    # ── Note metadata ───────────────────────────────────────────
    st.markdown('<p class="section-header">Note Details</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        title = st.text_input("Title", placeholder="e.g. Q1 2024 Energy Market Review")
    with col2:
        author = st.text_input("Author", "Javier Pradere")
    with col3:
        template = st.selectbox("Template", list(NOTE_TEMPLATES.keys()))

    today = date.today().isoformat()

    # ── Executive summary ───────────────────────────────────────
    st.markdown('<p class="section-header">Content</p>', unsafe_allow_html=True)

    summary = st.text_area(
        "Executive Summary",
        placeholder="1-2 sentence summary of your key finding or view...",
        height=80,
    )

    # ── Main body ───────────────────────────────────────────────
    default_body = NOTE_TEMPLATES[template]
    body = st.text_area(
        "Analysis",
        value=default_body,
        placeholder="Write your analysis here. Markdown supported.\n\nReference data from the Data Explorer or Commodity Monitor.",
        height=350,
    )

    # ── Data sources ────────────────────────────────────────────
    sources = st.text_input(
        "Data Sources",
        placeholder="e.g. FRED, ECB SDW, IMF PCPS",
    )

    # ── Include last chart data? ────────────────────────────────
    include_data = False
    if "last_data" in st.session_state and st.session_state["last_data"] is not None:
        label = st.session_state.get("last_label", "data")
        include_data = st.checkbox(f"Append data table from: {label}")

    # ── Generate ────────────────────────────────────────────────
    st.markdown("---")

    if st.button("📄 Generate Note", type="primary", use_container_width=True):
        if not title:
            st.warning("Please enter a title.")
            return

        sections = [
            f"# {title}",
            f"*{author} · {today}*",
            "",
        ]

        if summary:
            sections.extend(["## Summary", summary, ""])

        if body:
            sections.extend(["## Analysis", body, ""])

        if include_data and "last_data" in st.session_state:
            df = st.session_state["last_data"]
            sections.extend([
                "## Data",
                "",
                df.to_markdown(index=False),
                "",
            ])

        if sources:
            sections.extend(["---", f"*Data sources: {sources}*"])

        note_text = "\n".join(sections)

        # ── Preview ─────────────────────────────────────────────
        st.markdown('<p class="section-header">Preview</p>', unsafe_allow_html=True)
        st.markdown(note_text)

        # ── Export ──────────────────────────────────────────────
        st.markdown('<p class="section-header">Export</p>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            filename = f"{today}_{title.lower().replace(' ', '-')[:40]}.md"
            st.download_button(
                "⬇️ Download Markdown",
                note_text,
                filename,
                "text/markdown",
                use_container_width=True,
            )

        with col_b:
            st.code(note_text, language="markdown")
