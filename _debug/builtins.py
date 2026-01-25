import builtins
import contextlib

from .debug import dbg


def install() -> None:
    builtins.dbg = dbg  # type: ignore [attr-defined]


def uninstall() -> None:
    with contextlib.suppress(AttributeError):
        del builtins.dbg  # type: ignore [attr-defined]
