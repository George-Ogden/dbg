from dataclasses import dataclass
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


CONFIG = DbgConfig()
