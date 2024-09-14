#!/usr/bin/env python3
"""Search for a term in the Webster 1913 dictionary.

Converted from the original Perl script from https://github.com/dnmfarrell/WebsterSearch.
"""

import argparse
import re
from pathlib import Path


def main(search_term: str) -> None:
    search_term = (search_term).upper() + "\n"
    entry_pattern = re.compile(r"^[A-Z][A-Z0-9' ;-]*$")
    index = {
        "A": 601,
        "B": 1796502,
        "C": 3293436,
        "D": 6039049,
        "E": 7681559,
        "F": 8833301,
        "G": 10034091,
        "H": 10926753,
        "I": 11930292,
        "J": 13148994,
        "K": 13380269,
        "L": 13586035,
        "M": 14532408,
        "N": 15916448,
        "O": 16385339,
        "P": 17042770,
        "Q": 19439223,
        "R": 19610041,
        "S": 21015876,
        "T": 24379537,
        "U": 25941093,
        "V": 26405366,
        "W": 26925697,
        "X": 27748359,
        "Y": 27774096,
        "Z": 27866401,
    }

    dictionary_path = Path(__file__).with_name("webster-1913.txt")

    with dictionary_path.open("r", encoding="latin1") as dict_file:
        start = index.get(search_term[0], 0)
        dict_file.seek(start)

        found_match = False
        while True:
            line = dict_file.readline()
            if not line:
                break  # End of file

            line_stripped = line.rstrip("\n")
            if not entry_pattern.match(line_stripped):
                continue

            if line == search_term:
                output = line  # line includes newline
                while True:
                    pos_before_next_line = dict_file.tell()
                    next_line = dict_file.readline()
                    if not next_line:
                        break  # End of file
                    next_line_stripped = next_line.rstrip("\n")
                    if entry_pattern.match(next_line_stripped):
                        dict_file.seek(pos_before_next_line)
                        break
                    output += next_line
                print(output, end="")
                found_match = True

            if found_match and search_term.rstrip("\n") < line_stripped:
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("search_term", type=str, help="The term to search for")
    args = parser.parse_args()
    main(args.search_term)
