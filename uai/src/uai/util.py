import json
import sys
from pathlib import Path
from typing import Any


def read_json(input_path: Path) -> Any:
    """Read JSON from `input_path`. If it's '-', read from stdin."""
    if input_path.name == "-":
        return json.load(sys.stdin)
    else:
        return json.loads(input_path.read_bytes())


def read_text(input_path: Path) -> str:
    """Read text from `input_path`. If it's '-', read from stdin."""
    if input_path.name == "-":
        return sys.stdin.read()
    else:
        return input_path.read_text()


def write_json(data: Any, output_path: Path) -> None:
    """Write `data` as JSON to `output_path`. If it's '-', print to stdout."""
    if output_path.name == "-":
        json.dump(data, sys.stdout, indent=2)
    else:
        output_path.write_text(json.dumps(data, indent=2))
