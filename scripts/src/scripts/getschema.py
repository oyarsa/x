"""Get schema from JSON file, including nested structures."""

import argparse
import json

from scripts.util import HelpOnErrorArgumentParser

type Json = float | int | str | bool | None | list[Json] | dict[str, Json]


def merge_schemas(schemas: list[Json]) -> list[Json]:
    str_schemas = {json.dumps(schema) for schema in schemas}
    return sorted([json.loads(schema) for schema in str_schemas], key=str)


def get_schema(data: Json) -> Json:
    match data:
        case bool():
            return "bool"
        case int():
            return "int"
        case float():
            return "float"
        case str():
            return "string"
        case None:
            return "null"
        case list(items):
            return merge_schemas([get_schema(item) for item in items])
        case dict(d):
            return {key: get_schema(value) for key, value in d.items()}


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument("input", type=argparse.FileType(), help="Input JSON data file")
    parser.add_argument(
        "output", type=argparse.FileType("w"), help="Output JSON schema file"
    )
    args = parser.parse_args()

    data = json.load(args.input)
    schema = get_schema(data)
    args.output.write(json.dumps(schema, indent=2))


if __name__ == "__main__":
    main()
