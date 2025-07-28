import configparser
from dataclasses import dataclass
import inspect
import os.path
import sys
from typing import ClassVar

from pygments.formatters import Terminal256Formatter
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
    style: str
    color: bool

    def __init__(self) -> None:
        self.style = "solarized-dark"
        self.color = supports_color()

    UNKNOWN_MESSAGE: ClassVar[str] = "<unknown>"
    SECTION: ClassVar[str] = "dbg"

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
        try:
            config = configparser.ConfigParser(allow_unnamed_section=True)
        except TypeError:
            config = configparser.ConfigParser()
        try:
            config.read(filepath)
        except configparser.MissingSectionHeaderError:
            with open(filepath) as f:
                config_string = f"[{self.SECTION}]\n" + f.read()
                config.read_string(config_string)
        annotations = inspect.get_annotations(type(self))
        for section_name in config.sections():
            section = config[section_name]
            for key in section.keys():
                value_type = annotations.get(key, None)
                if value_type is None:
                    continue
                elif value_type is bool:
                    value = section.getboolean(key)
                else:
                    value = section[key]

                setattr(self, key, value)


CONFIG = DbgConfig()
