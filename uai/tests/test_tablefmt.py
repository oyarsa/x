"""Tests for tablefmt command."""

from uai.tablefmt import format_table, is_separator_row, parse_table


class TestParseTable:
    def test_simple_table(self) -> None:
        text = """\
| A | B |
|---|---|
| 1 | 2 |
"""
        rows = parse_table(text)
        assert rows == [["A", "B"], ["---", "---"], ["1", "2"]]

    def test_table_with_line_numbers(self) -> None:
        """Tables with line numbers and prefix characters are stripped correctly."""
        text = """\
      64 -| Name | Eval Prompt | Sources | Description |
      65 -|------|-------------|---------|-------------|
      66 -| Sans | `sans` | N/A | Abstract only (baseline) |
      67 -| Related only | `related` | both | Related papers without graph |
"""
        rows = parse_table(text)
        assert len(rows) == 4
        assert rows[0] == ["Name", "Eval Prompt", "Sources", "Description"]
        assert rows[2] == ["Sans", "`sans`", "N/A", "Abstract only (baseline)"]
        assert rows[3] == [
            "Related only",
            "`related`",
            "both",
            "Related papers without graph",
        ]

    def test_empty_input(self) -> None:
        assert parse_table("") == []

    def test_no_pipes(self) -> None:
        assert parse_table("no table here") == []


class TestIsSeparatorRow:
    def test_simple_separator(self) -> None:
        assert is_separator_row(["---", "---", "---"])

    def test_left_aligned(self) -> None:
        assert is_separator_row([":---", "---", "---"])

    def test_right_aligned(self) -> None:
        assert is_separator_row(["---:", "---", "---"])

    def test_center_aligned(self) -> None:
        assert is_separator_row([":---:", "---", "---"])

    def test_not_separator(self) -> None:
        assert not is_separator_row(["text", "---", "---"])
        assert not is_separator_row(["Name", "Value", "Description"])


class TestFormatTable:
    def test_simple_table(self) -> None:
        rows = [["A", "B"], ["---", "---"], ["1", "2"]]
        result = format_table(rows)
        expected = """\
| A | B |
|---|---|
| 1 | 2 |"""
        assert result == expected

    def test_padding(self) -> None:
        rows = [
            ["Name", "Description"],
            ["---", "---"],
            ["Short", "A longer description"],
        ]
        result = format_table(rows)
        expected = """\
| Name  | Description          |
|-------|----------------------|
| Short | A longer description |"""
        assert result == expected

    def test_user_example(self) -> None:
        """Test the exact example from the user."""
        input_text = """\
      64 -| Name | Eval Prompt | Sources | Description |
      65 -|------|-------------|---------|-------------|
      66 -| Sans | `sans` | N/A | Abstract only (baseline) |
      67 -| Related only | `related` | both | Related papers without graph |
      68 -| Graph only | `norel-graph` | N/A | Graph without related papers |
      69 -| Citations only | `full-graph-structured` | citations | Full pipeline, citations only |
      70 -| Semantic only | `full-graph-structured` | semantic | Full pipeline, semantic only |
      71 -| Full | `full-graph-structured` | both | Full pipeline (baseline) |
"""
        rows = parse_table(input_text)
        result = format_table(rows)
        expected = """\
| Name           | Eval Prompt             | Sources   | Description                   |
|----------------|-------------------------|-----------|-------------------------------|
| Sans           | `sans`                  | N/A       | Abstract only (baseline)      |
| Related only   | `related`               | both      | Related papers without graph  |
| Graph only     | `norel-graph`           | N/A       | Graph without related papers  |
| Citations only | `full-graph-structured` | citations | Full pipeline, citations only |
| Semantic only  | `full-graph-structured` | semantic  | Full pipeline, semantic only  |
| Full           | `full-graph-structured` | both      | Full pipeline (baseline)      |"""
        assert result == expected

    def test_empty_table(self) -> None:
        assert format_table([]) == ""
