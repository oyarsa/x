"""Generate interactive bar charts from aggregated conference paper counts."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import plotly.graph_objects as go
import typer

from config import get_venue_to_conference_map

app = typer.Typer(help="Plot conference paper counts by year")


def build_year_conference_data(
    by_year_venue: dict[str, int],
    venue_to_conf: dict[str, str],
) -> dict[str, dict[str, int]]:
    """Build {year: {conference: count}} from {year|venue: count}."""
    by_year_conference: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for year_venue, count in by_year_venue.items():
        year, venue = year_venue.split("|", 1)
        conf_name = venue_to_conf.get(venue, venue)  # Fall back to venue if not mapped
        by_year_conference[year][conf_name] += count

    return by_year_conference


def create_chart(
    by_year_conference: dict[str, dict[str, int]],
    title: str,
) -> go.Figure:
    """Create a stacked bar chart figure."""
    years = sorted(by_year_conference.keys())
    conf_names = sorted(
        {conf for year_data in by_year_conference.values() for conf in year_data}
    )

    fig = go.Figure()

    for conf_name in conf_names:
        counts = [by_year_conference[year].get(conf_name, 0) for year in years]
        fig.add_trace(
            go.Bar(
                name=conf_name,
                x=years,
                y=counts,
                hovertemplate=(
                    f"<b>{conf_name}</b><br>"
                    "Year: %{x}<br>"
                    "Papers: %{y}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title="Year",
        yaxis_title="Number of Papers",
        legend_title="Conference",
        hovermode="closest",
    )

    return fig


@app.command()
def main(
    input_file: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Input JSON file with aggregated counts (from main.py)",
        ),
    ] = Path("output/aggregated_counts.json"),
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Output directory for the charts",
        ),
    ] = Path("output"),
) -> None:
    """Generate interactive stacked bar charts of papers by year and conference."""
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        raise typer.Exit(1)

    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    by_year_venue = data.get("by_year_venue", {})
    by_year_venue_with_pdf = data.get("by_year_venue_with_pdf", {})

    if not by_year_venue:
        print("Error: No by_year_venue data found in input file")
        raise typer.Exit(1)

    venue_to_conf = get_venue_to_conference_map()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Chart 1: All papers
    by_year_conf = build_year_conference_data(by_year_venue, venue_to_conf)
    fig_all = create_chart(by_year_conf, "Papers by Year and Conference")
    chart_all_path = output_dir / "chart.html"
    fig_all.write_html(chart_all_path)
    print(f"Saved chart to {chart_all_path}")

    # Chart 2: Papers with PDF only
    if by_year_venue_with_pdf:
        by_year_conf_pdf = build_year_conference_data(by_year_venue_with_pdf, venue_to_conf)
        fig_pdf = create_chart(by_year_conf_pdf, "Papers with Open Access PDF by Year and Conference")
        chart_pdf_path = output_dir / "chart_with_pdf.html"
        fig_pdf.write_html(chart_pdf_path)
        print(f"Saved chart to {chart_pdf_path}")
    else:
        print("No by_year_venue_with_pdf data found, skipping PDF chart")


if __name__ == "__main__":
    app()
