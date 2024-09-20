# arxiv-news

Extract titles and links from arXiv's daily email and present them in a more readable
Markdown format.

## Usage

```sh
$ uv run arxiv-news $URL
```

Where `$URL` is the link to the raw email. In Fastmail, this can be found by clicking
on Actions > Show Raw Message. Copy the URL and paste it in the command above.

If the email is long you can pipe to `less` (`-Rg` for colours and links):

```sh
$ uv run arxiv-news $URL | less -Rg
```

## License

This project is licensed under the GPL v3 or later:

    arxiv-news: Summarise arXiv daily emails
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
