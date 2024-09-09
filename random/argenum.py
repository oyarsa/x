"""Use an Enum for argparse choices."""

import argparse
from enum import Enum


class Color(str, Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


parser = argparse.ArgumentParser()
parser.add_argument(
    "--color",
    type=Color,
    choices=[color.value for color in Color],
    default=[color.value for color in Color],
    nargs="*",
    help="Choose a color",
)

args = parser.parse_args()
print(f"Selected color: {args.color}")
