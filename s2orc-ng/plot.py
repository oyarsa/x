"""Generate interactive bar charts from aggregated conference paper counts."""

# ruff: noqa: SLF001

import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

import plotly.express as px
import plotly.graph_objects as go
import typer
from plotly.subplots import make_subplots

from config import CONFERENCE_PATTERNS, get_venue_to_conference_map

app = typer.Typer(
    help="Plot conference paper counts by year",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


def get_color_map(conf_names: list[str]) -> dict[str, str]:
    """Create a consistent color mapping for conference names."""
    colors = px.colors.qualitative.Plotly + px.colors.qualitative.D3
    return {name: colors[i % len(colors)] for i, name in enumerate(sorted(conf_names))}


def get_conference_to_category_map() -> dict[str, str]:
    """Build a mapping from conference names to their categories."""
    return {conf.name: conf.category for conf in CONFERENCE_PATTERNS}


def get_all_categories() -> list[str]:
    """Get all unique categories in order."""
    seen: set[str] = set()
    categories: list[str] = []
    for conf in CONFERENCE_PATTERNS:
        if conf.category not in seen:
            seen.add(conf.category)
            categories.append(conf.category)
    return categories


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


def build_year_category_data(
    by_year_venue: dict[str, int],
    venue_to_conf: dict[str, str],
    conf_to_category: dict[str, str],
) -> dict[str, dict[str, int]]:
    """Build {year: {category: count}} from {year|venue: count}."""
    by_year_category: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for year_venue, count in by_year_venue.items():
        year, venue = year_venue.split("|", 1)
        conf_name = venue_to_conf.get(venue, venue)
        category = conf_to_category.get(conf_name, "Other")
        by_year_category[year][category] += count

    return by_year_category


def add_chart_traces(
    fig: go.Figure,
    by_year_conference: dict[str, dict[str, int]],
    color_map: dict[str, str],
    conf_to_category: dict[str, str],
    row: int,
    show_legend: bool = True,
) -> list[str]:
    """Add bar chart traces to a figure for a specific subplot row.

    Returns:
        List of category names for each trace added (excluding the totals trace).
    """
    years = sorted(by_year_conference.keys())
    conf_names = sorted(color_map.keys())
    trace_categories: list[str] = []

    for conf_name in conf_names:
        counts = [by_year_conference[year].get(conf_name, 0) for year in years]
        category = conf_to_category.get(conf_name, "Other")
        fig.add_trace(
            go.Bar(
                name=conf_name,
                x=years,
                y=counts,
                hovertemplate=(
                    f"<b>{conf_name}</b> ({category})<br>"
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
        trace_categories.append(category)

    # Calculate totals for each year
    totals = [sum(by_year_conference[year].values()) for year in years]

    # Add total annotations above each bar
    fig.add_trace(
        go.Scatter(
            x=years,
            y=totals,
            mode="text",
            text=[f"{t:,}" for t in totals],
            textposition="top center",
            showlegend=False,
            hoverinfo="skip",
        ),
        row=row,
        col=1,
    )
    trace_categories.append("_totals")  # Special marker for totals trace

    return trace_categories


def get_category_to_conferences_map() -> dict[str, list[str]]:
    """Build a mapping from categories to their conference names."""
    result: dict[str, list[str]] = defaultdict(list)
    for conf in CONFERENCE_PATTERNS:
        result[conf.category].append(conf.name)
    return dict(result)


def add_category_chart_traces(
    fig: go.Figure,
    by_year_category: dict[str, dict[str, int]],
    color_map: dict[str, str],
    category_to_confs: dict[str, list[str]],
    row: int,
    show_legend: bool = True,
) -> None:
    """Add bar chart traces grouped by category to a figure."""
    years = sorted(by_year_category.keys())
    categories = sorted(color_map.keys())

    for category in categories:
        counts = [by_year_category[year].get(category, 0) for year in years]
        confs = category_to_confs.get(category, [])
        confs_str = ", ".join(sorted(confs)) if confs else "None"
        fig.add_trace(
            go.Bar(
                name=category,
                x=years,
                y=counts,
                hovertemplate=(
                    f"<b>{category}</b><br>"
                    "Year: %{x}<br>"
                    "Papers: %{y}<br>"
                    f"<i>Conferences: {confs_str}</i><extra></extra>"
                ),
                showlegend=show_legend,
                legendgroup=category,
                marker_color=color_map[category],
            ),
            row=row,
            col=1,
        )

    # Calculate totals for each year
    totals = [sum(by_year_category[year].values()) for year in years]

    # Add total annotations above each bar
    fig.add_trace(
        go.Scatter(
            x=years,
            y=totals,
            mode="text",
            text=[f"{t:,}" for t in totals],
            textposition="top center",
            showlegend=False,
            hoverinfo="skip",
        ),
        row=row,
        col=1,
    )


def get_pdf_source_label(pdf_source: str | None) -> str:
    """Convert pdf_source field to display label."""
    if pdf_source is None:
        return "No PDF"
    return {
        "S2": "Semantic Scholar",
        "ArXiv": "ArXiv",
        "ACL": "ACL Anthology",
    }.get(pdf_source, pdf_source)


def classify_pdf_host(url: str | None) -> str:
    """Classify a PDF URL by its host."""
    if not url:
        return "No PDF"
    if "arxiv.org" in url:
        return "ArXiv"
    if "aclanthology.org" in url:
        return "ACL Anthology"
    if "openaccess.thecvf.com" in url:
        return "CVF"
    if "openreview.net" in url:
        return "OpenReview"
    if "proceedings.neurips.cc" in url:
        return "NeurIPS"
    if "proceedings.mlr.press" in url:
        return "PMLR"
    return "Other"


def build_year_host_data(papers: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Build {year: {host: count}} from papers list."""
    by_year_host: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for paper in papers:
        year = paper.get("year")
        if not year:
            continue
        host = classify_pdf_host(paper.get("open_access_pdf"))
        by_year_host[str(year)][host] += 1

    return by_year_host


def build_year_source_data(papers: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Build {year: {source: count}} from papers list."""
    by_year_source: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for paper in papers:
        year = paper.get("year")
        if not year:
            continue
        source = get_pdf_source_label(paper.get("pdf_source"))
        by_year_source[str(year)][source] += 1

    return by_year_source


def add_source_chart_traces(
    fig: go.Figure,
    by_year_source: dict[str, dict[str, int]],
    row: int,
    show_legend: bool = True,
) -> None:
    """Add bar chart traces for PDF sources to a figure."""
    years = sorted(by_year_source.keys())
    # Fixed order and colors for sources
    sources = ["Semantic Scholar", "ArXiv", "ACL Anthology", "No PDF"]
    source_colors = {
        "Semantic Scholar": "#636EFA",
        "ArXiv": "#EF553B",
        "ACL Anthology": "#00CC96",
        "No PDF": "#AB63FA",
    }

    for source in sources:
        counts = [by_year_source[year].get(source, 0) for year in years]
        fig.add_trace(
            go.Bar(
                name=source,
                x=years,
                y=counts,
                hovertemplate=(
                    f"<b>{source}</b><br>Year: %{{x}}<br>Papers: %{{y}}<extra></extra>"
                ),
                showlegend=show_legend,
                legendgroup=source,
                marker_color=source_colors[source],
            ),
            row=row,
            col=1,
        )

    # Calculate totals for each year
    totals = [sum(by_year_source[year].values()) for year in years]

    # Add total annotations above each bar
    fig.add_trace(
        go.Scatter(
            x=years,
            y=totals,
            mode="text",
            text=[f"{t:,}" for t in totals],
            textposition="top center",
            showlegend=False,
            hoverinfo="skip",
        ),
        row=row,
        col=1,
    )


def add_host_chart_traces(
    fig: go.Figure,
    by_year_host: dict[str, dict[str, int]],
    row: int,
    show_legend: bool = True,
) -> None:
    """Add bar chart traces for PDF hosts to a figure."""
    years = sorted(by_year_host.keys())
    # Fixed order and colors for hosts
    hosts = [
        "ArXiv",
        "ACL Anthology",
        "CVF",
        "OpenReview",
        "NeurIPS",
        "PMLR",
        "Other",
        "No PDF",
    ]
    host_colors = {
        "ArXiv": "#EF553B",
        "ACL Anthology": "#00CC96",
        "CVF": "#636EFA",
        "OpenReview": "#FFA15A",
        "NeurIPS": "#19D3F3",
        "PMLR": "#FF6692",
        "Other": "#B6E880",
        "No PDF": "#AB63FA",
    }

    for host in hosts:
        counts = [by_year_host[year].get(host, 0) for year in years]
        if sum(counts) == 0:  # Skip hosts with no data
            continue
        fig.add_trace(
            go.Bar(
                name=host,
                x=years,
                y=counts,
                hovertemplate=(
                    f"<b>{host}</b><br>Year: %{{x}}<br>Papers: %{{y}}<extra></extra>"
                ),
                showlegend=show_legend,
                legendgroup=host,
                marker_color=host_colors[host],
            ),
            row=row,
            col=1,
        )

    # Calculate totals for each year
    totals = [sum(by_year_host[year].values()) for year in years]

    # Add total annotations above each bar
    fig.add_trace(
        go.Scatter(
            x=years,
            y=totals,
            mode="text",
            text=[f"{t:,}" for t in totals],
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
    papers_file: Annotated[
        Path,
        typer.Option(
            "--papers",
            "-p",
            help="Input JSON file with paper records (for PDF source analysis)",
        ),
    ] = Path("output/papers.json"),
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
    conf_to_category = get_conference_to_category_map()
    all_categories = get_all_categories()

    by_year_conf = build_year_conference_data(by_year_venue, venue_to_conf)
    has_pdf_data = bool(by_year_venue_with_pdf)

    # Get all conference names and create consistent color mapping
    all_conf_names = {conf for year_data in by_year_conf.values() for conf in year_data}
    color_map = get_color_map(list(all_conf_names))

    # Pre-compute totals by category for title updates
    def compute_category_totals(
        by_year_conf_data: dict[str, dict[str, int]],
    ) -> dict[str, int]:
        """Compute total papers per category."""
        totals: dict[str, int] = defaultdict(int)
        for year_data in by_year_conf_data.values():
            for conf, count in year_data.items():
                cat = conf_to_category.get(conf, "Other")
                totals[cat] += count
        totals["All Categories"] = sum(
            sum(year_data.values()) for year_data in by_year_conf_data.values()
        )
        return totals

    if has_pdf_data:
        by_year_conf_pdf = build_year_conference_data(
            by_year_venue_with_pdf, venue_to_conf
        )

        total_all = sum(by_year_venue.values())
        total_pdf = sum(by_year_venue_with_pdf.values())

        # Compute category totals for both charts
        cat_totals_all = compute_category_totals(by_year_conf)
        cat_totals_pdf = compute_category_totals(by_year_conf_pdf)

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

        trace_cats_1 = add_chart_traces(
            fig, by_year_conf, color_map, conf_to_category, row=1, show_legend=True
        )
        trace_cats_2 = add_chart_traces(
            fig, by_year_conf_pdf, color_map, conf_to_category, row=2, show_legend=False
        )
        all_trace_categories = trace_cats_1 + trace_cats_2

        # Store category info for JavaScript
        category_trace_map = {
            cat: [i for i, c in enumerate(all_trace_categories) if c == cat]
            for cat in all_categories
        }

        fig.update_layout(
            barmode="stack",
            title="Papers by Year and Conference",
            height=900,
            legend_title="Conference",
            hovermode="closest",
        )

        # Store data for JavaScript
        fig._category_trace_map = category_trace_map
        fig._all_categories = all_categories
        fig._total_traces = len(all_trace_categories)
        fig._cat_totals_all = cat_totals_all
        fig._cat_totals_pdf = cat_totals_pdf
        fig._has_pdf_data = True

        fig.update_xaxes(title_text="Year", row=2, col=1)
        fig.update_yaxes(title_text="Number of Papers", row=1, col=1)
        fig.update_yaxes(title_text="Number of Papers", row=2, col=1)
    else:
        # Single chart if no PDF data
        fig = make_subplots(rows=1, cols=1)
        trace_cats = add_chart_traces(
            fig, by_year_conf, color_map, conf_to_category, row=1, show_legend=True
        )

        category_trace_map = {
            cat: [i for i, c in enumerate(trace_cats) if c == cat]
            for cat in all_categories
        }

        fig.update_layout(
            barmode="stack",
            title="Papers by Year and Conference",
            xaxis_title="Year",
            yaxis_title="Number of Papers",
            legend_title="Conference",
            hovermode="closest",
        )

        cat_totals = compute_category_totals(by_year_conf)
        fig._category_trace_map = category_trace_map
        fig._all_categories = all_categories
        fig._total_traces = len(trace_cats)
        fig._cat_totals_all = cat_totals
        fig._cat_totals_pdf = {}
        fig._has_pdf_data = False
        total_all = sum(by_year_venue.values())
        total_pdf = 0

    # Create the category-level charts
    by_year_cat = build_year_category_data(
        by_year_venue, venue_to_conf, conf_to_category
    )
    category_color_map = get_color_map(all_categories)
    category_to_confs = get_category_to_conferences_map()

    if has_pdf_data:
        by_year_cat_pdf = build_year_category_data(
            by_year_venue_with_pdf, venue_to_conf, conf_to_category
        )

        fig_cat = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=[
                f"All Papers by Category ({total_all:,})",
                f"Papers with Open Access PDF by Category ({total_pdf:,})",
            ],
            vertical_spacing=0.12,
        )

        add_category_chart_traces(
            fig_cat,
            by_year_cat,
            category_color_map,
            category_to_confs,
            row=1,
            show_legend=True,
        )
        add_category_chart_traces(
            fig_cat,
            by_year_cat_pdf,
            category_color_map,
            category_to_confs,
            row=2,
            show_legend=False,
        )

        fig_cat.update_layout(
            barmode="stack",
            title="Papers by Year and Category",
            height=900,
            legend_title="Category",
            hovermode="closest",
        )

        fig_cat.update_xaxes(title_text="Year", row=2, col=1)
        fig_cat.update_yaxes(title_text="Number of Papers", row=1, col=1)
        fig_cat.update_yaxes(title_text="Number of Papers", row=2, col=1)
    else:
        fig_cat = make_subplots(rows=1, cols=1)
        add_category_chart_traces(
            fig_cat,
            by_year_cat,
            category_color_map,
            category_to_confs,
            row=1,
            show_legend=True,
        )

        fig_cat.update_layout(
            barmode="stack",
            title="Papers by Year and Category",
            xaxis_title="Year",
            yaxis_title="Number of Papers",
            legend_title="Category",
            hovermode="closest",
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Generate HTML with custom checkbox controls
    category_trace_map = fig._category_trace_map
    all_cats = fig._all_categories
    total_traces = fig._total_traces
    cat_totals_all = fig._cat_totals_all
    cat_totals_pdf = fig._cat_totals_pdf
    has_pdf_data_flag = fig._has_pdf_data

    # Build checkbox HTML and JavaScript
    checkbox_html = """
<div id="category-controls" style="margin-bottom: 10px; padding: 10px; background: #f5f5f5; border-radius: 5px;">
  <strong>Filter by Category:</strong>
  <label style="margin-left: 15px;"><input type="checkbox" id="cb-all" checked onchange="toggleAll(this)"> All</label>
"""
    for cat in all_cats:
        safe_id = cat.replace("/", "-").replace(" ", "-")
        checkbox_html += f'  <label style="margin-left: 15px;"><input type="checkbox" class="cat-cb" data-category="{cat}" id="cb-{safe_id}" checked onchange="toggleCategory()"> {cat}</label>\n'
    checkbox_html += "</div>\n"

    # JavaScript for checkbox logic
    checkbox_js = f"""
<script>
const categoryTraceMap = {json.dumps(category_trace_map)};
const totalTraces = {total_traces};
const catTotalsAll = {json.dumps(cat_totals_all)};
const catTotalsPdf = {json.dumps(cat_totals_pdf)};
const hasPdfData = {json.dumps(has_pdf_data_flag)};

function formatNumber(num) {{
    return num.toLocaleString();
}}

function toggleAll(checkbox) {{
    const catCheckboxes = document.querySelectorAll('.cat-cb');
    catCheckboxes.forEach(cb => cb.checked = checkbox.checked);
    updateVisibility();
}}

function toggleCategory() {{
    updateVisibility();
    // Update "All" checkbox state
    const catCheckboxes = document.querySelectorAll('.cat-cb');
    const allChecked = Array.from(catCheckboxes).every(cb => cb.checked);
    const noneChecked = Array.from(catCheckboxes).every(cb => !cb.checked);
    document.getElementById('cb-all').checked = allChecked;
    document.getElementById('cb-all').indeterminate = !allChecked && !noneChecked;
}}

function updateVisibility() {{
    const catCheckboxes = document.querySelectorAll('.cat-cb');
    const visibility = new Array(totalTraces).fill(false);
    let totalAll = 0;
    let totalPdf = 0;
    const selectedCategories = [];

    catCheckboxes.forEach(cb => {{
        if (cb.checked) {{
            const category = cb.dataset.category;
            selectedCategories.push(category);
            const indices = categoryTraceMap[category] || [];
            indices.forEach(i => visibility[i] = true);
            totalAll += catTotalsAll[category] || 0;
            totalPdf += catTotalsPdf[category] || 0;
        }}
    }});

    // Update the conference chart
    const confDiv = document.getElementById('conf-chart');
    if (confDiv) {{
        Plotly.restyle(confDiv, {{'visible': visibility.map(v => v ? true : false)}});

        // Update subplot titles
        const allChecked = selectedCategories.length === Object.keys(categoryTraceMap).length;
        let title1, title2;

        if (allChecked) {{
            title1 = `All Papers (${{formatNumber(totalAll)}})`;
            title2 = `Papers with Open Access PDF (${{formatNumber(totalPdf)}})`;
        }} else if (selectedCategories.length === 0) {{
            title1 = 'All Papers (0)';
            title2 = 'Papers with Open Access PDF (0)';
        }} else {{
            const catLabel = selectedCategories.length === 1 ? selectedCategories[0] : `${{selectedCategories.length}} categories`;
            title1 = `All Papers - ${{catLabel}} (${{formatNumber(totalAll)}})`;
            title2 = `Papers with Open Access PDF - ${{catLabel}} (${{formatNumber(totalPdf)}})`;
        }}

        if (hasPdfData) {{
            Plotly.relayout(confDiv, {{
                'annotations[0].text': title1,
                'annotations[1].text': title2
            }});
        }} else {{
            Plotly.relayout(confDiv, {{
                'annotations[0].text': title1
            }});
        }}
    }}
}}
</script>
"""

    # Create PDF source chart if papers file exists
    source_chart_html = ""
    if papers_file.exists():
        with open(papers_file, encoding="utf-8") as f:
            papers = json.load(f)

        by_year_source = build_year_source_data(papers)
        total_papers = sum(sum(sources.values()) for sources in by_year_source.values())
        total_with_pdf = sum(
            sum(count for src, count in sources.items() if src != "No PDF")
            for sources in by_year_source.values()
        )

        fig_source = make_subplots(
            rows=1,
            cols=1,
            subplot_titles=[
                f"PDF Sources ({total_with_pdf:,} / {total_papers:,} papers)"
            ],
        )

        add_source_chart_traces(fig_source, by_year_source, row=1, show_legend=True)

        fig_source.update_layout(
            barmode="stack",
            title="Papers by PDF Source",
            xaxis_title="Year",
            yaxis_title="Number of Papers",
            legend_title="Source",
            hovermode="closest",
            height=500,
        )

        source_chart_html = fig_source.to_html(
            full_html=False, include_plotlyjs=False, div_id="source-chart"
        )

        # Create PDF host chart
        by_year_host = build_year_host_data(papers)
        total_with_pdf_host = sum(
            sum(count for host, count in hosts.items() if host != "No PDF")
            for hosts in by_year_host.values()
        )

        fig_host = make_subplots(
            rows=1,
            cols=1,
            subplot_titles=[
                f"PDF Hosts ({total_with_pdf_host:,} / {total_papers:,} papers)"
            ],
        )

        add_host_chart_traces(fig_host, by_year_host, row=1, show_legend=True)

        fig_host.update_layout(
            barmode="stack",
            title="Papers by PDF Host",
            xaxis_title="Year",
            yaxis_title="Number of Papers",
            legend_title="Host",
            hovermode="closest",
            height=500,
        )

        host_chart_html = fig_host.to_html(
            full_html=False, include_plotlyjs=False, div_id="host-chart"
        )
    else:
        host_chart_html = ""

    # Generate HTML for figures
    conf_chart_html = fig.to_html(
        full_html=False, include_plotlyjs=False, div_id="conf-chart"
    )
    cat_chart_html = fig_cat.to_html(
        full_html=False, include_plotlyjs=False, div_id="cat-chart"
    )

    # Combine into single HTML
    combined_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Conference Paper Analysis</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .chart-container {{ margin-bottom: 40px; }}
        h2 {{ color: #333; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
    </style>
</head>
<body>
{checkbox_html}

<div class="chart-container">
    <h2>By Conference</h2>
    {conf_chart_html}
</div>

<div class="chart-container">
    <h2>By Category</h2>
    {cat_chart_html}
</div>

{
        f'''<div class="chart-container">
    <h2>By PDF Source</h2>
    {source_chart_html}
</div>'''
        if source_chart_html
        else ""
    }

{
        f'''<div class="chart-container">
    <h2>By PDF Host</h2>
    {host_chart_html}
</div>'''
        if host_chart_html
        else ""
    }

{checkbox_js}
</body>
</html>
"""

    output_file.write_text(combined_html, encoding="utf-8")
    print(f"Saved chart to {output_file}")


if __name__ == "__main__":
    app()
