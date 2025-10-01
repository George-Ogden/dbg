import configparser
from dataclasses import dataclass
import inspect
import os.path
import re
import sys
from typing import Any, ClassVar
import warnings

import platformdirs
from pygments.formatters import Terminal256Formatter

from ._code import validate_style


def pytest_enabled() -> bool:
    return "PYTEST_VERSION" in os.environ


def supports_color() -> bool:
    """
    Returns True if the running system's terminal supports color, and False otherwise.
    Modified from from https://stackoverflow.com/a/22254892.
    """
    plat = sys.platform
    supported_platform = plat != "Pocket PC" and (plat != "win32" or "ANSICON" in os.environ)
    is_a_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    if not is_a_tty and pytest_enabled() and sys.__stderr__ is not None:
        is_a_tty = hasattr(sys.__stderr__, "isatty") and sys.__stderr__.isatty()
    return supported_platform and is_a_tty


@dataclass
class DbgConfig:
    color: bool
    indent: int
    style: str

    def __init__(self) -> None:
        self._style = "solarized-dark"
        self.color = supports_color()
        self.indent = 2

    _FILENAME: ClassVar[str] = "dbg.conf"
    _SECTION: ClassVar[str] = "dbg"
    DEFAULT_WIDTH: ClassVar[int] = 80
    _USER_FILENAME: ClassVar[str] = os.path.join(platformdirs.user_config_dir("debug"), _FILENAME)
    _LOCAL_FILENAME: ClassVar[str] = os.path.join(os.getcwd(), _FILENAME)

    @property  # type: ignore
    def style(self) -> str:
        return self._style

    @style.setter
    def style(self, value: str) -> None:
        try:
            validate_style(value)
        except ValueError as e:
            warnings.warn(str(e))
        else:
            self._style = value

    @property
    def _formatter(self) -> Terminal256Formatter:
        return Terminal256Formatter(style=self.style, noitalic=True, nobold=True, nounderline=True)

    def _use_config(self, filepath: str) -> None:
        filepath = os.path.abspath(filepath)
        config = configparser.ConfigParser()
        try:
            with open(filepath) as f:
                config_string = f.read()
        except OSError as e:
            warnings.warn(f"Unable to load config from '{filepath}'. ({type(e).__name__})")
            return
        try:
            config.read_string(config_string)
        except configparser.MissingSectionHeaderError:
            config_string = f"[{self._SECTION}]\n" + config_string
        try:
            config.read_string(config_string)
        except configparser.Error as e:
            warnings.warn(f"Unable to load config from '{filepath}'. ({type(e).__name__})")
            return
        annotations = inspect.get_annotations(type(self))
        if len(config.sections()) > 1:
            for section_name in config.sections():
                if section_name != self._SECTION:
                    warnings.warn(
                        f"Extra section [{section_name}] found in '{filepath}'. "
                        "Please, use no sections or one section called [dbg]."
                    )
        elif self._SECTION not in config.sections():
            for section_name in config.sections():
                warnings.warn(
                    f"Wrong section [{section_name}] used in '{filepath}'. "
                    "Please, use [dbg] or no sections."
                )
        for section_name in config.sections():
            section = config[section_name]
            for key in section.keys():
                value_type = annotations.get(key, None)
                value: Any
                if value_type is None:
                    warnings.warn(f"Unused field '{key}' found in '{filepath}'.")
                    continue
                elif value_type is bool:
                    value = section.getboolean(key)
                elif value_type is int:
                    value = section.getint(key)
                else:
                    value = section[key]
                    match = re.match(r"^('(.*)'|\"(.*)\")$", value)
                    if match:
                        warnings.warn(
                            f"Quotes used around {value} in '{filepath}'. "
                            "They will be ignored, but please remove to silence this warning."
                        )
                        value = (match.group(2) or "") + (match.group(3) or "")

                setattr(self, key, value)

    @classmethod
    def _get_terminal_width(cls) -> int:
        width = cls.DEFAULT_WIDTH
        try:
            width, _ = os.get_terminal_size(sys.stderr.fileno())
        except OSError:
            if pytest_enabled():
                stderr = sys.__stderr__
                if stderr is not None:
                    try:
                        width, _ = os.get_terminal_size(stderr.fileno())
                    except OSError:
                        ...
        if width < cls.DEFAULT_WIDTH / 2:
            width = cls.DEFAULT_WIDTH
        return width


CONFIG = DbgConfig()
if not os.path.exists(CONFIG._USER_FILENAME):
    os.makedirs(os.path.dirname(CONFIG._USER_FILENAME), exist_ok=True)
    try:
        with (
            open(CONFIG._USER_FILENAME, "x") as config_file,
            open(os.path.join(os.path.dirname(__file__), "default.conf")) as default_file,
        ):
            config_file.write(default_file.read())
    except OSError:
        ...

CONFIG._use_config(CONFIG._USER_FILENAME)
if os.path.exists(CONFIG._LOCAL_FILENAME):
    CONFIG._use_config(CONFIG._LOCAL_FILENAME)
