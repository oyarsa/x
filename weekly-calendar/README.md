# weekly-calendar: Show weekly progress calendar between two dates

## Getting started

Requires Go. Install with:

```console
$ cargo install github.com/oyarsa/x/weekly-calendar
```

Or clone the repository and run:

```console
$ cargo install --path .
```

## Usage

```console
$ weekly-calendar -h
Usage: calendar <start_date> <end_date>

Dates should be in YYYY-MM-DD format

$ weekly-calendar 2024-08-12 2024-12-15
Aug 12 ◼ ◼ ◼ ◼ ◼ ◼ ◼
Aug 19 ◼ ◼ ◼ ◼ ◼ ◼ ◼
Aug 26 ◼ ◼ ◼ ◼ ◼ ◼ ◼
Sep 02 ◼ ◼ ◼ ◼ ◼ ◼ ◼
Sep 09 ◼ ◼ ◼ ◼ ◼ ◼ ◼
Sep 16 ◼ ◼ ◼ ◼ ◼ ◼ ◼
Sep 23 ◈ ◻ ◻ ◻ ◻ ◻ ◻
Sep 30 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Oct 07 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Oct 14 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Oct 21 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Oct 28 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Nov 04 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Nov 11 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Nov 18 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Nov 25 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Dec 02 ◻ ◻ ◻ ◻ ◻ ◻ ◻
Dec 09 ◻ ◻ ◻ ◻ ◻ ◻ ◻

Days passed:     43 (34.13%)
Days remaining:  83 (65.87%)
Total days:     126
```

Add `--todo PATH` to print the `$PATH` file after the calendar.

## License

This project is licensed under the GPL v3 or later:

    weekly-calendar: Show weekly progress calendar between two dates
    Copyright (C) 2024 Italo Luis da Silva

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

See the [LICENSE](LICENSE) file for the full license text.
