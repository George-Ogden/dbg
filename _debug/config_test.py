import filecmp
import importlib
import os
import re
import sys
import tempfile
from typing import Any
from unittest import mock

from _pytest.capture import CaptureFixture
import pytest

from . import CONFIG
from .config import DbgConfig
from .conftest import SAMPLE_DIR, TEST_DATA_DIR
from .format import strip_ansi


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


def test_highlighting_avoided_with_ansi(capsys: CaptureFixture) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.colored_repr"
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        from _debug import CONFIG

        CONFIG.color = True
        CONFIG.style = "solarized-dark"
        importlib.import_module(module)

    expected_out = "\x1b[40m\x1b[97m[0]\x1b[0m"
    expected_err = "[colored_repr.py:8:7] ColoredRepr() = \x1b[40m\x1b[97m[0]\x1b[0m"

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert strip_ansi(err.strip().split(" = ")[0]) == expected_err.split(" = ")[0]
    assert err.strip().split(" = ")[1] == expected_err.split(" = ")[1]


@pytest.mark.parametrize(
    "name, settings",
    [
        ("disabled", dict(color=False)),
        ("monokai", dict(style="monokai", color=True)),
        ("extra_section", dict(style="default", color=False)),
        ("unused_field", dict(style="default")),
        ("style_quotes", dict(style="algol")),
        ("color_quotes", dict(color="auto")),
        ("syntax_error", dict()),
        ("location_error", dict()),
        ("empty", dict()),
        ("../debug/default", dict()),
        ("wide_indent", dict(indent=4)),
        ("auto_color", dict(color="auto")),
        ("invalid_indent", dict()),
        ("invalid_color", dict()),
    ],
)
@pytest.mark.filterwarnings("ignore")
def test_load_config(name: str, settings: dict[str, Any]) -> None:
    config = DbgConfig()
    filename = os.path.join(TEST_DATA_DIR, name + ".conf")
    config.use_config(filename)

    expected_config = DbgConfig()
    for k, v in settings.items():
        setattr(expected_config, k, v)
    assert config == expected_config


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
            "style_quotes",
            'Quotes used around "algol" in $. '
            "They will be ignored, but please remove to silence this warning.",
        ),
        (
            "color_quotes",
            "Quotes used around 'auto' in $. "
            "They will be ignored, but please remove to silence this warning.",
        ),
        ("wrong_section", "Wrong section [debugging] used in $. Please, use [dbg] or no sections."),
        ("syntax_error", "Unable to load config from $. (ParsingError)"),
        ("location_error", "Unable to load config from $. (FileNotFoundError)"),
        (
            "invalid_indent",
            "Invalid value '\"----\"' found in field 'indent' (expected int) in $.",
        ),
        (
            "invalid_color",
            "Invalid value 'bad-color' found in field 'color' (expected bool or 'auto') in $.",
        ),
    ],
)
def test_load_config_displays_warning(name: str, warning_message: str) -> None:
    config = DbgConfig()
    filename = os.path.join(TEST_DATA_DIR, name + ".conf")

    filename_msg = f"'{os.path.abspath(filename)}'"
    warning_regex = re.escape(warning_message.replace("$", filename_msg))
    with pytest.warns(match=warning_regex):
        config.use_config(filename)


def test_invalid_style_warns() -> None:
    config = DbgConfig()
    config.style = "monokai"

    with pytest.warns(match=r"Unknown style 'invalid'\. Please, choose one of .*\."):
        config.style = "invalid"

    assert config.style == "monokai"


def test_creates_default_config() -> None:
    temp_dir = tempfile.mkdtemp()
    config_filename = os.path.join(temp_dir, "debug", "dbg.conf")

    def user_config_dir(appname: str) -> str:
        return os.path.join(temp_dir, appname)

    with mock.patch("platformdirs.user_config_dir", user_config_dir):
        importlib.reload(sys.modules["_debug.config"])
        importlib.reload(sys.modules["_debug"])
        if "debug" in sys.modules:
            importlib.reload(sys.modules["debug"])
        from debug import dbg

        _ = dbg

    assert os.path.exists(config_filename)
    assert os.path.getsize(config_filename) > 0
    assert filecmp.cmp(config_filename, "_debug/default.conf")


def test_loads_default_config() -> None:
    temp_dir = tempfile.mkdtemp()
    config_filename = os.path.join(temp_dir, "debug", "dbg.conf")
    os.mkdir(os.path.dirname(config_filename))
    with open(config_filename, "w") as f:
        f.write("style = fruity")

    def user_config_dir(appname: str) -> str:
        return os.path.join(temp_dir, appname)

    with mock.patch("platformdirs.user_config_dir", user_config_dir):
        importlib.reload(sys.modules["_debug.config"])
        importlib.reload(sys.modules["_debug"])
        importlib.reload(sys.modules["debug"])
        from _debug import CONFIG

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
        importlib.reload(sys.modules["_debug.config"])
        importlib.reload(sys.modules["_debug"])
        importlib.reload(sys.modules["debug"])
        from _debug import CONFIG

    assert CONFIG.style == "vim"
