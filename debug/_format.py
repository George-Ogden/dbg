from __future__ import annotations

import abc
from array import array
from collections import Counter, UserDict, UserList, defaultdict
from collections.abc import Collection, ItemsView, Iterable, KeysView, ValuesView
import dataclasses
from dataclasses import dataclass, field
import os
import re
import sys
import textwrap
from types import MethodWrapperType
from typing import (
    Any,
    Callable,
    ClassVar,
    Generic,
    Protocol,
    Self,
    TypeAlias,
    TypeVar,
)
import unicodedata

from wcwidth import wcswidth

from ._code import highlight_code
from ._config import DbgConfig

frozendict: type[Any]
try:
    from frozendict import frozendict
except (ModuleNotFoundError, ImportError):
    frozendict = type("", (), {})

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


Visited: TypeAlias = set[int]


class BaseFormat(abc.ABC):
    SEQUENCE_MAKERS: ClassVar[list[SequenceMaker]]
    KNOWN_WRAPPED_CLASSES: ClassVar[tuple[type[Any], ...]]
    KNOWN_EXTRA_CLASSES: ClassVar[tuple[type[Any], ...]]
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
    def _from(cls, obj: Any, visited: Visited) -> BaseFormat:
        if dataclasses.is_dataclass(obj):
            if (
                not isinstance(obj, type)
                and obj.__dataclass_params__.repr  # type: ignore
                and hasattr(obj.__repr__, "__wrapped__")
                and "__create_fn__" in obj.__repr__.__wrapped__.__qualname__
            ):
                visited.add(id(obj))
                dataclass_subformat: list[BaseFormat] = [
                    AttrFormat(field.name, cls._from(getattr(obj, field.name), visited))
                    for field in dataclasses.fields(obj)
                    if field.repr
                ]
                visited.remove(id(obj))
                return DataclassFormat(type(obj), RoundSequenceFormat(dataclass_subformat, None))
            else:
                return ItemFormat(obj)

        if (
            isinstance(obj, cls.KNOWN_WRAPPED_CLASSES)
            and not isinstance(obj, cls.KNOWN_EXTRA_CLASSES)
            and type(obj.__repr__) is not MethodWrapperType
        ):
            return ItemFormat(obj)

        for extra_cls in cls.KNOWN_EXTRA_CLASSES:
            if isinstance(obj, extra_cls) and obj.__repr__.__code__ != extra_cls.__repr__.__code__:
                return ItemFormat(obj)

        for sequence_maker in cls.SEQUENCE_MAKERS:
            if isinstance(obj, sequence_maker.base_cls):
                return sequence_maker.formatter(obj, visited=visited)

        if isinstance(obj, array):
            body: Any
            try:
                string = obj.tounicode()
            except ValueError:
                body = obj.tolist()
            else:
                body = string
            sub_objs = [obj.typecode]
            if body:
                sub_objs.append(body)
            array_subformat = RoundSequenceFormat(
                [cls._from(sub_obj, visited) for sub_obj in sub_objs], None
            )
            return NamedObjectFormat(type(obj), array_subformat)

        return ItemFormat(obj)


