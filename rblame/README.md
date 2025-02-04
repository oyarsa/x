# rblame: Pretty print git blame for a file

## Example

```console
$ rblame

Pretty print git blame of a file

Usage: rblame <FILE>

Arguments:
  <FILE>  File to get blame

Options:
  -h, --help     Print help
  -V, --version  Print version
```

```console
$ rblame Cargo.toml

8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 1  [package]
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 2  name = "rblame"
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 3  version = "0.0.1"
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 4  edition = "2021"
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 5  authors = ["Italo Silva <italo@maleldil.com>"]
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 6  license = "GPL-3.0-or-later"
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 7  description = "Pretty print git blame of a file"
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 8
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 9  [dependencies]
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 10 clap = { version = "4.5.27", features = ["derive"] }
8b1056bb Cargo.toml Italo Silva Initial commit with full funcionality 11 regex = "1.11.1"
```

Note: the actual output has different colours for each column.


## License

This project is licensed under the GPL v3 or later:

    rblame: pretty print git blame for a file
    Copyright (C) 2025 The rblame contributors

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
