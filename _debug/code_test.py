import textwrap

from pygments.formatters import Terminal256Formatter
import pytest

from .code import format_code, get_formatter, validate_style


@pytest.mark.parametrize("style", ["github-dark", "default"])
def test_config_formatter_valid_style_and_background(style: str) -> None:
    formatter = get_formatter(style)
    assert isinstance(formatter, Terminal256Formatter)
    assert formatter.style.name == style


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


@pytest.mark.parametrize(
    "code, expected",
    (
        # empty list
        ("[]", "[]"),
        # multiline addition
        (
            """
            1
            +
            2
            """,
            "1 + 2",
        ),
        # trailing comma list with spaces
        (
            "[1, 2, 3,]",
            """
            [
                1,
                2,
                3,
            ]
            """,
        ),
        # trailing comma list no spaces
        (
            "[1,2,3,]",
            """
            [
                1,
                2,
                3,
            ]
            """,
        ),
        # no trailing comma list with spaces
        (
            "[1, 2, 3]",
            "[1, 2, 3]",
        ),
        # no trailing comma list no spaces
        (
            "[1,2,3]",
            "[1, 2, 3]",
        ),
        # multiline addition with comment
        (
            """
            1
            + # add
            2
            """,
            "1 + 2",
        ),
        # string literal
        ("""'foo:bar,baz'""", """'foo:bar,baz'"""),
        # trailing comma dict with spaces
        (
            "{1: 2, 3: 4,}",
            """
            {
                1: 2,
                3: 4,
            }
            """,
        ),
        # trailing comma dict no spaces
        (
            "{1:2,3:4,}",
            """
            {
                1: 2,
                3: 4,
            }
            """,
        ),
        # no trailing comma dict with spaces
        (
            "{1: 2, 3: 4}",
            "{1: 2, 3: 4}",
        ),
        # no trailing comma dict no spaces
        (
            "{1:2,3:4}",
            "{1: 2, 3: 4}",
        ),
    ),
)
def test_format_code(code: str, expected: str) -> None:
    assert format_code(textwrap.dedent(code)).strip() == textwrap.dedent(expected).strip()
