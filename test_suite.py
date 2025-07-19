import importlib
import textwrap

from _pytest.capture import CaptureFixture
import pytest

MODULE = "test_samples"


@pytest.mark.parametrize(
    "name,expected_out,expected_err",
    [
        ("number", "12", "[number.py:3] 12 = 12"),
        ("variable", "17", "[variable.py:4] x = 17"),
        ("two_line", "-32", "[two_line.py:6] x * y = -32"),
        ("three_line", "14\n14", "[three_line.py:3] (y := (10 + 4)) = 14"),
        (
            "same_line",
            "7",
            """
            [same_line.py:6] x = 3
            [same_line.py:6] y = 4
            """,
        ),
        (
            "nested_expression",
            "4",
            """
            [nested_expression.py:5] (x := (x + 1)) = 4
            [nested_expression.py:5] dbg((x := (x + 1))) = 4
            """,
        ),
    ],
)
def test_samples(name: str, expected_out: str, expected_err, capsys: CaptureFixture) -> None:
    module = f"{MODULE}.{name}"
    importlib.import_module(module)

    expected_out = textwrap.dedent(expected_out).strip()
    expected_err = textwrap.dedent(expected_err).strip()

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert err.strip() == expected_err
