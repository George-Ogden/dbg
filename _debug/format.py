from __future__ import annotations

import abc
from array import array
import ast
from collections import ChainMap, Counter, OrderedDict, UserDict, UserList, defaultdict, deque
from collections.abc import (
    Callable,
    Collection,
    ItemsView,
    Iterable,
    KeysView,
    Sequence,
    ValuesView,
)
import dataclasses
from dataclasses import dataclass
import functools
import re
import sys
import textwrap
from types import MethodWrapperType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    Protocol,
    Self,
    TypeAlias,
    TypeVar,
)
import unicodedata
import warnings

from wcwidth import wcswidth

from . import defaults as defaults
from .code import highlight_code, validate_style
from .config import CONFIG
from .file import FileWrapper

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

frozendict: type[Any]
try:
    from frozendict import frozendict
except (ModuleNotFoundError, ImportError):
    frozendict = type("", (), {})

BidictBase: type[Any]
try:
    from bidict import BidictBase
except (ModuleNotFoundError, ImportError):
    BidictBase = type("", (), {})

try:
    import numpy as np
except (ModuleNotFoundError, ImportError):
    from . import _numpy_backup as np  # type: ignore

ANSI_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return ANSI_PATTERN.sub("", text)


def not_first() -> Callable[..., bool]:
    _first_time_call = True

    def fn(*_: Any) -> bool:
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
    def _format(self, highlight_now: bool, config: FormatterConfig) -> str: ...

    def _highlight_code(self, style: str | None, text: str) -> str:
        if style is not None and self._highlight_subitems:
            return highlight_code(text, style)
        return text

    @property
    @abc.abstractmethod
    def _highlight_subitems(self) -> bool: ...

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
    def _from(cls, obj: Any, visited: Visited, *, sort_unordered_collections: bool) -> BaseFormat:
        obj_cls = type(obj)
        if dataclasses.is_dataclass(obj):
            if (
                not isinstance(obj, type)
                and obj.__dataclass_params__.repr  # type: ignore
                and hasattr(obj.__repr__, "__wrapped__")
                and "__create_fn__" in obj.__repr__.__wrapped__.__qualname__
            ):
                if id(obj) in visited:
                    return NamedObjectFormat(obj_cls, None)
                visited.add(id(obj))
                dataclass_format = NamedObjectFormat(
                    obj_cls,
                    [
                        AttrFormat(
                            field.name,
                            cls._from(
                                getattr(obj, field.name),
                                visited,
                                sort_unordered_collections=sort_unordered_collections,
                            ),
                        )
                        for field in dataclasses.fields(obj)
                        if field.repr
                    ],
                )
                visited.remove(id(obj))
                return dataclass_format
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
                return sequence_maker.formatter(
                    obj, visited=visited, sort_unordered_collections=sort_unordered_collections
                )

        if isinstance(obj, np.ndarray):
            data = obj.tolist()
            dtype = obj.dtype
            if type(obj) is np.ndarray:
                obj_cls = array
            if id(obj) in visited:
                return NamedObjectFormat(
                    obj_cls,
                    [
                        EllipsisFormat(),
                        AttrFormat(
                            "dtype",
                            cls._from(
                                dtype.name,
                                visited,
                                sort_unordered_collections=sort_unordered_collections,
                            ),
                        ),
                    ],
                )
            visited.add(id(obj))
            np_array_format = NamedObjectFormat(
                obj_cls,
                [
                    cls._from(data, visited, sort_unordered_collections=sort_unordered_collections),
                    AttrFormat(
                        "dtype",
                        cls._from(
                            dtype.name,
                            visited,
                            sort_unordered_collections=sort_unordered_collections,
                        ),
                    ),
                ],
            )
            visited.remove(id(obj))
            return np_array_format

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
            return NamedObjectFormat(
                obj_cls,
                [
                    cls._from(
                        sub_obj, visited, sort_unordered_collections=sort_unordered_collections
                    )
                    for sub_obj in sub_objs
                ],
            )

        if isinstance(obj, ast.AST):
            if id(obj) in visited:
                return NamedObjectFormat(obj_cls, None)
            visited.add(id(obj))
            ast_subformat: list[BaseFormat] = []
            if hasattr(obj_cls, "_field_types"):
                for field in obj._fields:
                    try:
                        value = getattr(obj, field)
                    except AttributeError:
                        continue
                    if value is None and getattr(obj_cls, field, ...) is None:
                        continue
                    if value == []:
                        field_type = obj_cls._field_types.get(field, object)
                        if getattr(field_type, "__origin__", ...) is list:
                            continue
                    elif isinstance(value, ast.Load):
                        field_type = obj_cls._field_types.get(field, object)
                        if field_type is ast.expr_context:
                            continue
                    ast_subformat.append(
                        AttrFormat(
                            field,
                            cls._from(
                                value,
                                visited,
                                sort_unordered_collections=sort_unordered_collections,
                            ),
                        )
                    )
            else:
                ast_subformat = [
                    AttrFormat(
                        field,
                        cls._from(
                            getattr(obj, field),
                            visited,
                            sort_unordered_collections=sort_unordered_collections,
                        ),
                    )
                    for field in obj._fields
                    if getattr(obj, field, None) not in (None, [])
                    or (isinstance(obj, ast.Constant | ast.MatchSingleton) and field == "value")
                ]

            ast_format = NamedObjectFormat(
                obj_cls,
                ast_subformat,
            )
            visited.remove(id(obj))
            return ast_format

        if isinstance(obj, ChainMap):
            if id(obj) in visited:
                return NamedObjectFormat(obj_cls, None)
            visited.add(id(obj))
            chainmap_subformat = NamedObjectFormat(
                obj_cls,
                [
                    cls._from(map, visited, sort_unordered_collections=sort_unordered_collections)
                    for map in obj.maps
                ],
            )
            visited.remove(id(obj))
            return chainmap_subformat

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

    def _format(self, highlight_now: bool, config: FormatterConfig) -> str:
        if self._objs is None:
            return self._empty_format(config)
        length = self.length()
        if len(self._objs) == 0 or (
            length is not None
            and (config.remaining_width is None or length <= config.remaining_width)
        ):
            return self._highlight_code(
                config.get_style(highlight_now), self._flat_format(self._objs, config)
            )
        return self._highlight_code(
            config.get_style(highlight_now), self._nested_format(self._objs, config)
        )

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
            + ", ".join(obj._format(not self._highlight_subitems, config) for obj in objs)
            + ("," if self._extra_trailing_comma else "")
            + close
        )

    def _nested_format(self, objs: list[BaseFormat], config: FormatterConfig) -> str:
        """Return a formatted sequence across multiple lines."""
        open, close = self.parentheses
        config = config.indent()
        return (
            f"{open}\n"
            + textwrap.indent(
                "\n".join(
                    f"{obj._format(not self._highlight_subitems, config.use_only(1))},"
                    for obj in objs
                ),
                prefix=config.get_indent(),
            )
            + f"\n{close}"
        )

    @property
    @abc.abstractmethod
    def _parentheses(self) -> tuple[str, str]: ...

    @functools.cached_property
    def _highlight_subitems(self) -> bool:
        if self._objs is None:
            return True
        return all(obj._highlight_subitems for obj in self._objs)


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


