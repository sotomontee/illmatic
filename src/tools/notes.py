"""Note drafting tool — markdown research note template."""

from datetime import date


def register(mcp):
    @mcp.tool()
    async def draft_note(
        title: str,
        summary: str,
        body: str,
        data_sources: str = "",
        chart_paths: str = "",
        author: str = "Javier Pradere",
    ) -> str:
        """Draft a markdown research note.

        title: note title
        summary: 1-2 sentence executive summary
        body: main analysis text (markdown)
        data_sources: comma-separated list of data sources used
        chart_paths: comma-separated paths to chart PNGs to embed
        author: author name

        Returns formatted markdown note.
        """
        today = date.today().isoformat()

        sections = [
            f"# {title}",
            f"*{author} · {today}*",
            "",
            "## Summary",
            summary,
            "",
            "## Analysis",
            body,
        ]

        if chart_paths:
            sections.extend(["", "## Charts"])
            for p in chart_paths.split(","):
                p = p.strip()
                sections.append(f"![chart]({p})")

        if data_sources:
            sections.extend([
                "",
                "---",
                f"*Data sources: {data_sources}*",
            ])

        return "\n".join(sections)
