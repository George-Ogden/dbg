import filecmp
import importlib
import os
import re
import sys
import tempfile
import textwrap
from typing import Any
from unittest import mock

from _pytest.capture import CaptureFixture
from pygments.formatters import Terminal256Formatter
import pytest
from strip_ansi import strip_ansi

from debug import CONFIG
from debug._config import DbgConfig

SAMPLE_DIR = "test_samples"
TEST_DATA_DIR = "test_data"


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
        (
            "lists",
            """
                [8, 9, 10]
                [8, 9, 10]
            """,
            """
                [lists.py:3:7] [8, 9, 10] = [8, 9, 10]
                [lists.py:7:7] [
                    8,
                    9,
                    10,
                ] = [8, 9, 10]
            """,
        ),
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
    formatter = CONFIG._formatter
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


@pytest.mark.parametrize(
    "name, settings",
    [
        ("disabled", dict(color=False)),
        ("monokai", dict(style="monokai", color=True)),
        ("extra_section", dict(style="default", color=False)),
        ("unused_field", dict(style="default")),
        ("quotes", dict(style="algol")),
        ("syntax_error", dict()),
        ("location_error", dict()),
        ("empty", dict()),
        ("../debug/default", dict()),
    ],
)
@pytest.mark.filterwarnings("ignore")
def test_load_config(name: str, settings: dict[str, Any]) -> None:
    config = DbgConfig()
    filename = os.path.join(TEST_DATA_DIR, name + ".conf")
    config._use_config(filename)

    expected_config = DbgConfig()
    for k, v in settings.items():
        setattr(expected_config, k, v)
    assert expected_config == config


@pytest.mark.parametrize(
    "name, warning_message",
    [
        (
            "extra_section",
            "Extra section [extra] found in $. "
            "Please, use no sections or one section called [dbg].",
        ),
        ("unused_field", "Unused field 'extra' found in $"),
        (
            "quotes",
            'Quotes used around "algol" in $. '
            "They will be ignored, but please remove to silence this warning.",
        ),
        ("wrong_section", "Wrong section [debugging] used in $. Please, use [dbg] or no sections."),
        ("syntax_error", "Unable to load config from $. (ParsingError)"),
        ("location_error", "Unable to load config from $. (FileNotFoundError)"),
    ],
)
def test_load_config_displays_warning(name: str, warning_message: str) -> None:
    config = DbgConfig()
    filename = os.path.join(TEST_DATA_DIR, name + ".conf")

    filename_msg = f"'{os.path.abspath(filename)}'"
    warning_regex = re.escape(warning_message.replace("$", filename_msg))
    with pytest.warns(match=warning_regex):
        config._use_config(filename)


def test_invalid_style_warns() -> None:
    config = DbgConfig()
    config.style = "monokai"

    with pytest.warns(match=r"Invalid style 'invalid'\. Choose one of .*\."):
        config.style = "invalid"

    assert "monokai" == config.style


def test_creates_default_config() -> None:
    temp_dir = tempfile.mkdtemp()
    config_filename = os.path.join(temp_dir, "debug", "dbg.conf")

    def user_config_dir(appname: str) -> str:
        return os.path.join(temp_dir, appname)

    with mock.patch("platformdirs.user_config_dir", user_config_dir):
        importlib.reload(sys.modules["debug._config"])
        from debug import dbg

        _ = dbg

    assert os.path.exists(config_filename)
    assert os.path.getsize(config_filename) > 0
    assert filecmp.cmp(config_filename, "debug/default.conf")


def test_loads_default_config() -> None:
    temp_dir = tempfile.mkdtemp()
    config_filename = os.path.join(temp_dir, "debug", "dbg.conf")
    os.mkdir(os.path.dirname(config_filename))
    with open(config_filename, "w") as f:
        f.write("style = fruity")

    def user_config_dir(appname: str) -> str:
        return os.path.join(temp_dir, appname)

    with mock.patch("platformdirs.user_config_dir", user_config_dir):
        importlib.reload(sys.modules["debug._config"])
        importlib.reload(sys.modules["debug._debug"])
        importlib.reload(sys.modules["debug"])
        from debug import CONFIG

    assert CONFIG.style == "fruity"


def test_loads_default_config_over_user_config() -> None:
    user_dir = tempfile.mkdtemp()
    user_config_filename = os.path.join(user_dir, "debug", "dbg.conf")
    os.mkdir(os.path.dirname(user_config_filename))
    with open(user_config_filename, "w") as f:
        f.write("style = fruity")

    current_dir = tempfile.mkdtemp()
    local_config_filename = os.path.join(current_dir, "dbg.conf")
    with open(local_config_filename, "w") as f:
        f.write("style = vim")

    def user_config_dir(appname: str) -> str:
        return os.path.join(user_dir, appname)

    with (
        mock.patch("platformdirs.user_config_dir", user_config_dir),
        mock.patch("os.getcwd", mock.Mock(return_value=current_dir)),
    ):
        importlib.reload(sys.modules["debug._config"])
        importlib.reload(sys.modules["debug._debug"])
        importlib.reload(sys.modules["debug"])
        from debug import CONFIG

    assert CONFIG.style == "vim"
