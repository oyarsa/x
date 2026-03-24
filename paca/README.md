# paca: PArse and create CAlendar appointments

Parse appointment information from image or text and create Google Calendar events.

## Installation

```console
git clone https://github.com/oyarsa/x.git
uv tool install x/cchs
```

## Usage

```console
# Search past conversations by keyword
$ cchs search "database migration"

# Natural language works too (stop words are removed automatically)
$ cchs search "how did we set up the auth middleware"

# Get more context around a result
$ cchs expand <message-uuid> --before 5 --after 10

# JSON output for programmatic use (e.g. from a Claude Code skill)
$ cchs search "auth" --json

# Rebuild the search index
$ cchs index --force

# Install as a Claude Code skill
$ cchs skill --install
```

## License

This project is licensed under the AGPL v3 or later:

    cchs: Claude Code history search
    Copyright (C) Italo Luis da Silva

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

See the [LICENSE](LICENSE) file for the full license text.
