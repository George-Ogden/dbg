import configparser
from dataclasses import dataclass
import inspect
import os.path
import re
import sys
from typing import ClassVar
import warnings

import platformdirs
from pygments.formatters import Terminal256Formatter
import pygments.styles
from pygments.token import Token


def supports_color() -> bool:
    """
    Returns True if the running system's terminal supports color, and False otherwise.
    Modified from from https://stackoverflow.com/a/22254892.
    """
    plat = sys.platform
    supported_platform = plat != "Pocket PC" and (plat != "win32" or "ANSICON" in os.environ)
    is_a_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    return supported_platform and is_a_tty


@dataclass
class DbgConfig:
    color: bool
    style: str  # type: ignore

    def __init__(self) -> None:
        self._style = "solarized-dark"
        self.color = supports_color()

    UNKNOWN_MESSAGE: ClassVar[str] = "<unknown>"
    FILENAME: ClassVar[str] = "dbg.conf"
    SECTION: ClassVar[str] = "dbg"
    USER_FILENAME: ClassVar[str] = os.path.join(platformdirs.user_config_dir("debug"), FILENAME)

    @property
    def style(self) -> str:
        return self._style

    @style.setter
    def style(self, value: str) -> None:
        if value in pygments.styles.get_all_styles():
            self._style = value
        else:
            warnings.warn(
                f"Invalid style {value!r}. Choose one of {list(pygments.styles.get_all_styles())}."
            )

    @property
    def formatter(self) -> Terminal256Formatter:
        return Terminal256Formatter(style=self.style, noitalic=True, nobold=True, nounderline=True)

    @property
    def unknown_message(self) -> str:
        if self.color:
            on, off = self.formatter.style_string[str(Token.Comment.Single)]
            return on + self.UNKNOWN_MESSAGE + off
        else:
            return self.UNKNOWN_MESSAGE

    def use_config(self, filepath: str) -> None:
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
            config_string = f"[{self.SECTION}]\n" + config_string
        try:
            config.read_string(config_string)
        except configparser.Error as e:
            warnings.warn(f"Unable to load config from '{filepath}'. ({type(e).__name__})")
            return
        annotations = inspect.get_annotations(type(self))
        if len(config.sections()) > 1:
            for section in config.sections():
                if section != self.SECTION:
                    warnings.warn(
                        f"Extra section [{section}] found in '{filepath}'. "
                        "Please, use no sections or one section called [dbg]."
                    )
        elif self.SECTION not in config.sections():
            for section in config.sections():
                warnings.warn(
                    f"Wrong section [{section}] used in '{filepath}'. "
                    "Please, use [dbg] or no sections."
                )
        for section_name in config.sections():
            section = config[section_name]
            for key in section.keys():
                value_type = annotations.get(key, None)
                if value_type is None:
                    warnings.warn(f"Unused field '{key}' found in '{filepath}'.")
                    continue
                elif value_type is bool:
                    value = section.getboolean(key)
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


CONFIG = DbgConfig()
if not os.path.exists(CONFIG.USER_FILENAME):
    os.makedirs(os.path.dirname(CONFIG.USER_FILENAME), exist_ok=True)
    try:
        with (
            open(CONFIG.USER_FILENAME, "x") as config_file,
            open(os.path.join(os.path.dirname(__file__), "default.conf")) as default_file,
        ):
            config_file.write(default_file.read())
    except OSError:
        ...

CONFIG.use_config(CONFIG.USER_FILENAME)
