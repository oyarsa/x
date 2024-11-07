"""Analyse Python modules to find the shortest path to each public item.

This script helps developers understand the best way to import items from a module by showing
the shortest available import path. It can also display class inheritance hierarchies.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from types import ModuleType
from typing import Annotated, NewType

import typer

ObjectPath = NewType("ObjectPath", str)


def main(
    module_name: Annotated[str, typer.Argument(help="Name of the module to analyse")],
    show_ancestors: Annotated[
        bool, typer.Option(help="Show class inheritance hierarchies")
    ] = False,
) -> None:
    """Process a module and print its public items.

    Takes a module name and outputs either just the paths to public items or, if
    show_ancestors is True, also includes inheritance information for classes.
    """
    try:
        for line in analyse_module(module_name, show_ancestors):
            print(line)
    except ModuleNotFoundError:
        print(f"Error: Module '{module_name}' not found")
    except Exception as e:
        print(f"Error analysing module: {e}")


def analyse_module(
    module_name: str,
    show_ancestors: bool = False,
) -> Iterable[str]:
    """Analyse a module and yield formatted strings describing its contents.

    Creates a comprehensive listing of the module's public items, optionally including
    inheritance information for classes.
    """
    module = importlib.import_module(module_name)
    seen_objects: dict[int, FoundObject] = {}

    for found in _get_module_items(module, "", seen_objects):
        if show_ancestors:
            if inspect.isclass(found.obj):
                yield f"{found.path} <: {_format_mro(found.obj)}"
        else:
            yield found.path


def _get_module_items(
    module: ModuleType, base_path: str, seen_objects: dict[int, FoundObject]
) -> Iterable[FoundObject]:
    """Extract all items from a module, tracking the shortest path to each.

    Recursively explores the module's attributes, keeping track of the shortest path
    to each unique object (identified by its id).
    """
    for name, obj in inspect.getmembers(module):
        if _is_private(name):
            continue

        current_path = f"{base_path}.{name}" if base_path else name
        obj_id = id(obj)

        # Skip if we've seen this object with a shorter path
        if obj_id in seen_objects and len(seen_objects[obj_id].path) <= len(
            current_path
        ):
            continue

        found_obj = FoundObject(obj=obj, path=ObjectPath(current_path))
        seen_objects[obj_id] = found_obj
        yield found_obj

        # Recursively handle submodules
        if (
            inspect.ismodule(obj)
            and hasattr(obj, "__package__")
            and (
                obj.__package__ and obj.__package__.startswith(module.__package__ or "")
            )
        ):
            yield from _get_module_items(obj, current_path, seen_objects)


@dataclass(frozen=True, kw_only=True)
class FoundObject:
    """Discovered object and its import path.

    Tracks both the object itself and the shortest path we've found to import it. The
    path is stored as a dot-separated string (e.g., 'aiohttp.ClientError').
    """

    obj: object
    path: ObjectPath


def _is_private(name: str) -> bool:
    """Determine if a name represents a private object.

    The name is private if it starts with an underscore but isn't a dunder method.
    """
    is_dunder = name.startswith("__") and name.endswith("__")
    return name.startswith("_") and not is_dunder


def _format_mro(cls: type) -> str:
    """Format the Method Resolution Order (MRO) of a class.

    Creates a readable representation of a class's inheritance hierarchy.
    """
    return ", ".join(
        f"{base.__module__}.{base.__qualname__}"
        if hasattr(base, "__module__")
        else base.__qualname__
        for base in cls.__mro__[:-1]  # Exclude `object`
    )
