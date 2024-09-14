"""Find keys in JSON files that match a given keyword, recursively."""

import argparse
import json
from pathlib import Path

type JSONObject = list[JSONObject] | dict[str, JSONObject] | int | float | str | None


def normalise_key(key: str) -> str:
    return key.lower().replace(" ", "")


def search_object(obj: JSONObject, keyword: str, current_path: str = "") -> list[str]:
    results: list[str] = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{current_path}.{key}" if current_path else key
            if keyword in normalise_key(key):
                results.append(new_path)
            results.extend(search_object(value, keyword, new_path))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            new_path = f"{current_path}[{index}]"
            results.extend(search_object(item, keyword, new_path))

    return results


def main(paths: list[Path], keyword: str) -> None:
    keyword = normalise_key(keyword)

    for path in paths:
        for file_path in path.rglob("*.json"):
            data = json.loads(file_path.read_text())

            matches = search_object(data, keyword)
            if not matches:
                continue

            print(file_path)
            for match in matches:
                print(f"  {match}")
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search JSON files for objects with matching keys."
    )
    parser.add_argument("keyword", type=str, help="Keyword to search for in JSON keys")
    parser.add_argument(
        "paths", nargs="+", type=Path, help="List of paths to search for JSON files"
    )
    args = parser.parse_args()
    main(args.paths, args.keyword)
