"""Typing utils."""

from typing import Any, cast, overload

from typing_extensions import TypeIs


def is_list_of[T](obj: object, elem_type: type[T]) -> TypeIs[list[T]]:
    """Check if object is of type list[T].

    Exhaustively checks if all elements in the list are of type T.
    Checking empty lists always returns true.
    """
    if not isinstance(obj, list):
        return False
    if not obj:  # Empty list can be of any type
        return True

    obj = cast(list[object], obj)
    return all(isinstance(x, elem_type) for x in obj)


@overload
def is_dict_of[K, V](obj: object, *, k: type[K], v: type[V]) -> TypeIs[dict[K, V]]: ...
@overload
def is_dict_of[K](obj: object, *, k: type[K], v: Any) -> TypeIs[dict[K, Any]]: ...
def is_dict_of(obj: object, *, k: type, v: type | Any) -> bool:
    """Check if object is of type ``dict[K, V]``.

    Exhaustively checks if all keys are of type *k* and all values are of
    type *v*.  Pass ``v=Any`` to skip value checking.  Empty dicts always
    return True.

    Args:
        obj: The object to check.
        k: Expected key type.
        v: Expected value type, or ``Any`` to allow any value.

    Returns:
        True if *obj* is a dict with matching key/value types.
    """
    if not isinstance(obj, dict):
        return False
    if not obj:
        return True

    obj = cast(dict[object, object], obj)
    return all(
        isinstance(key, k) and (v is Any or isinstance(value, v))
        for key, value in obj.items()
    )
