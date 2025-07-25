import importlib
import os
import sys
import textwrap
from unittest import mock

from _pytest.capture import CaptureFixture
from pygments.formatters import Terminal256Formatter
import pytest
from strip_ansi import strip_ansi

from debug import CONFIG

SAMPLE_DIR = "test_samples"


@pytest.fixture(autouse=True)
def reset_modules() -> None:
    for key in list(sys.modules.keys()):
        if key.startswith(SAMPLE_DIR):
            del sys.modules[key]


@pytest.mark.parametrize(
    "name,expected_out,expected_err",
    [
        ("number", "12", "[number.py:3:7] 12 = 12"),
        ("variable", "17", "[variable.py:5:7] x = 17"),
        ("two_line", "-32", "[two_line.py:6:7] x * y = -32"),
        ("three_line", "14\n14", "[three_line.py:3:7] y := (10 + 4) = 14"),
        (
            "same_line",
            "7",
            """
            [same_line.py:6:7] x = 3
            [same_line.py:6:16] y = 4
            """,
        ),
        (
            "nested_expression",
            "4",
            """
            [nested_expression.py:5:11] x := x + 1 = 4
            [nested_expression.py:5:7] dbg(x := x + 1) = 4
            """,
        ),
        ("nested.file", "foo", "[nested/file.py:5:7] x = 'foo'"),
        ("offset", "5", "[offset.py:7:12] arg = 5"),
        ("no_offset", "-5", "[no_offset.py:3:12] arg = -5"),
        (
            "nested_function",
            "8",
            """
            [nested_function.py:8:16] a = 2
            [nested_function.py:8:25] b = 6
            """,
        ),
        (
            "multiple_arguments",
            "('hello', 8.5)",
            """
            [multiple_arguments.py:6:7] x = 'hello'
            [multiple_arguments.py:6:7] y = 8.5
            """,
        ),
        ("singleton", "False", "[singleton.py:4:7] v = False"),
        ("no_arguments", "()", "[no_arguments.py:3:7]"),
        (
            "multiline_arguments",
            "('bye', 0.25, -5)",
            """
            [multiline_arguments.py:7:7] x = 'bye'
            [multiline_arguments.py:7:7] y = 0.25
            [multiline_arguments.py:7:7] z + 4 = -5
            """,
        ),
        (
            "string",
            """
            foo
            bar
            """,
            """
            [string.py:3:7] 'foo' = 'foo'
            [string.py:4:7] "bar" = 'bar'
            """,
        ),
        ("brackets", "()", "[brackets.py:3:7] ((())) = ()"),
    ],
)
def test_samples(name: str, expected_out: str, expected_err, capsys: CaptureFixture) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.{name}"
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        importlib.import_module(module)

    expected_out = textwrap.dedent(expected_out).strip()
    expected_err = textwrap.dedent(expected_err).strip()

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert strip_ansi(err.strip()) == expected_err


@pytest.mark.parametrize(
    "name,expected_out,expected_err",
    [
        ("variable", "17", "[<string>:5:7] <unknown> = 17"),
        (
            "multiple_arguments",
            "('hello', 8.5)",
            """
            [<string>:6:7] <unknown> = 'hello'
            [<string>:6:7] <unknown> = 8.5
            """,
        ),
        ("no_arguments", "()", "[<string>:3:7]"),
    ],
)
def test_run_from_exec(name: str, expected_out: str, expected_err, capsys: CaptureFixture) -> None:
    filepath = os.path.join(SAMPLE_DIR, *name.split("."))
    filepath += ".py"
    with open(filepath) as f:
        source = f.read()

    cwd = os.getcwd()
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        exec(source)

    expected_out = textwrap.dedent(expected_out).strip()
    expected_err = textwrap.dedent(expected_err).strip()

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert strip_ansi(err.strip()) == expected_err


@pytest.mark.parametrize(
    "name,expected_out,expected_err",
    [
        ("variable", "17", "[<unknown>] <unknown> = 17"),
        (
            "multiple_arguments",
            "('hello', 8.5)",
            """
                [<unknown>] <unknown> = 'hello'
                [<unknown>] <unknown> = 8.5
                """,
        ),
        ("no_arguments", "()", "[<unknown>]"),
    ],
)
def test_with_no_frames(name: str, expected_out: str, expected_err, capsys: CaptureFixture) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.{name}"
    with (
        mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))),
        mock.patch("inspect.currentframe", mock.Mock(return_value=None)),
    ):
        importlib.import_module(module)

    expected_out = textwrap.dedent(expected_out).strip()
    expected_err = textwrap.dedent(expected_err).strip()

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert strip_ansi(err.strip()) == expected_err


@pytest.mark.parametrize("style", ["github-dark", "default"])
def test_config_formatter_valid_style_and_background(style: str):
    CONFIG.style = style
    formatter = CONFIG.formatter
    assert isinstance(formatter, Terminal256Formatter)
    assert formatter.style.name == style


def test_config_style_changes_code_highlighting(capsys: CaptureFixture) -> None:
    module = f"{SAMPLE_DIR}.string"

    CONFIG.color = True
    CONFIG.style = "github-dark"
    importlib.import_module(module)

    out_1, err_1 = capsys.readouterr()

    del sys.modules[module]

    CONFIG.color = True
    CONFIG.style = "bw"
    importlib.import_module(module)

    out_2, err_2 = capsys.readouterr()

    assert out_1 == out_2
    assert strip_ansi(err_1.strip()) == strip_ansi(err_2.strip())
    assert err_1.strip() != err_2.strip()