class NamedObjectFormat(RoundSequenceFormat):
    def __init__(
        self,
        type: type[Any],
        objs: list[BaseFormat] | None,
    ) -> None:
        self._name = type.__name__
        super().__init__(objs, None)

    @property
    def _parentheses(self) -> tuple[str, str]:
        open, close = super()._parentheses
        return f"{self._name}{open}", close


class PairFormat(BaseFormat):
    def __init__(self, key: BaseFormat, value: BaseFormat) -> None:
        self._key = key
        self._value = value
        self._length = self.add(self.add(self._key.length(), self._value.length()), 2)

    def _format(self, highlight: bool, config: FormatterConfig) -> str:
        key_format = self._key._format(not self._highlight_subitems, config.use_only(1)) + ":"
        lines = key_format.splitlines()
        offset_width = self.len(lines[-1]) + 1
        value_format = " " + self._value._format(
            not self._highlight_subitems, config.use_extra(offset_width)
        )
        if isinstance(self._value, ItemFormat) and self._value.length() is None:
            value_format = textwrap.indent(
                value_format, prefix=" " * offset_width, predicate=not_first()
            )
        return self._highlight_code(config.get_style(highlight), key_format + value_format)

    def length(self) -> int | None:
        return self._length

    @functools.cached_property
    def _highlight_subitems(self) -> bool:
        return self._key._highlight_subitems and self._value._highlight_subitems


