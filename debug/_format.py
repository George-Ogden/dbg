from __future__ import annotations

import abc
from collections import defaultdict
from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass, field
import os
import re
import sys
import textwrap
from typing import Any, Callable, ClassVar, Generic, Self, TypeVar
import unicodedata

from wcwidth import wcswidth

from ._code import highlight_code
from ._config import DbgConfig

ANSI_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return ANSI_PATTERN.sub("", text)


def not_first() -> Callable[..., bool]:
    _first_time_call = True

    def fn(*_) -> bool:
        nonlocal _first_time_call

        res = not _first_time_call
        _first_time_call = False
        return res

    return fn


class BaseFormat(abc.ABC):
    SEQUENCE_FORMATTERS: ClassVar[list[tuple[type[Any], type[SequenceFormat]]]]
    _length: int | None

    @abc.abstractmethod
    def length(self) -> int | None: ...

    @abc.abstractmethod
    def _format(self, used_width: int, highlight: bool, config: FormatterConfig) -> str: ...

    def _highlight_code(self, highlight: bool, text: str) -> str:
        if highlight and self._highlight:
            return highlight_code(text)
        return text

    @property
    @abc.abstractmethod
    def _highlight(self) -> bool: ...

    @classmethod
    def total_length(cls, objs: Iterable[BaseFormat]) -> int | None:
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

    @classmethod
    def clean_string(cls, string: str) -> str:
        return "".join(
            char
            for char in strip_ansi(string)
            if unicodedata.category(char)[0] != "C" and wcswidth(char) != -1
        )

    @classmethod
    def len(cls, string: str) -> int:
        return wcswidth(cls.clean_string(string))

    @classmethod
    def _from(cls, obj: Any, visited: set[int]) -> BaseFormat:
        if dataclasses.is_dataclass(obj):
            if (
                not isinstance(obj, type)
                and obj.__dataclass_params__.repr  # type: ignore
                and hasattr(obj.__repr__, "__wrapped__")
                and "__create_fn__" in obj.__repr__.__wrapped__.__qualname__
            ):
                visited.add(id(obj))
                dataclass_subformat = [
                    AttrFormat(field.name, cls._from(getattr(obj, field.name), visited))
                    for field in dataclasses.fields(obj)
                    if field.repr
                ]
                visited.remove(id(obj))
                return DataclassFormat(type(obj), RoundSequenceFormat(dataclass_subformat, None))
            else:
                return ItemFormat(obj)

        format: BaseFormat
        if isinstance(obj, defaultdict):
            visited.add(id(obj))
            defaultdict_subformat = RoundSequenceFormat(
                [cls._from(obj.default_factory, visited), cls._from(dict(obj.items()), visited)],
                None,
            )
            visited.remove(id(obj))
            return NamedObjectFormat(type(obj), defaultdict_subformat)

        obj_type: type[Any] | None
        if isinstance(obj, dict):
            if type(obj) is dict:
                obj_type = None
            else:
                obj_type = type(obj)
            if id(obj) in visited:
                return DictFormat(None, obj_type)
            visited.add(id(obj))
            items = None
            try:
                items = obj.most_common()  # type: ignore
            except (TypeError, AttributeError):
                ...
            if items is None:
                items = obj.items()
            format = DictFormat(
                [
                    PairFormat(
                        cls._from(k, visited),
                        cls._from(v, visited),
                    )
                    for k, v in items
                ],
                obj_type,
            )
            visited.remove(id(obj))
            return format

        for sequence_cls, formatter_cls in cls.SEQUENCE_FORMATTERS:
            if isinstance(obj, sequence_cls):
                if type(obj) is set and len(obj) == 0:
                    obj_type = set
                elif type(obj) is sequence_cls:
                    obj_type = None
                else:
                    obj_type = type(obj)
                if id(obj) in visited:
                    return formatter_cls(None, obj_type)
                visited.add(id(obj))
                objs = obj
                kwargs: dict[str, Any] = {}
                if type(obj) is tuple and len(obj) == 1:
                    kwargs |= dict(extra_trailing_comma=True)
                format = formatter_cls(
                    [cls._from(obj, visited) for obj in objs], obj_type, **kwargs
                )
                visited.remove(id(obj))
                return format
        return ItemFormat(obj)


