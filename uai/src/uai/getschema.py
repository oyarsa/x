"""Get schema from JSON file, including nested structures."""

import json
from pathlib import Path
from typing import Annotated

import typer

from uai.util import read_json, write_json

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


def main(
    input: Annotated[Path, typer.Argument(help="Input JSON data file")] = Path("-"),
    output: Annotated[Path, typer.Argument(help="Output JSON schema file")] = Path("-"),
) -> None:
    data = read_json(input)
    schema = get_schema(data)
    write_json(schema, output)