class AttrFormat(BaseFormat):
    def __init__(self, attr: str, value: BaseFormat) -> None:
        self._attr = attr
        self._value = value
        self._length = self.add(1 + len(self._attr), self._value.length())

    def _format(self, highlight: bool, config: FormatterConfig) -> str:
        attr_format = self._attr + "="
        value_format = self._value._format(
            not self._highlight_subitems, config.use_extra(len(attr_format))
        )
        if isinstance(self._value, ItemFormat) and self._value.length() is None:
            value_format = textwrap.indent(
                value_format, prefix=" " * len(attr_format), predicate=not_first()
            )
        return self._highlight_code(config.get_style(highlight), attr_format + value_format)

    def length(self) -> int | None:
        return self._length

    @functools.cached_property
    def _highlight_subitems(self) -> bool:
        return self._value._highlight_subitems


class ItemFormat(BaseFormat):
    def __init__(self, obj: Any) -> None:
        self.repr = repr(obj)

    def length(self) -> int | None:
        if self.multiline:
            return None
        return self.len(self.repr)

    def _format(self, highlight_now: bool, config: FormatterConfig) -> str:
        return self._highlight_code(config.get_style(highlight_now), self.repr)

    @property
    def multiline(self) -> bool:
        return "\n" in self.repr

    @functools.cached_property
    def _highlight_subitems(self) -> bool:
        return strip_ansi(self.repr) == self.repr


class EllipsisFormat(ItemFormat):
    def __init__(self) -> None:
        self.repr = "..."


class SequenceCallable(Protocol):
    def __call__(
        self, sub_objs: None | list[BaseFormat], display_type: type | None, **kwargs: Any
    ) -> BaseFormat: ...


SequenceInit: TypeAlias = SequenceCallable | type[SequenceFormat]
SequenceMakerT = TypeVar("SequenceMakerT", bound=Collection)


class SafeSortItem:
    def __init__(self, obj: Any, /) -> None:
        self._obj = obj

    def __lt__(self, other: Self) -> bool:
        try:
            return self._obj < other._obj
        except TypeError:
            return (str(type(self._obj)), id(self._obj)) < (str(type(other._obj)), id(other._obj))


def SafeSortTuple(objs: Sequence[Any], /) -> tuple[SafeSortItem, ...]:
    return tuple(SafeSortItem(obj) for obj in objs)


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

    def formatter(
        self,
        obj: SequenceMakerT,
        visited: Visited,
        *,
        sort_unordered_collections: bool,
        **kwargs: Any,
    ) -> BaseFormat:
        display_type = self.use_type(obj)
        if len(obj) == 0:
            empty_formatter = self.format_empty(display_type)
            if empty_formatter is not None:
                return empty_formatter
        if id(obj) in visited:
            sub_objs = None
        else:
            visited.add(id(obj))
            sub_objs = self.format_sub_objs(
                obj, visited, sort_unordered_collections=sort_unordered_collections
            )
            visited.remove(id(obj))
        return self.sequence_init(obj)(sub_objs, display_type, **kwargs)

    def sequence_init(self, obj: SequenceMakerT) -> SequenceInit:
        return self._sequence_cls

    def format_empty(self, display_type: type | None) -> BaseFormat | None:
        if self._show_braces_when_empty or display_type is None:
            return None
        return NamedObjectFormat(display_type, [])

    def format_sub_objs(
        self, sub_objs: SequenceMakerT, visited: Visited, *, sort_unordered_collections: bool
    ) -> list[BaseFormat]:
        return [
            BaseFormat._from(
                sub_obj, visited, sort_unordered_collections=sort_unordered_collections
            )
            for sub_obj in sub_objs
        ]

    def use_type(self, obj: SequenceMakerT) -> None | type:
        obj_type = type(obj)
        if not self._include_name and obj_type is self.base_cls:
            return None
        return obj_type