SequenceFormatT = TypeVar("SequenceFormatT", bound=BaseFormat)


class SequenceFormat(BaseFormat, abc.ABC, Generic[SequenceFormatT]):
    def __init__(
        self,
        objs: list[SequenceFormatT] | None,
        type: None | type[Any],
        *,
        extra_trailing_comma: bool = False,
    ) -> None:
        self._objs = objs
        self._type = type
        if self._objs is None:
            self._length = 3 + self._paren_length
        else:
            self._length = self.add(BaseFormat.total_length(self._objs), self._paren_length)
            if len(self._objs) > 0:
                self._length = self.add(self._length, (len(self._objs) - 1) * 2)
        self._extra_trailing_comma = extra_trailing_comma
        if self._extra_trailing_comma:
            self._length = self.add(self._length, 1)

    def length(self) -> int | None:
        return self._length

    @property
    def _paren_length(self) -> int:
        open, close = self.parentheses
        return len(open) + len(close)

    def _format(self, used_width: int, highlight: bool, config: FormatterConfig) -> str:
        if self._objs is None:
            return self._empty_format(config)
        length = self.length()
        if len(self._objs) == 0 or (
            length is not None
            and (config._terminal_width is None or length <= config._terminal_width - used_width)
        ):
            return self._highlight_code(highlight, self._flat_format(self._objs, config))
        return self._highlight_code(highlight, self._nested_format(self._objs, used_width, config))

    @property
    def parentheses(self) -> tuple[str, str]:
        open, close = self._parentheses
        if self._type is not None:
            if self._objs is not None and len(self._objs) > 0:
                open = f"{self._type.__name__}({open}"
                close = f"{close})"
            else:
                open = f"{self._type.__name__}("
                close = ")"
        return open, close

    @property
    def multiline(self) -> bool:
        return False

    def _empty_format(self, config: FormatterConfig) -> str:
        """Return a formatted sequence that is recursive."""
        open, close = self.parentheses
        return open + "..." + close

    def _flat_format(self, objs: list[SequenceFormatT], config: FormatterConfig) -> str:
        """Return a formatted sequence in one line."""
        open, close = self.parentheses
        config = config.flatten()
        return (
            open
            + ", ".join(
                obj._format(len(open) + len(close), not self._highlight, config) for obj in objs
            )
            + ("," if self._extra_trailing_comma else "")
            + close
        )

    def _nested_format(
        self, objs: list[SequenceFormatT], used_width: int, config: FormatterConfig
    ) -> str:
        """Return a formatted sequence across multiple lines."""
        open, close = self.parentheses
        config = config.indent()
        return (
            f"{open}\n"
            + textwrap.indent(
                "\n".join(f"{obj._format(1, not self._highlight, config)}," for obj in objs),
                prefix=config.get_indent(),
            )
            + f"\n{close}"
        )

    @property
    @abc.abstractmethod
    def _parentheses(self) -> tuple[str, str]: ...

    @property
    def _highlight(self) -> bool:
        if self._objs is None:
            return True
        return all(obj._highlight for obj in self._objs)


SquareSequenceFormatT = TypeVar("SquareSequenceFormatT", bound=BaseFormat)


class SquareSequenceFormat(SequenceFormat[SquareSequenceFormatT]):
    @property
    def _parentheses(self) -> tuple[str, str]:
        return "[", "]"


CurlySequenceFormatT = TypeVar("CurlySequenceFormatT", bound=BaseFormat)


class CurlySequenceFormat(SequenceFormat[CurlySequenceFormatT]):
    @property
    def _parentheses(self) -> tuple[str, str]:
        return "{", "}"


RoundSequenceFormatT = TypeVar("RoundSequenceFormatT", bound=BaseFormat)


class RoundSequenceFormat(SequenceFormat[RoundSequenceFormatT]):
    @property
    def _parentheses(self) -> tuple[str, str]:
        return "(", ")"


class NamedObjectFormat(BaseFormat):
    def __init__(self, type: type[Any], subformat: BaseFormat) -> None:
        self._name = type.__name__
        self._subformat = subformat

    def length(self) -> int | None:
        return self.add(len(self._name), self._subformat.length())

    def _format(self, used_width: int, highlight: bool, config: FormatterConfig) -> str:
        return self._name + self._subformat._format(used_width + len(self._name), highlight, config)

    @property
    def _highlight(self) -> bool:
        return self._subformat._highlight


