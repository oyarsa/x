"""Tests for parch.typing — runtime type checking utilities."""

from typing import Any

from parch.typing import is_dict_of, is_list_of

# ---------------------------------------------------------------------------
# is_list_of
# ---------------------------------------------------------------------------


class TestIsListOf:
    """Runtime check: is the object a list where every element has type T?"""

    def test_list_of_ints(self) -> None:
        assert is_list_of([1, 2, 3], int)

    def test_list_of_strs(self) -> None:
        assert is_list_of(["a", "b"], str)

    def test_empty_list_always_true(self) -> None:
        assert is_list_of([], int)

    def test_mixed_types_false(self) -> None:
        assert not is_list_of([1, "a"], int)

    def test_not_a_list(self) -> None:
        assert not is_list_of("hello", str)

    def test_tuple_is_not_list(self) -> None:
        assert not is_list_of((1, 2), int)

    def test_none_is_not_list(self) -> None:
        assert not is_list_of(None, int)

    def test_nested_lists(self) -> None:
        assert is_list_of([[1], [2]], list)


# ---------------------------------------------------------------------------
# is_dict_of
# ---------------------------------------------------------------------------


class TestIsDictOf:
    """Runtime check: is the object a dict[K, V]?"""

    def test_str_to_int(self) -> None:
        assert is_dict_of({"a": 1}, k=str, v=int)

    def test_str_to_str(self) -> None:
        assert is_dict_of({"a": "b"}, k=str, v=str)

    def test_empty_dict_always_true(self) -> None:
        assert is_dict_of({}, k=str, v=int)

    def test_wrong_key_type(self) -> None:
        assert not is_dict_of({1: "a"}, k=str, v=str)

    def test_wrong_value_type(self) -> None:
        assert not is_dict_of({"a": 1}, k=str, v=str)

    def test_not_a_dict(self) -> None:
        assert not is_dict_of([1, 2], k=str, v=int)

    def test_none_is_not_dict(self) -> None:
        assert not is_dict_of(None, k=str, v=int)

    def test_any_value_skips_value_check(self) -> None:
        assert is_dict_of({"a": 1, "b": "two", "c": [3]}, k=str, v=Any)

    def test_any_value_with_none(self) -> None:
        assert is_dict_of({"x": None}, k=str, v=Any)
