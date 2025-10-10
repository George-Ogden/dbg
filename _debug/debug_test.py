from collections.abc import Iterator
import importlib
import os
import sys
import tempfile
import textwrap
from unittest import mock

from _pytest.capture import CaptureFixture
import pytest

from .conftest import SAMPLE_DIR
from .format import strip_ansi


@pytest.fixture(autouse=True, scope="module")
def reload_modules() -> None:
    if "debug" in sys.modules:
        importlib.reload(sys.modules["_debug.config"])
        importlib.reload(sys.modules["_debug.format"])
        importlib.reload(sys.modules["_debug"])
        importlib.reload(sys.modules["debug"])


@pytest.fixture(autouse=True)
def set_wide_indent() -> None:
    from .config import CONFIG

    CONFIG.indent = 4


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
        (
            "generator",
            "None",
            ["[generator.py:7:44] True = True", "[generator.py:7:44] <unknown> = True"],
        ),
        (
            "lists",
            """
            [8, 9, 10]
            [8, 9, 10]
            [A
            B, 'A\\nB']
            [1, 2, 3]
            """,
            """
            [lists.py:3:7] [8, 9, 10] = [8, 9, 10]
            [lists.py:7:7] [
                8,
                9,
                10,
            ] = [8, 9, 10]
            [lists.py:15:7] [MultilineObject(), "A\\nB"] = [
                A
                B,
                'A\\nB',
            ]
            [lists.py:17:7] [1, 2, 3] = [1, 2, 3]
            """,
        ),
        ("colored_repr", "[0]", "[colored_repr.py:8:7] ColoredRepr() = [0]"),
        (
            "pytest_width",
            "",
            f"""
            [pytest_width.py:3:1] ["X" * 40] * 2 = [
                {"X" * 40!r},
                {"X" * 40!r},
            ]
            """,
        ),
        (
            "single_spill",
            "(1, 2, 3)",
            """
            [single_spill.py:3:7] *[1, 2, 3] -> 1
            [single_spill.py:3:7] *[1, 2, 3] -> 2
            [single_spill.py:3:7] *[1, 2, 3] -> 3
            """,
        ),
        (
            "spill_edge_cases",
            """
            ()
            (1, 2, 3, 4)
            (4, 3, 2, 1)
            (1, 2, 3, 3, 2, 1)
            (1, 2, 3, 4, 3, 2, 1)
            (4, 3, 2, 1, 1, 2, 3, 4)
            """,
            """
            [spill_edge_cases.py:3:7]
            [spill_edge_cases.py:6:7] *xs -> 1
            [spill_edge_cases.py:6:7] *xs -> 2
            [spill_edge_cases.py:6:7] *xs -> 3
            [spill_edge_cases.py:6:7] 4 = 4
            [spill_edge_cases.py:7:7] 4 = 4
            [spill_edge_cases.py:7:7] *reversed(xs) -> 3
            [spill_edge_cases.py:7:7] *reversed(xs) -> 2
            [spill_edge_cases.py:7:7] *reversed(xs) -> 1
            [spill_edge_cases.py:8:7] *xs, *reversed(xs) -> 1
            [spill_edge_cases.py:8:7] *xs, *reversed(xs) -> 2
            [spill_edge_cases.py:8:7] *xs, *reversed(xs) -> 3
            [spill_edge_cases.py:8:7] *xs, *reversed(xs) -> 3
            [spill_edge_cases.py:8:7] *xs, *reversed(xs) -> 2
            [spill_edge_cases.py:8:7] *xs, *reversed(xs) -> 1
            [spill_edge_cases.py:9:7] *xs, 4, *reversed(xs) -> 1
            [spill_edge_cases.py:9:7] *xs, 4, *reversed(xs) -> 2
            [spill_edge_cases.py:9:7] *xs, 4, *reversed(xs) -> 3
            [spill_edge_cases.py:9:7] *xs, 4, *reversed(xs) -> 4
            [spill_edge_cases.py:9:7] *xs, 4, *reversed(xs) -> 3
            [spill_edge_cases.py:9:7] *xs, 4, *reversed(xs) -> 2
            [spill_edge_cases.py:9:7] *xs, 4, *reversed(xs) -> 1
            [spill_edge_cases.py:10:7] 4 = 4
            [spill_edge_cases.py:10:7] *reversed(xs), *xs -> 3
            [spill_edge_cases.py:10:7] *reversed(xs), *xs -> 2
            [spill_edge_cases.py:10:7] *reversed(xs), *xs -> 1
            [spill_edge_cases.py:10:7] *reversed(xs), *xs -> 1
            [spill_edge_cases.py:10:7] *reversed(xs), *xs -> 2
            [spill_edge_cases.py:10:7] *reversed(xs), *xs -> 3
            [spill_edge_cases.py:10:7] 4 = 4
            """,
        ),
        (
            "partial_fns",
            """
            0
            (10, 20, 30)
            (0, 1, 2, 3)
            (0, 1, 2, 3)
            """,
            """
            [partial_fns.py:6:7] 0 = 0
            [partial_fns.py:9:7] <unknown> = 10
            [partial_fns.py:9:7] <unknown> = 20
            [partial_fns.py:9:7] <unknown> = 30
            [partial_fns.py:12:7] *[1, 2, 3] -> 0
            [partial_fns.py:12:7] *[1, 2, 3] -> 1
            [partial_fns.py:12:7] *[1, 2, 3] -> 2
            [partial_fns.py:12:7] *[1, 2, 3] -> 3
            [partial_fns.py:16:7] 1 = 0
            [partial_fns.py:16:7] *[2, 3] -> 1
            [partial_fns.py:16:7] *[2, 3] -> 2
            [partial_fns.py:16:7] *[2, 3] -> 3
            """,
        ),
        (
            "stateful_repr",
            """
            stdout
            """,
            """
            stderr
            [stateful_repr.py:13:1] StatefulRepr() = repr
            """,
        ),
        (
            "many_files",
            """
            'stdout'
            'stdout'
            repr
            'stdout'
            """,
            """
            'stderr'
            'stderr'
            'stderr'
            repr
            """,
        ),
        ("pprint_sort", "{1: 3, 2: 2, 3: 1}", ""),
        pytest.param(
            "t_string",
            "",
            """"[t_string.py:3:1] t"{3.14}" = Template(strings=('', ''), interpolations=(Interpolation(3.14, '3.14', None, ''),))""",
            marks=[pytest.mark.skip] if sys.version_info < (3, 14) else [],
        ),
    ],
)
def test_samples(
    name: str, expected_out: str, expected_err: str | list[str], capsys: CaptureFixture
) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.{name}"
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        importlib.import_module(module)

    expected_out = textwrap.dedent(expected_out).strip()
    if not isinstance(expected_err, list):
        expected_err = [expected_err]
    expected_err = [textwrap.dedent(possible_err).strip() for possible_err in expected_err]

    out, err = capsys.readouterr()
    assert strip_ansi(out.strip()) == expected_out
    err = strip_ansi(err.strip())
    if len(expected_err) == 1:
        [expected_err] = expected_err
        assert err == expected_err
    else:
        assert err in expected_err


@pytest.fixture
def patch_tempfile() -> Iterator[str]:
    fd, filename = tempfile.mkstemp()
    try:
        with mock.patch("tempfile.mkstemp", mock.Mock(return_value=(fd, filename))):
            yield filename
    finally:
        os.remove(filename)


@pytest.mark.parametrize("name, expected", [("many_files", "'tempfile'")])
def test_write_to_tempfile(name: str, expected: str, patch_tempfile: str) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.{name}"
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        importlib.import_module(module)

    expected = textwrap.dedent(expected).strip()
    with open(patch_tempfile) as f:
        assert f.read().strip() == expected


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
def test_run_from_exec(
    name: str, expected_out: str, expected_err: str, capsys: CaptureFixture
) -> None:
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
def test_with_no_frames(
    name: str, expected_out: str, expected_err: str, capsys: CaptureFixture
) -> None:
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
