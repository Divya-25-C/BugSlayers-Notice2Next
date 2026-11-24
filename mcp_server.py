from __future__ import annotations

from mcp.server import MCPServer

from analysis import analyze_text, validate_reminder

mcp = MCPServer("Notice2Next")


@mcp.tool()
def find_notice_dates(text: str) -> dict:
    """Find possible dates in a campus notice and return page-text evidence. Review every result against the source."""
    if len(text) > 100_000:
        raise ValueError("Notice text must be 100,000 characters or less.")
    return analyze_text(text)


@mcp.tool()
def draft_reminder(title: str, date_value: str, source_page: int, evidence: str) -> dict:
    """Create a reminder draft with source evidence. This tool never writes to a calendar."""
    return validate_reminder(title, date_value, source_page, evidence)


if __name__ == "__main__":
    mcp.run(transport="stdio")
