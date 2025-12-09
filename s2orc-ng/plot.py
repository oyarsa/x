"""Generate interactive bar charts from aggregated conference paper counts."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import plotly.express as px
import plotly.graph_objects as go
import typer
from plotly.subplots import make_subplots

from config import get_venue_to_conference_map

app = typer.Typer(help="Plot conference paper counts by year")


def get_color_map(conf_names: list[str]) -> dict[str, str]:
    """Create a consistent color mapping for conference names."""
    colors = px.colors.qualitative.Plotly + px.colors.qualitative.D3
    return {name: colors[i % len(colors)] for i, name in enumerate(sorted(conf_names))}


def build_year_conference_data(
    by_year_venue: dict[str, int],
    venue_to_conf: dict[str, str],
) -> dict[str, dict[str, int]]:
    """Build {year: {conference: count}} from {year|venue: count}."""
    by_year_conference: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for year_venue, count in by_year_venue.items():
        year, venue = year_venue.split("|", 1)
        conf_name = venue_to_conf.get(venue, venue)  # Fall back to venue if not mapped
        by_year_conference[year][conf_name] += count

    return by_year_conference


def add_chart_traces(
    fig: go.Figure,
    by_year_conference: dict[str, dict[str, int]],
    color_map: dict[str, str],
    row: int,
    show_legend: bool = True,
) -> None:
    """Add bar chart traces to a figure for a specific subplot row."""
    years = sorted(by_year_conference.keys())
    conf_names = sorted(color_map.keys())

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
                showlegend=show_legend,
                legendgroup=conf_name,
                marker_color=color_map[conf_name],
            ),
            row=row,
            col=1,
        )

    # Calculate totals for each year
    totals = [sum(by_year_conference[year].values()) for year in years]

    # Add total annotations above each bar
    fig.add_trace(
        go.Scatter(
            x=years,
            y=totals,
            mode="text",
            text=[str(t) for t in totals],
            textposition="top center",
            showlegend=False,
            hoverinfo="skip",
        ),
        row=row,
        col=1,
    )


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
    output_file: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output HTML file for the charts",
        ),
    ] = Path("output/chart.html"),
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

    by_year_conf = build_year_conference_data(by_year_venue, venue_to_conf)
    has_pdf_data = bool(by_year_venue_with_pdf)

    # Get all conference names and create consistent color mapping
    all_conf_names = {
        conf for year_data in by_year_conf.values() for conf in year_data
    }
    color_map = get_color_map(list(all_conf_names))

    if has_pdf_data:
        by_year_conf_pdf = build_year_conference_data(
            by_year_venue_with_pdf, venue_to_conf
        )

        total_all = sum(by_year_venue.values())
        total_pdf = sum(by_year_venue_with_pdf.values())

        # Create subplots with 2 rows
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=[
                f"All Papers ({total_all:,})",
                f"Papers with Open Access PDF ({total_pdf:,})",
            ],
            vertical_spacing=0.12,
        )

        add_chart_traces(fig, by_year_conf, color_map, row=1, show_legend=True)
        add_chart_traces(fig, by_year_conf_pdf, color_map, row=2, show_legend=False)

        fig.update_layout(
            barmode="stack",
            title="Papers by Year and Conference",
            height=900,
            legend_title="Conference",
            hovermode="closest",
        )

        fig.update_xaxes(title_text="Year", row=2, col=1)
        fig.update_yaxes(title_text="Number of Papers", row=1, col=1)
        fig.update_yaxes(title_text="Number of Papers", row=2, col=1)
    else:
        # Single chart if no PDF data
        fig = make_subplots(rows=1, cols=1)
        add_chart_traces(fig, by_year_conf, color_map, row=1, show_legend=True)

        fig.update_layout(
            barmode="stack",
            title="Papers by Year and Conference",
            xaxis_title="Year",
            yaxis_title="Number of Papers",
            legend_title="Conference",
            hovermode="closest",
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_file)
    print(f"Saved chart to {output_file}")


if __name__ == "__main__":
    app()