USequenceMakerT = TypeVar("USequenceMakerT", bound=Collection)


class UnorderedSequenceMaker(Generic[USequenceMakerT], SequenceMaker[USequenceMakerT]):
    def format_sub_objs(
        self, sub_objs: USequenceMakerT, visited: Visited, *, sort_unordered_collections: bool
    ) -> list[BaseFormat]:
        if sort_unordered_collections:
            sub_objs = sorted(sub_objs, key=SafeSortItem)  # type: ignore
        return super().format_sub_objs(
            sub_objs, visited, sort_unordered_collections=sort_unordered_collections
        )


class SetMaker(UnorderedSequenceMaker[set]):
    def format_empty(self, display_type: type | None) -> BaseFormat | None:
        return NamedObjectFormat(display_type or self.base_cls, [])


class TupleMaker(SequenceMaker[tuple]):
    def formatter(
        self, obj: tuple, visited: Visited, *, sort_unordered_collections: bool, **kwargs: Any
    ) -> BaseFormat:
        if len(obj) == 1:
            kwargs = kwargs | dict(extra_trailing_comma=True)
        return super().formatter(
            obj, visited, sort_unordered_collections=sort_unordered_collections, **kwargs
        )


ODictMakerT = TypeVar("ODictMakerT", bound=dict)


class OrderedDictMaker(Generic[ODictMakerT], SequenceMaker[ODictMakerT]):
    def format_sub_objs(
        self, sub_objs: ODictMakerT, visited: Visited, *, sort_unordered_collections: bool
    ) -> list[BaseFormat]:
        return [
            PairFormat(
                BaseFormat._from(k, visited, sort_unordered_collections=sort_unordered_collections),
                BaseFormat._from(v, visited, sort_unordered_collections=sort_unordered_collections),
            )
            for k, v in sub_objs.items()
        ]


DictMakerT = TypeVar("DictMakerT", bound=dict)


class DictMaker(Generic[DictMakerT], OrderedDictMaker[DictMakerT]):
    def format_sub_objs(
        self, sub_objs: DictMakerT, visited: Visited, *, sort_unordered_collections: bool
    ) -> list[BaseFormat]:
        items: Iterable[tuple[Any, Any]]
        items = sub_objs.items()
        if sort_unordered_collections:
            items = sorted(items, key=SafeSortTuple)
        return super().format_sub_objs(
            dict(items),  # type: ignore
            visited,
            sort_unordered_collections=sort_unordered_collections,
        )


class CounterMaker(OrderedDictMaker[Counter]):
    def format_sub_objs(
        self, sub_objs: Counter, visited: Visited, *, sort_unordered_collections: bool
    ) -> list[BaseFormat]:
        items: Iterable[tuple[Any, Any]]
        try:
            items = sub_objs.most_common()
        except (AttributeError, TypeError):
            items = sub_objs.items()
        return super().format_sub_objs(
            dict(items),  # type: ignore
            visited,
            sort_unordered_collections=sort_unordered_collections,
        )


