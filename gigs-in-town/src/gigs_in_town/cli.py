"""Process ICS files to deliver statistics on concert events."""

from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, no_type_check

import icalendar
import typer
import yaml
from pydantic import BaseModel, ConfigDict
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    date: str
    location: str


@app.command(no_args_is_help=True)
def convert(
    input_file: Annotated[Path, typer.Argument(help="Input ICS file.")],
    output_file: Annotated[Path, typer.Argument(help="Output events YAML file.")],
) -> None:
    """Convert events from ICS file into YAML.

    Tested with Google Calendar export.
    """
    events = sorted(_parse_ics(input_file), key=lambda e: e.date)
    _save(output_file, events)


@no_type_check
def _parse_ics(path: Path) -> list[Event]:
    """Parse events from ICS file.

    Walks the "vevent" component. Assumes "summary", "location" and "dtstart" properties.
    "dtstart" must be a datetime.
    """
    cal = icalendar.Calendar.from_ical(path.read_text())
    return [
        Event(
            name=str(component.get("summary", "")),
            date=component.get("dtstart").dt.strftime("%Y-%m-%d"),
            location=str(component.get("location", "")),
        )
        for component in cal.walk("vevent")
    ]


class Concert(BaseModel):
    model_config = ConfigDict(frozen=True)

    bands: Sequence[str]
    date: str
    location: str


@app.command(no_args_is_help=True)
def stats(
    input_file: Annotated[Path, typer.Argument(help="Input concerts YAML file.")],
    start_date: Annotated[
        str | None, typer.Option("--start", help="Start date for filtering.")
    ] = None,
    end_date: Annotated[
        str | None, typer.Option("--end", help="Start date for filtering.")
    ] = None,
) -> None:
    """Show statistics about bands and venues."""
    concerts = _load(Event, input_file)

    start_date = start_date or "2022-01-01"
    end_date = end_date or dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")

    concerts = [
        Concert(
            bands=[band for name in event.name.split("&") if (band := name.strip())],
            date=event.date,
            location=event.location,
        )
        for event in concerts
        if start_date <= event.date <= end_date
    ]

    bands_all = [band for concert in concerts for band in concert.bands]
    bands = set(bands_all)
    venues = {concert.location for concert in concerts}
    earliest_date = min(event.date for event in concerts)
    avg_interesting = len(bands_all) / len(concerts)

    console = Console()
    console.print(_details_table(bands, "band", concerts))
    console.print(_details_table(venues, "venue", concerts))
    console.print()
    console.print(f"Start: {start_date}")
    console.print(f"End: {end_date}")
    console.print(f"Earliest date: {earliest_date}")
    console.print(f"Unique bands: {len(bands)}")
    console.print(f"Unique venues: {len(venues)}")
    console.print(f"Events: {len(concerts)}")
    console.print(f"Total interesting bands: {len(bands_all)}")
    console.print(f"Average interesting bands per concert: {avg_interesting:.2f}")

    monthly: defaultdict[str, list[Concert]] = defaultdict(list)
    for concert in concerts:
        month = "-".join(concert.date.split("-")[:2])
        monthly[month].append(concert)

    monthly_table = Table("Month", "Events", "Headliners", "Bands")
    for month, concerts in sorted(monthly.items(), key=lambda x: x[0]):
        bands = [band for concert in concerts for band in concert.bands]
        headliners = [concert.bands[0] for concert in concerts]
        monthly_table.add_row(
            month, str(len(concerts)), ", ".join(headliners), ", ".join(bands)
        )
    console.print(monthly_table)


@dataclass(frozen=True, kw_only=True)
class Details:
    count: int
    dates: str
    items: str


def _get_band_details(concerts: Sequence[Concert], band: str) -> Details:
    """Get count, sorted dates and venues for a band."""
    band_concerts = [c for c in concerts if band in c.bands]

    dates = ", ".join(sorted(c.date for c in band_concerts))
    venues = _format_duplicates(c.location for c in band_concerts)

    return Details(count=len(band_concerts), dates=dates, items=venues)


def _get_venue_details(concerts: Sequence[Concert], venue: str) -> Details:
    """Get count, sorted dates and bands for a venue.

    One event with three bands counts the venues three times.
    """
    venue_concerts = [c for c in concerts if c.location == venue]
    count = sum(len(c.bands) for c in venue_concerts)

    dates = ", ".join(sorted(c.date for c in venue_concerts))
    bands = _format_duplicates(band for c in venue_concerts for band in c.bands)

    return Details(count=count, dates=dates, items=bands)


def _format_duplicates(items: Iterable[str]) -> str:
    """Format an iterable of strings with duplicate counting."""
    return ", ".join(
        item if count == 1 else f"{item} (x{count})"
        for item, count in Counter(items).items()
    )


def _details_table(counter: set[str], name: str, concerts: Sequence[Concert]) -> Table:
    """Generate table with the item type (bands/venues) with counts, dates and items."""
    func = _get_band_details if name == "band" else _get_venue_details
    item_details = [(item, func(concerts, item)) for item in counter]

    table = Table(name.capitalize(), "Count", "Dates", "Items")
    for item, details in sorted(item_details, key=lambda x: x[1].count, reverse=True):
        table.add_row(item, str(details.count), details.dates, details.items)
    return table


def _load[T: BaseModel](class_: type[T], file: Path) -> list[T]:
    """Load list of `pydantic.BaseModel`s of type `T` from YAML file."""
    with file.open() as f:
        return [class_.model_validate(x) for x in yaml.safe_load(f)]


def _save(file: Path, data: Iterable[BaseModel]) -> None:
    """Save iterable of `pydantic.BaseModel`s to YAML file."""
    file.write_text(yaml.dump([x.model_dump() for x in data], sort_keys=False))


if __name__ == "__main__":
    app()
