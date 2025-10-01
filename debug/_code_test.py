import pytest

from ._code import validate_style


@pytest.mark.parametrize(
    "style, error",
    [
        ("github-dark", None),
        ("solarized-light", None),
        ("", r"Unknown style ''\. Please, choose one of \['abap', 'algol',.*\]\."),
        ("made-up", r"Unknown style 'made-up'\. Please, choose one of \[.*\]\."),
    ],
)
def test_validate_style(style: str, error: str | None) -> None:
    if error is None:
        validate_style(style)
    else:
        with pytest.raises(ValueError, match=error):
            validate_style(style)
