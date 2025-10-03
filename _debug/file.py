from __future__ import annotations

import functools
import os
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Self, TextIO

from . import defaults as defaults

if TYPE_CHECKING:
    from _typeshed import SupportsWrite


class FileWrapper:
    _current: ClassVar[list[Self]] = []
    _file: SupportsWrite[str]

    def __init__(self, file: SupportsWrite[str]) -> None:
        self._file = file

    @classmethod
    def _pytest_enabled(cls) -> bool:
        return "PYTEST_VERSION" in os.environ

    @classmethod
    def _fallback_file(cls, file: Any) -> TextIO | None:
        if file == sys.stdout and sys.__stdout__ is not None:
            return sys.__stdout__
        elif file == sys.stderr and sys.__stderr__ is not None:
            return sys.__stderr__
        return None

    @functools.cached_property
    def supports_color(self) -> bool:
        """
        Returns True if the running system's terminal supports color, and False otherwise.
        Modified from from https://stackoverflow.com/a/22254892.
        """
        plat = sys.platform
        supported_platform = plat != "Pocket PC" and (plat != "win32" or "ANSICON" in os.environ)
        if not supported_platform:
            return False
        is_a_tty = hasattr(self._file, "isatty") and self._file.isatty()
        if not is_a_tty and self._pytest_enabled():
            fallback_file = self._fallback_file(self._file)
            if fallback_file is not None:
                is_a_tty = hasattr(fallback_file, "isatty") and fallback_file.isatty()
        return is_a_tty

    @functools.cached_property
    def terminal_width(self) -> int:
        width = defaults.DEFAULT_WIDTH
        try:
            width, _ = os.get_terminal_size(self._file.fileno())  # type: ignore
        except (OSError, AttributeError):
            if self._pytest_enabled():
                fallback_file = self._fallback_file(self._file)
                if fallback_file is not None:
                    try:
                        width, _ = os.get_terminal_size(fallback_file.fileno())
                    except (OSError, AttributeError):
                        ...
        if width < defaults.DEFAULT_WIDTH / 2:
            width = defaults.DEFAULT_WIDTH
        return width

    def write(self, text: str) -> None:
        self._file.write(text)

    @classmethod
    def back(cls) -> Self:
        return cls._current[-1]

    class lock:
        _file: SupportsWrite[str]

        def __init__(self, file: SupportsWrite[str]) -> None:
            self._file = file

        def __enter__(self) -> FileWrapper:
            FileWrapper._current.append(FileWrapper(self._file))
            return FileWrapper.back()

        def __exit__(
            self, exception_type: Any, exception_value: Any, exception_traceback: Any
        ) -> None:
            FileWrapper._current.pop()
