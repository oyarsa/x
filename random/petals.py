"""Calculate expected gold difference between teams from Spirit Petals."""

import argparse
from typing import Protocol, cast


def gold_from_stacks(stacks: int) -> float:
    """Calculate the gold value based on the number of stacks.

    Uses predefined mapping for stacks 1-34, and 8.74 per additional stack for 35+.

    Args:
        stacks: Number of stacks.

    Returns:
        Gold value for the given number of stacks.
    """

    stacks_data = {
        1: 26.25,
        2: 52.5,
        3: 76.13,
        4: 102.38,
        5: 126,
        6: 149.63,
        7: 173.25,
        8: 194.25,
        9: 217.88,
        10: 238.88,
        11: 259.88,
        12: 280.88,
        13: 299.25,
        14: 320.25,
        15: 338.63,
        16: 357,
        17: 375.38,
        18: 391.13,
        19: 409.5,
        20: 425.25,
        21: 441,
        22: 456.75,
        23: 469.88,
        24: 485.63,
        25: 498.75,
        26: 511.88,
        27: 525,
        28: 535.5,
        29: 548.63,
        30: 559.13,
        31: 569.63,
        32: 580.13,
        33: 588,
        34: 598.5,
    }

    if stacks <= 0:
        return 0.0

    if stacks <= 34:
        return stacks_data[stacks]

    # For stacks 35+, use base value at stack 34 + 8.74 per additional stack
    base_value = stacks_data[34]
    additional_stacks = stacks - 34
    return base_value + (additional_stacks * 8.74)


def gold_diff(stacks_blue: int, stacks_red: int) -> float:
    """Calculate the gold difference between blue and red teams based on the stacks.

    Args:
        stacks_blue: Number of stacks for blue team.
        stacks_red: Number of stacks for red team.

    Returns:
        (Blue team petals gold - Red team petals gold) * 5.
    """
    blue_gold = gold_from_stacks(stacks_blue)
    red_gold = gold_from_stacks(stacks_red)
    return (blue_gold - red_gold) * 5


def main():
    """CLI interface for calculating gold difference between teams."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blue", type=int, help="Number of stacks for blue team.")
    parser.add_argument("red", type=int, help="Number of stacks for red team.")

    class Args(Protocol):
        blue: int
        red: int

    args: Args = cast(Args, parser.parse_args())

    difference = gold_diff(args.blue, args.red)
    # Determine advantage team
    colour = "blue" if difference > 0 else "red"

    for team, stacks in [("blue", args.blue), ("red", args.red)]:
        cprint(
            f"{team} team: {stacks} stacks ({gold_from_stacks(stacks):.2f} gold)",
            team,
        )
    cprint(f"gold difference ({colour}) * 5: {difference:.2f}", colour)


def cprint(msg: str, colour: str) -> None:
    # ANSI color codes
    colours = {
        "blue": "\033[94m",
        "red": "\033[91m",
    }
    reset = "\033[0m"

    assert colour in colours, f"Colour unsupported: {colour}"

    print(f"{colours[colour]}{msg}{reset}")


if __name__ == "__main__":
    main()
