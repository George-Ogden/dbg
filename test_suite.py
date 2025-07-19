import importlib

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
    ],
)
def test_samples(name: str, expected_out: str, expected_err, capsys: CaptureFixture) -> None:
    module = f"{MODULE}.{name}"
    importlib.import_module(module)

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert err.strip() == expected_err