class DefaultDictMaker(DictMaker[defaultdict]):
    def sequence_init(self, obj: defaultdict) -> SequenceInit:
        def construct_default_dict(
            sub_objs: None | list[BaseFormat], display_type: type | None, **kwargs: Any
        ) -> BaseFormat:
            assert display_type is not None
            return NamedObjectFormat(
                display_type,
                [ItemFormat(obj.default_factory), self._sequence_cls(sub_objs, None)],
                **kwargs,
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
    OrderedDictMaker(
        include_name=True,
        base_cls=OrderedDict,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    DictMaker(
        include_name=True,
        base_cls=frozendict,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=True,
    ),
    DictMaker(
        include_name=True,
        base_cls=BidictBase,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    DictMaker(
        include_name=False,
        base_cls=dict,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    UnorderedSequenceMaker(
        include_name=True,
        base_cls=frozenset,
        sequence_cls=CurlySequenceFormat,
        show_braces_when_empty=False,
    ),
    UnorderedSequenceMaker(
        include_name=True,
        base_cls=KeysView,
        sequence_cls=SquareSequenceFormat,
        show_braces_when_empty=True,
    ),
    UnorderedSequenceMaker(
        include_name=True,
        base_cls=ValuesView,
        sequence_cls=SquareSequenceFormat,
        show_braces_when_empty=True,
    ),
    UnorderedSequenceMaker(
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
    SequenceMaker(
        include_name=True,
        base_cls=deque,
        sequence_cls=SquareSequenceFormat,
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
    deque,
    ast.AST,
    np.ndarray,
)

BaseFormat.KNOWN_EXTRA_CLASSES = (
    Counter,
    frozendict,
    BidictBase,
    UserList,
    UserDict,
    ChainMap,
)


@dataclass(repr=False, kw_only=True, frozen=True)
class FormatterConfig:
    indent_width: int
    width_pair: None | tuple[int, int]
    style: str | None

    def __post_init__(self) -> None:
        if self.style is not None:
            validate_style(self.style)

    @property
    def remaining_width(self) -> int | None:
        if self.width_pair is None:
            return None
        used_width, terminal_width = self.width_pair
        return terminal_width - used_width

    def indent(self) -> Self:
        if self.width_pair is None:
            return self
        used_width, terminal_width = self.width_pair
        return self.replace(
            width_pair=(used_width, terminal_width - self.indent_width),
        )

    def replace(self, **kwargs: Any) -> Self:
        return dataclasses.replace(self, **kwargs)

    def flatten(self) -> Self:
        return self.replace(width_pair=None)

    def get_indent(self) -> str:
        return " " * self.indent_width

    def _update_used_space(self, update: Callable[[int], int]) -> Self:
        if self.width_pair is None:
            return self
        used_width, terminal_width = self.width_pair
        return self.replace(
            width_pair=(update(used_width), terminal_width),
        )

    def use_extra(self, space: int) -> Self:
        return self._update_used_space(lambda used_width: used_width + space)

    def use_only(self, space: int) -> Self:
        return self._update_used_space(lambda used_width: space)

    @property
    def color(self) -> bool:
        return self.style is not None

    def get_style(self, enabled: bool) -> str | None:
        if not enabled:
            return None
        return self.style


def pprint(
    obj: Any,
    /,
    *,
    file: SupportsWrite[str] | None = None,
    width: int | Literal["auto"] | None = "auto",
    style: str | Literal["config"] | None = "config",
    color: bool | Literal["auto"] | Literal["config"] = "config",
    indent: int | Literal["config"] = "config",
    sort_unordered_collections: bool = False,
    prefix: str = "",
) -> None:
    """Pretty print an object to a file. This recursively calls `repr` on all the subobjects, but with special overrides for common classes.

    Args:
        obj (Any):
            The object to pretty print.

        file (SupportsWrite[str] | None, optional):
            The file to write to.
            If `None` is used, `sys.stdout` will be used.
            Defaults to `None`.

        width (int | Literal["auto"] | None, optional):
            The terminal width for pretty printing.
            If `"auto"` is used, this is calculated based on the `file` width (if `file` is a terminal).
            However, if `file` is not a terminal, a default of 80 is used.
            If `None` is used, the file is treated as having infinite length, but multiple lines may still be used.
            Defaults to `"auto"`.

        style (str | Literal["config"] | None, optional):
            The color scheme to use for displaying text.
            If `"config"` is used, the style is taken from local `dbg.conf` files.
            If a string is used, the output will be colored using that color theme.
            See https://pygments.org/styles/ for the full list of styles.
            If `None` is used, the output will not be colored.
            Defaults to `"config"`.

        color (bool | Literal["auto"] | Literal["config"], optional):
            Whether to use color when displaying the output.
            If `"config"` is used, highlighting is determined from local `dbg.conf` files.
            If `"auto"` is used, this is calculated based on whether `file` is a terminal that supports color.
            If `True` is used, `style` is always used to highlight.
            If `False` is used, the output is never highlighted.
            Defaults to `"config"`.

        indent (int | Literal["config"], optional):
            The indent size when printing nested objects.
            If `"config"` is used, the indent is taken from local `dbg.conf` files.
            If an integer is used, that many spaces are used for indenting.
            Defaults to `"config"`.

        prefix (str, optional):
            A prefix to print before the object is formatted.
            This string is never colored or formatted.
            Defaults to `""`.
    """
    if color is True and style is None:
        warnings.warn(
            f"`color` was set to {color!r}, but `style` was set to {style!r}. "
            "The output will not be colored."
        )
    elif color is False and (style is not None and style != "config"):
        warnings.warn(
            f"`color` was set to {color!r}, but `style` was set to {style!r}. "
            "The output will not be colored."
        )
    if file is None:
        file = sys.stdout
    if file == "upper":
        wrapped_file = FileWrapper.back()
    else:
        wrapped_file = FileWrapper(file)
    if color == "config":
        color = CONFIG.color
    if style == "config":
        style = CONFIG.style
    if indent == "config":
        indent = CONFIG.indent
    if color == "auto":
        color = wrapped_file.supports_color
    if width == "auto":
        width = wrapped_file.terminal_width
    if not color:
        style = None
    wrapped_file.write(
        pformat(
            obj,
            width=width,
            style=style,
            indent=indent,
            sort_unordered_collections=sort_unordered_collections,
            prefix=prefix,
        )
        + "\n"
    )


def pformat(
    obj: Any,
    /,
    *,
    width: int | None = defaults.DEFAULT_WIDTH,
    style: str | None = None,
    indent: int = defaults.DEFAULT_INDENT,
    sort_unordered_collections: bool = False,
    prefix: str = "",
) -> str:
    """Pretty print an object to a string. This recursively calls `repr` on all the subobjects, but with special overrides for common classes.

    Args:
        obj (Any):
            The object to pretty print.

        width (int | None, optional):
            The terminal width for pretty printing.
            If `None` is used, the file is treated as having infinite length, but multiple lines may still be used.
            Defaults to 80.

        style (str | None, optional):
            The color scheme to use for displaying text.
            If a string is used, the output will be colored using that color theme.
            See https://pygments.org/styles/ for the full list of styles.
            If `None` is used, the output will not be colored.
            Defaults to `None`.

        indent (int, optional):
            The number of spaces to use for indents when printing nested objects.
            Defaults to 4.

        prefix (str, optional):
            A prefix to print before the object is formatted.
            This string is never colored or formatted.
            Defaults to `""`.
    """
    *_, last_line = prefix.rsplit("\n", maxsplit=1)
    initial_offset = BaseFormat.len(last_line)
    if width is None:
        width_pair = None
    else:
        width_pair = (initial_offset, width)
    config = FormatterConfig(width_pair=width_pair, indent_width=indent, style=style)
    formatted_obj = BaseFormat._from(
        obj, set(), sort_unordered_collections=sort_unordered_collections
    )
    text = formatted_obj._format(highlight_now=True, config=config)
    if prefix and isinstance(formatted_obj, ItemFormat) and text:
        max_len = max(map(BaseFormat.len, text.splitlines()))
        if config.remaining_width is not None and max_len > config.remaining_width:
            text = "\n" + text
            if config.remaining_width >= 1:
                text = "\u23ce" + text
        else:
            text = textwrap.indent(text, " " * initial_offset, predicate=not_first())
    return prefix + text
