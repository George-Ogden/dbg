from __future__ import annotations

import abc
from collections.abc import Iterable
from dataclasses import dataclass, field
import os
import sys
import textwrap
from typing import Any


class FormattedObj(abc.ABC):
    @abc.abstractmethod
    def length(self) -> int | None: ...

    @abc.abstractmethod
    def _format(self, width: None | int, config: FormatterConfig) -> str: ...

    @classmethod
    def total_length(cls, objs: Iterable[FormattedObj]) -> int | None:
        total_length = 0
        for obj in objs:
            length = obj.length()
            if length is None:
                return None
            total_length += length
        return total_length

    @classmethod
    def add(cls, a: None | int, b: None | int) -> int | None:
        if a is None or b is None:
            return None
        return a + b


class SequenceFormat(FormattedObj, abc.ABC):
    def __init__(self, objs: list[FormattedObj]) -> None:
        self._objs = objs
        self._length = self.add(FormattedObj.total_length(objs), 2)
        if len(self._objs) > 0:
            self._length = self.add(self._length, (len(self._objs) - 1) * 2)

    def length(self) -> int | None:
        return self._length

    def _format(self, width: None | int, config: FormatterConfig) -> str:
        length = self.length()
        if len(self._objs) == 0 or (length is not None and (width is None or length <= width)):
            return self._flat_format(config)
        return self._nested_format(width, config)

    @property
    def multiline(self) -> bool:
        return False

    def _flat_format(self, config: FormatterConfig) -> str:
        """Return a formatted list in one line."""
        open, close = self.parentheses
        return f"{open}{', '.join(obj._format(None, config) for obj in self._objs)}{close}"

    def _nested_format(self, width: None | int, config: FormatterConfig) -> str:
        """Return a formatted list in one line."""
        inner_width = None
        if width is not None:
            inner_width = width - config.indent - 1
        open, close = self.parentheses
        return (
            f"{open}\n"
            + textwrap.indent(
                "\n".join(f"{obj._format(inner_width, config)}," for obj in self._objs),
                prefix=" " * config.indent,
            )
            + f"\n{close}"
        )

    @property
    @abc.abstractmethod
    def parentheses(self) -> tuple[str, str]: ...


class ListFormat(SequenceFormat):
    @property
    def parentheses(self) -> tuple[str, str]:
        return "[", "]"


class SetFormat(SequenceFormat):
    @property
    def parentheses(self) -> tuple[str, str]:
        return "{", "}"


class ItemFormat(FormattedObj):
    def __init__(self, obj: Any) -> None:
        self.repr = repr(obj)

    def length(self) -> int | None:
        if self.multiline:
            return None
        return len(self.repr)

    def _format(self, width: None | int, config: FormatterConfig) -> str:
        return self.repr

    @property
    def multiline(self) -> bool:
        return "\n" in self.repr


@dataclass
class FormatterConfig:
    @staticmethod
    def _get_terminal_width() -> None | int:
        try:
            width, _ = os.get_terminal_size(sys.stderr.fileno())
        except OSError:
            return None
        else:
            return width

    indent: int = 2
    width: None | int = field(default_factory=_get_terminal_width)


class Formatter:
    def __init__(self, config: FormatterConfig) -> None:
        self._config = config

    def format(self, obj: Any) -> str:
        return str(self._formatted_object(obj)._format(self._config.width, self._config))

    def _formatted_object(self, obj: Any) -> FormattedObj:
        match obj:
            case list():
                objs = obj
                return ListFormat([self._formatted_object(obj) for obj in objs])
            case set():
                objs = obj
                return SetFormat([self._formatted_object(obj) for obj in objs])
            case _:
                return ItemFormat(obj)