class SequenceFormat(BaseFormat, abc.ABC):
    def __init__(
        self,
        objs: list[BaseFormat] | None,
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
            open = f"{self._type.__name__}({open}"
            close = f"{close})"
        return open, close

    @property
    def multiline(self) -> bool:
        return False

    def _empty_format(self, config: FormatterConfig) -> str:
        """Return a formatted sequence that is recursive."""
        open, close = self.parentheses
        return open + "..." + close

    def _flat_format(self, objs: list[BaseFormat], config: FormatterConfig) -> str:
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
        self, objs: list[BaseFormat], used_width: int, config: FormatterConfig
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


class SquareSequenceFormat(SequenceFormat):
    @property
    def _parentheses(self) -> tuple[str, str]:
        return "[", "]"


class CurlySequenceFormat(SequenceFormat):
    @property
    def _parentheses(self) -> tuple[str, str]:
        return "{", "}"


class RoundSequenceFormat(SequenceFormat):
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


class SequenceCallable(Protocol):
    def __call__(
        self, sub_objs: None | list[BaseFormat], display_type: type | None, **kwargs: Any
    ) -> BaseFormat: ...


SequenceInit: TypeAlias = SequenceCallable | type[SequenceFormat]
SequenceMakerT = TypeVar("SequenceMakerT", bound=Collection)


class SequenceMaker(Generic[SequenceMakerT]):
    def __init__(
        self,
        *,
        include_name: bool,
        base_cls: type[SequenceMakerT],
        sequence_cls: type[SequenceFormat],
        show_braces_when_empty: bool,
    ) -> None:
        self._include_name = include_name
        self.base_cls = base_cls
        self._sequence_cls = sequence_cls
        self._show_braces_when_empty = show_braces_when_empty

    def formatter(self, obj: SequenceMakerT, visited: Visited, **kwargs: Any) -> BaseFormat:
        display_type = self.use_type(obj)
        if len(obj) == 0:
            empty_formatter = self.format_empty(display_type)
            if empty_formatter is not None:
                return empty_formatter
        if id(obj) in visited:
            sub_objs = None
        else:
            visited.add(id(obj))
            sub_objs = self.format_sub_objs(obj, visited)
            visited.remove(id(obj))
        return self.sequence_init(obj)(sub_objs, display_type, **kwargs)

    def sequence_init(self, obj: SequenceMakerT) -> SequenceInit:
        return self._sequence_cls

    def format_empty(self, display_type: type | None) -> BaseFormat | None:
        if self._show_braces_when_empty or display_type is None:
            return None
        return NamedObjectFormat(display_type, RoundSequenceFormat([], None))

    def format_sub_objs(self, sub_objs: SequenceMakerT, visited: Visited) -> list[BaseFormat]:
        return [BaseFormat._from(sub_obj, visited) for sub_obj in sub_objs]

    def use_type(self, obj: SequenceMakerT) -> None | type:
        obj_type = type(obj)
        if not self._include_name and obj_type is self.base_cls:
            return None
        return obj_type


class SetMaker(SequenceMaker[set]):
    def format_empty(self, display_type: type | None) -> BaseFormat | None:
        return NamedObjectFormat(display_type or self.base_cls, RoundSequenceFormat([], None))


class TupleMaker(SequenceMaker[tuple]):
    def formatter(self, obj: tuple, visited: Visited, **kwargs: Any) -> BaseFormat:
        if len(obj) == 1:
            kwargs = kwargs | dict(extra_trailing_comma=True)
        return super().formatter(obj, visited, **kwargs)


DictMakerT = TypeVar("DictMakerT", bound=dict)


class DictMaker(Generic[DictMakerT], SequenceMaker[DictMakerT]):
    def format_sub_objs(self, sub_objs: DictMakerT, visited: Visited) -> list[BaseFormat]:
        items = sub_objs.items()
        return [
            PairFormat(
                BaseFormat._from(k, visited),
                BaseFormat._from(v, visited),
            )
            for k, v in items
        ]


class CounterMaker(DictMaker[Counter]):
    def format_sub_objs(self, sub_objs: Counter, visited: Visited) -> list[BaseFormat]:
        try:
            items = list(sub_objs.most_common())
        except (AttributeError, TypeError):
            items = list(sub_objs.items())
        return super().format_sub_objs(dict(items), visited)  # type: ignore


class DefaultDictMaker(DictMaker[defaultdict]):
    def sequence_init(self, obj: defaultdict) -> SequenceInit:
        def construct_default_dict(
            sub_objs: None | list[BaseFormat], display_type: type | None, **kwargs: Any
        ) -> BaseFormat:
            assert display_type is not None
            return NamedObjectFormat(
                display_type,
                RoundSequenceFormat(
                    [ItemFormat(obj.default_factory), self._sequence_cls(sub_objs, None)],
                    None,
                    **kwargs,
                ),
            )

        return construct_default_dict


BaseFormat.SEQUENCE_MAKERS = [
    SequenceMaker(
        include_name=False,
        base_cls=list,
        sequence_cls=SquareSequenceFormat,
        show_braces_when_empty=False,
    ),
    SetMaker(
        include_name=False,
        base_cls=set,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    TupleMaker(
        include_name=False,
        base_cls=tuple,
        sequence_cls=RoundSequenceFormat,
        show_braces_when_empty=False,
    ),
    CounterMaker(
        include_name=True,
        base_cls=Counter,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    DefaultDictMaker(
        include_name=True,
        base_cls=defaultdict,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=True,
    ),
    DictMaker(
        include_name=True,
        base_cls=frozendict,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=True,
    ),
    DictMaker(
        include_name=False,
        base_cls=dict,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    SequenceMaker(
        include_name=True,
        base_cls=frozenset,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    SequenceMaker(
        include_name=True,
        base_cls=KeysView,
        sequence_cls=SquareSequenceFormat,
        show_braces_when_empty=True,
    ),
    SequenceMaker(
        include_name=True,
        base_cls=ValuesView,
        sequence_cls=SquareSequenceFormat,
        show_braces_when_empty=True,
    ),
    SequenceMaker(
        include_name=True,
        base_cls=ItemsView,
        sequence_cls=SquareSequenceFormat,
        show_braces_when_empty=True,
    ),
    SequenceMaker(
        include_name=True,
        base_cls=UserList,
        sequence_cls=SquareSequenceFormat,
        show_braces_when_empty=True,
    ),
    DictMaker(
        include_name=True,
        base_cls=UserDict,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=True,
    ),
]

BaseFormat.KNOWN_WRAPPED_CLASSES = (
    list,
    set,
    tuple,
    dict,
    defaultdict,
    frozenset,
    array,
    KeysView,
    ValuesView,
    ItemsView,
)

BaseFormat.KNOWN_EXTRA_CLASSES = (Counter, frozendict)


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


class Formatter:
    def __init__(self, config: FormatterConfig) -> None:
        self._config = config

    def format(self, obj: Any, *, initial_width: int) -> str:
        formatted_obj = BaseFormat._from(obj, set())
        text = formatted_obj._format(initial_width, highlight=True, config=self._config)
        terminal_width = self._config._terminal_width
        if isinstance(formatted_obj, ItemFormat) and text:
            max_len = max(map(BaseFormat.len, text.splitlines()))
            if terminal_width is not None and max_len + initial_width > terminal_width:
                text = "\n" + text
                if initial_width + 1 <= terminal_width:
                    text = "\u23ce" + text
            else:
                text = textwrap.indent(text, " " * initial_width, predicate=not_first())
        return text
