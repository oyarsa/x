# gigs-in-towns: Process ICS files to deliver statistics on concert events

## Example usage

0. This project uses [`uv`](https://docs.astral.sh/uv/getting-started/). Install it, if
   you don't have it. It's really good; you should use it.
1. Export a calendar from Google Calendar:
    1. Go to Google Calendar Settings (gear icon).
    2. Select "Import & Export".
    3. Under "Export" click the "Export" button to download all calendars as a zip of
       `.ics `files.
    4. Unzip the file and select your file. We'll call it, for this example, `gigs.ics`.
2. Convert to our YAML format:
```bash
# Replace `gigs.ics` with your downloaded calendar and `gigs.yaml` with your output path
uv run gigs-in-town convert gigs.ics gigs.yaml
```

3. Hand-edit the `gigs.yaml` file to make sure the names, locations and dates are
   correct. This tool assumes that if you're interested in multiple bands in the same
   date, they're written under the same event separated by `&`, e.g. `'Kamelot &
   Blackbriar'`.
4. Run the statistics tool on your edited file. ```bash uv run gigs-in-town stats
   gigs_handedited.yaml ```

## License

This project is licensed under the GPL v3 or later:

    gigs-in-towns: Process ICS files to deliver statistics on concert events.
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
