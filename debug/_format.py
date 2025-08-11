from __future__ import annotations

import abc
from collections.abc import Iterable
from dataclasses import dataclass, field
import os
import sys
import textwrap
from typing import Any, Callable, ClassVar, Self


def not_first() -> Callable[..., bool]:
    _first_time_call = True

    def fn(*_) -> bool:
        nonlocal _first_time_call

        res = not _first_time_call
        _first_time_call = False
        return res

    return fn


class ObjFormat(abc.ABC):
    @abc.abstractmethod
    def length(self) -> int | None: ...

    @abc.abstractmethod
    def _format(self, used_width: int, config: FormatterConfig) -> str: ...

    @classmethod
    def total_length(cls, objs: Iterable[ObjFormat]) -> int | None:
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


class SequenceFormat(ObjFormat, abc.ABC):
    def __init__(self, objs: list[ObjFormat] | None) -> None:
        self._objs = objs
        if self._objs is None:
            self._length = 5
        else:
            self._length = self.add(ObjFormat.total_length(self._objs), 2)
            if len(self._objs) > 0:
                self._length = self.add(self._length, (len(self._objs) - 1) * 2)

    def length(self) -> int | None:
        return self._length

    def _format(self, used_width: int, config: FormatterConfig) -> str:
        if self._objs is None:
            return self._empty_format(config)
        length = self.length()
        if len(self._objs) == 0 or (
            length is not None
            and (config._terminal_width is None or length <= config._terminal_width - used_width)
        ):
            return self._flat_format(self._objs, config)
        return self._nested_format(self._objs, used_width, config)

    @property
    def multiline(self) -> bool:
        return False

    def _empty_format(self, config: FormatterConfig) -> str:
        """Return a formatted sequence that is recursive."""
        open, close = self.parentheses
        return open + "..." + close

    def _flat_format(self, objs: list[ObjFormat], config: FormatterConfig) -> str:
        """Return a formatted sequence in one line."""
        open, close = self.parentheses
        config = config.flatten()
        return open + ", ".join(obj._format(len(open) + len(close), config) for obj in objs) + close

    def _nested_format(
        self, objs: list[ObjFormat], used_width: int, config: FormatterConfig
    ) -> str:
        """Return a formatted sequence across multiple lines."""
        open, close = self.parentheses
        config = config.indent()
        return (
            f"{open}\n"
            + textwrap.indent(
                "\n".join(f"{obj._format(1, config)}," for obj in objs),
                prefix=config.get_indent(),
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


class TupleFormat(SequenceFormat):
    def __init__(self, objs: list[ObjFormat]) -> None:
        super().__init__(objs)
        if self._objs is not None and len(self._objs) == 1:
            self._length = self.add(self._length, 1)

    @property
    def parentheses(self) -> tuple[str, str]:
        return "(", ")"

    def _flat_format(self, objs: list[ObjFormat], config: FormatterConfig) -> str:
        if len(objs) == 1:
            open, close = self.parentheses
            [obj] = objs
            return f"{open}{obj._format(1 + len(open) + len(close), config)},{close}"
        return super()._flat_format(objs, config)


class PairFormat(ObjFormat):
    def __init__(self, key: ObjFormat, value: ObjFormat) -> None:
        self._key = key
        self._value = value
        self._length = self.add(self.add(self._key.length(), self._value.length()), 2)

    def _format(self, used_width: int, config: FormatterConfig) -> str:
        key_format = self._key._format(1, config) + ":"
        indent_width = 1 + len(key_format.splitlines()[-1])
        config = FormatterConfig(
            config._indent_width,
            self.add(config._terminal_width, -indent_width),
        )
        value_format = " " + self._value._format(1, config)
        if isinstance(self._value, ItemFormat) and self._value.length() is None:
            value_format = textwrap.indent(
                value_format, prefix=" " * indent_width, predicate=not_first()
            )
        return key_format + value_format

    def length(self) -> int | None:
        return self._length


class DictFormat(SequenceFormat):
    @property
    def parentheses(self) -> tuple[str, str]:
        return "{", "}"


class ItemFormat(ObjFormat):
    def __init__(self, obj: Any) -> None:
        self.repr = repr(obj)

    def length(self) -> int | None:
        if self.multiline:
            return None
        return len(self.repr)

    def _format(self, used_width: int, config: FormatterConfig) -> str:
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

    _indent_width: int = 2
    _terminal_width: None | int = field(default_factory=_get_terminal_width)

    def indent(self) -> Self:
        return type(self)(
            _indent_width=self._indent_width,
            _terminal_width=ObjFormat.add(self._terminal_width, -self._indent_width),
        )

    def flatten(self) -> Self:
        return type(self)(_indent_width=self._indent_width, _terminal_width=None)

    def get_indent(self) -> str:
        return " " * self._indent_width


class Formatter:
    SEQUENCE_FORMATTERS: ClassVar[list[tuple[type[Any], type[SequenceFormat]]]] = [
        (list, ListFormat),
        (set, SetFormat),
        (tuple, TupleFormat),
    ]

    def __init__(self, config: FormatterConfig) -> None:
        self._config = config

    def format(self, obj: Any) -> str:
        return str(self._formatted_object(obj, set())._format(0, self._config))

    def _formatted_object(self, obj: Any, visited: set[int]) -> ObjFormat:
        if isinstance(obj, dict):
            if id(obj) in visited:
                return DictFormat(None)
            visited.add(id(obj))
            return DictFormat(
                [
                    PairFormat(
                        self._formatted_object(k, visited), self._formatted_object(v, visited)
                    )
                    for k, v in obj.items()
                ]
            )

        for sequence_cls, formatter_cls in self.SEQUENCE_FORMATTERS:
            if isinstance(obj, sequence_cls):
                if id(obj) in visited:
                    return formatter_cls(None)
                visited.add(id(obj))
                objs = obj
                return formatter_cls([self._formatted_object(obj, visited) for obj in objs])
        return ItemFormat(obj)