class PairFormat(BaseFormat):
    def __init__(self, key: BaseFormat, value: BaseFormat) -> None:
        self._key = key
        self._value = value
        self._length = self.add(self.add(self._key.length(), self._value.length()), 2)

    def _format(self, used_width: int, highlight: bool, config: FormatterConfig) -> str:
        key_format = self._key._format(1, not self._highlight, config) + ":"
        indent_width = 1 + len(key_format.splitlines()[-1])
        config = FormatterConfig(
            config._indent_width,
            self.add(config._terminal_width, -indent_width),
        )
        value_format = " " + self._value._format(1, not self._highlight, config)
        if isinstance(self._value, ItemFormat) and self._value.length() is None:
            value_format = textwrap.indent(
                value_format, prefix=" " * indent_width, predicate=not_first()
            )
        return self._highlight_code(highlight, key_format + value_format)

    def length(self) -> int | None:
        return self._length

    @property
    def _highlight(self) -> bool:
        return self._key._highlight and self._value._highlight


DictFormatT = TypeVar("DictFormatT", bound=PairFormat)


class DictFormat(CurlySequenceFormat[PairFormat]): ...


class AttrFormat(BaseFormat):
    def __init__(self, attr: str, value: BaseFormat) -> None:
        self._attr = attr
        self._value = value
        self._length = self.add(1 + len(self._attr), self._value.length())

    def _format(self, used_width: int, highlight: bool, config: FormatterConfig) -> str:
        attr_format = self._attr + "="
        indent_width = len(attr_format)
        config = FormatterConfig(
            config._indent_width,
            self.add(config._terminal_width, -indent_width),
        )
        value_format = self._value._format(1, not self._highlight, config)
        if isinstance(self._value, ItemFormat) and self._value.length() is None:
            value_format = textwrap.indent(
                value_format, prefix=" " * indent_width, predicate=not_first()
            )
        return self._highlight_code(highlight, attr_format + value_format)

    def length(self) -> int | None:
        return self._length

    @property
    def _highlight(self) -> bool:
        return self._value._highlight


class DataclassFormat(NamedObjectFormat): ...


class ItemFormat(BaseFormat):
    def __init__(self, obj: Any) -> None:
        self.repr = repr(obj)

    def length(self) -> int | None:
        if self.multiline:
            return None
        return self.len(self.repr)

    def _format(self, used_width: int, highlight: bool, config: FormatterConfig) -> str:
        return self._highlight_code(highlight, self.repr)

    @property
    def multiline(self) -> bool:
        return "\n" in self.repr

    @property
    def _highlight(self) -> bool:
        return strip_ansi(self.repr) == self.repr


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
            _terminal_width=BaseFormat.add(self._terminal_width, -self._indent_width),
        )

    def flatten(self) -> Self:
        return type(self)(_indent_width=self._indent_width, _terminal_width=None)

    def get_indent(self) -> str:
        return " " * self._indent_width

    @classmethod
    def _from_config(cls, config: DbgConfig) -> Self:
        return cls(_indent_width=config.indent)


BaseFormat.SEQUENCE_FORMATTERS = [
    (list, SquareSequenceFormat),
    (set, CurlySequenceFormat),
    (tuple, RoundSequenceFormat),
]


class Formatter:
    def __init__(self, config: FormatterConfig) -> None:
        self._config = config

    def format(self, obj: Any, *, initial_width: int) -> str:
        formatted_obj = BaseFormat._from(obj, set())
        text = formatted_obj._format(initial_width, highlight=True, config=self._config)
        terminal_width = self._config._terminal_width
        if isinstance(formatted_obj, ItemFormat):
            max_len = max(map(BaseFormat.len, text.splitlines()))
            if terminal_width is not None and max_len + initial_width > terminal_width:
                text = "\n" + text
                if initial_width + 1 <= terminal_width:
                    text = "\u23ce" + text
            else:
                text = textwrap.indent(text, " " * initial_width, predicate=not_first())
        return text
