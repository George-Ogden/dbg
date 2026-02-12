from array import array
import ast
from collections import (
    ChainMap,
    Counter,
    OrderedDict,
    UserDict,
    UserList,
    defaultdict,
    deque,
    namedtuple,
)
from dataclasses import dataclass, field
import importlib
import io
import sys
import textwrap
from typing import Any, ClassVar, Final, NamedTuple, Self
from unittest import mock

import bidict
from colorama import Fore
from frozendict import frozendict
import numpy as np
import pytest

from . import defaults as defaults
from . import pformat
from .format import ANSI_PATTERN, pprint, strip_ansi


class MultilineObject:
    def __init__(self, lengths: list[int]) -> None:
        self._string = "\n".join(
            [
                chr(i) * length
                for i, length in zip(range(ord("A"), ord("A") + len(lengths)), lengths, strict=True)
            ]
        )

    def __repr__(self) -> str:
        return self._string


class ColoredMultilineObject:
    def __init__(self, lengths: list[int]) -> None:
        reset_character: Final[str] = "\033[39m"
        self._string = "\n".join(
            [
                f"{color}{chr(i) * length}{reset_character}"
                for i, length, color in zip(
                    range(ord("A"), ord("A") + len(lengths)),
                    lengths,
                    [Fore.RED, Fore.BLUE, Fore.GREEN],
                    strict=False,
                )
            ]
        )

    def __repr__(self) -> str:
        return self._string


recursive_list: list[Any] = []
recursive_list.append(recursive_list)

recursive_tree: list[Any] = []
recursive_tree.append(recursive_tree)
recursive_tree.append(recursive_tree)

recursive_dict: dict[Any, Any] = {}
recursive_dict[dict] = recursive_dict
recursive_dict[list] = recursive_list

recursive_multi_object_dict: dict[Any, Any] = {}
recursive_multi_object_list = []
recursive_multi_object_list.append(recursive_multi_object_dict)
recursive_multi_object_dict[0] = recursive_multi_object_list
recursive_multi_object_dict[1] = []

partial_recursive_object = (recursive_list, recursive_list)

recursive_chainmap: ChainMap[Any, Any] = ChainMap()
recursive_chainmap[ChainMap] = recursive_chainmap

recursive_numpy_array = np.array([None], dtype=object)
recursive_numpy_array[0] = recursive_numpy_array


class ListSubclass(list): ...


def custom_repr_cls(name: str, bases: type | tuple[type], *args: Any) -> Any:
    if not isinstance(bases, tuple):
        bases = (bases,)

    def __repr__(self: Any) -> str:  # noqa: N807
        return f"{name}!"

    return type(name, bases, dict(__repr__=__repr__))(*args)


@dataclass
class DataclassNoField: ...


@dataclass
class DataclassOneField:
    single_field: str


@dataclass
class DataclassMultipleFields:
    field1: int
    hidden: None = field(default=None, repr=False)
    field2: list[int] = field(default_factory=list)


@dataclass(repr=False)
class DataclassNoRepr:
    instance: ClassVar[Self]


DataclassNoRepr.instance = DataclassNoRepr()


@dataclass
class DataclassCustomRepr:
    def __repr__(self) -> str:
        return "DataclassCustomRepr!"


@dataclass
class RecursiveDataclass:
    recursive: Self


recursive_dataclass = RecursiveDataclass(None)  # type: ignore
recursive_dataclass.recursive = recursive_dataclass

recursive_ast = ast.Set([])
recursive_ast.elts.append(recursive_ast)


class EmptyRepr:
    def __repr__(self) -> str:
        return ""


class UserLister(UserList): ...


class UserDicter(UserDict): ...


if hasattr(ast.Constant, "_field_types"):
    nested_ast_expression = ast.Expression(body=ast.List(elts=[ast.Constant(1), ast.Name("x")]))
else:
    nested_ast_expression = ast.Expression(
        body=ast.List(
            elts=[ast.Constant(1), ast.Name("x", ctx=None)],  # type: ignore
            ctx=None,  # type: ignore
        )
    )


class RecursiveNamedTuple(NamedTuple):
    attr: list[Any]


recursive_named_tuple = RecursiveNamedTuple([])
recursive_named_tuple.attr.append(recursive_named_tuple)


@pytest.mark.parametrize(
    "obj, width, expected",
    [
        (10, None, "10"),
        (None, None, "None"),
        ("hello", None, "'hello'"),
        ("hello", 7, "'hello'"),
        ("hello", 1, "'hello'"),
        (["a", 10, None, 5.0], 20, "['a', 10, None, 5.0]"),
        (
            ["a", 10, None, 5.0],
            19,
            """
            [
                'a',
                10,
                None,
                5.0,
            ]
            """,
        ),
        (
            [[], [[]], [], [[], []]],
            24,
            """
            [[], [[]], [], [[], []]]
            """,
        ),
        (
            [[], [[]], [], [[], []]],
            23,
            """
            [
                [],
                [[]],
                [],
                [[], []],
            ]
            """,
        ),
        (
            [[], [[]], [], [[], []]],
            13,
            """
            [
                [],
                [[]],
                [],
                [[], []],
            ]
            """,
        ),
        (
            [[], [[]], [], [[], []]],
            12,
            """
            [
                [],
                [[]],
                [],
                [
                    [],
                    [],
                ],
            ]
            """,
        ),
        (
            [[], [[]], [], [[], []]],
            9,
            """
            [
                [],
                [[]],
                [],
                [
                    [],
                    [],
                ],
            ]
            """,
        ),
        (
            [[], [[]], [], [[], []]],
            8,
            """
            [
                [],
                [
                    [],
                ],
                [],
                [
                    [],
                    [],
                ],
            ]
            """,
        ),
        (
            [[], [[]], [], [[], []]],
            1,
            """
            [
                [],
                [
                    [],
                ],
                [],
                [
                    [],
                    [],
                ],
            ]
            """,
        ),
        (
            [MultilineObject([1, 1])],
            None,
            """
            [
                A
                B,
            ]
            """,
        ),
        (
            [[], [MultilineObject([1, 1])]],
            None,
            """
            [
                [],
                [
                    A
                    B,
                ],
            ]
            """,
        ),
        ({"a", "b"}, 10, ["{'a', 'b'}", "{'b', 'a'}"]),
        (
            {"a", "b"},
            9,
            [
                """
                {
                    'a',
                    'b',
                }
                """,
                """
                {
                    'b',
                    'a',
                }
                """,
            ],
        ),
        (
            [{MultilineObject([3, 2])}],
            None,
            """
            [
                {
                    AAA
                    BB,
                },
            ]
            """,
        ),
        (set(), None, "set()"),
        ([set(), set()], None, "[set(), set()]"),
        ([set(), set()], 14, "[set(), set()]"),
        (
            [set(), set()],
            13,
            """
            [
                set(),
                set(),
            ]
            """,
        ),
        ((), None, "()"),
        ((100,), None, "(100,)"),
        ((100,), 6, "(100,)"),
        (
            (100,),
            5,
            """
            (
                100,
            )
            """,
        ),
        (("a", "b"), None, "('a', 'b')"),
        (("a", "b"), 10, "('a', 'b')"),
        (
            ("a", "b"),
            9,
            """
            (
                'a',
                'b',
            )
            """,
        ),
        (
            (MultilineObject([2, 2]),),
            None,
            """
            (
                AA
                BB,
            )
            """,
        ),
        ({}, None, "{}"),
        (set(), 1, "set()"),
        ({}, 1, "{}"),
        (dict(a=50, b=5), None, "{'a': 50, 'b': 5}"),
        (dict(a=50, b=5), 17, "{'a': 50, 'b': 5}"),
        (
            dict(a=50, b=5),
            16,
            """
            {
                'a': 50,
                'b': 5,
            }
            """,
        ),
        ({0: 1}, None, "{0: 1}"),
        (
            dict(a=MultilineObject([3, 1, 3])),
            None,
            """
            {
                'a': AAA
                     B
                     CCC,
            }
            """,
        ),
        (
            dict(a=MultilineObject([3, 3]), aa=MultilineObject([2, 1])),
            None,
            """
            {
                'a': AAA
                     BBB,
                'aa': AA
                      B,
            }
            """,
        ),
        (
            {"a" * 5: [100, 200]},
            20,
            """
            {
                'aaaaa': [
                    100,
                    200,
                ],
            }
            """,
        ),
        ({EmptyRepr(): EmptyRepr()}, None, "{: }"),
        (
            {MultilineObject([3, 3]): "a", MultilineObject([1, 1]): "aa"},
            None,
            """
            {
                AAA
                BBB: 'a',
                A
                B: 'aa',
            }
            """,
        ),
        (
            {MultilineObject([3, 3]): MultilineObject([2, 2, 2])},
            None,
            """
            {
                AAA
                BBB: AA
                     BB
                     CC,
            }
            """,
        ),
        (
            {(MultilineObject([3, 3]),): [MultilineObject([2, 2, 2])]},
            None,
            """
            {
                (
                    AAA
                    BBB,
                ): [
                    AA
                    BB
                    CC,
                ],
            }
            """,
        ),
        ({1: dict(a={}), 2: dict(b={}, c=[])}, None, "{1: {'a': {}}, 2: {'b': {}, 'c': []}}"),
        ({1: dict(a={}), 2: dict(b={}, c=[])}, 37, "{1: {'a': {}}, 2: {'b': {}, 'c': []}}"),
        (
            {1: dict(a={}), 2: dict(b={}, c=[])},
            36,
            """
            {
                1: {'a': {}},
                2: {'b': {}, 'c': []},
            }
            """,
        ),
        (
            {1: dict(a={}), 2: dict(b={}, c=[])},
            26,
            """
            {
                1: {'a': {}},
                2: {'b': {}, 'c': []},
            }
            """,
        ),
        (
            {1: dict(a={}), 2: dict(b={}, c=[])},
            25,
            """
            {
                1: {'a': {}},
                2: {
                    'b': {},
                    'c': [],
                },
            }
            """,
        ),
        (
            {1: dict(a={}), 2: dict(b={}, c=[])},
            17,
            """
            {
                1: {'a': {}},
                2: {
                    'b': {},
                    'c': [],
                },
            }
            """,
        ),
        (
            {1: dict(a={}), 2: dict(b={}, c=[])},
            16,
            """
            {
                1: {
                    'a': {},
                },
                2: {
                    'b': {},
                    'c': [],
                },
            }
            """,
        ),
        (
            {1: dict(a={}), 2: dict(b={}, c=[])},
            1,
            """
            {
                1: {
                    'a': {},
                },
                2: {
                    'b': {},
                    'c': [],
                },
            }
            """,
        ),
        (
            {
                1: dict(a=MultilineObject([2, 2])),
                2: dict(b=MultilineObject([2, 2]), c=MultilineObject([2, 2])),
            },
            None,
            """
            {
                1: {
                    'a': AA
                         BB,
                },
                2: {
                    'b': AA
                         BB,
                    'c': AA
                         BB,
                },
            }
            """,
        ),
        (
            {
                1: dict(a=MultilineObject([2, 2])),
                2: dict(b=MultilineObject([2, 2]), c=MultilineObject([2, 2])),
            },
            16,
            """
            {
                1: {
                    'a': AA
                         BB,
                },
                2: {
                    'b': AA
                         BB,
                    'c': AA
                         BB,
                },
            }
            """,
        ),
        (
            {
                1: {MultilineObject([2, 2]): "a"},
                2: {MultilineObject([2, 2]): "b", MultilineObject([1, 1]): "c"},
            },
            None,
            """
            {
                1: {
                    AA
                    BB: 'a',
                },
                2: {
                    AA
                    BB: 'b',
                    A
                    B: 'c',
                },
            }
            """,
        ),
        ({"A" * 5: "B" * 5}, None, "{'AAAAA': 'BBBBB'}"),
        ({"A" * 5: "B" * 5}, 18, "{'AAAAA': 'BBBBB'}"),
        (
            {"A" * 5: "B" * 5},
            17,
            """
            {
                'AAAAA': 'BBBBB',
            }
            """,
        ),
        (
            {"A" * 5: "B" * 5},
            1,
            """
            {
                'AAAAA': 'BBBBB',
            }
            """,
        ),
        (
            {MultilineObject([2, 3, 3]): MultilineObject([1, 5, 1])},
            14,
            """
            {
                AA
                BBB
                CCC: A
                     BBBBB
                     C,
            }
            """,
        ),
        (
            {MultilineObject([2, 3, 3]): MultilineObject([1, 5, 1])},
            1,
            """
            {
                AA
                BBB
                CCC: A
                     BBBBB
                     C,
            }
            """,
        ),
        (
            {MultilineObject([2, 3, 2]): MultilineObject([1, 5, 1])},
            1,
            """
            {
                AA
                BBB
                CC: A
                    BBBBB
                    C,
            }
            """,
        ),
        (recursive_list, 7, "[[...]]"),
        (
            recursive_list,
            6,
            """
            [
                [...],
            ]
            """,
        ),
        (
            recursive_list,
            1,
            """
            [
                [...],
            ]
            """,
        ),
        (recursive_tree, 14, "[[...], [...]]"),
        (
            recursive_tree,
            13,
            """
            [
                [...],
                [...],
            ]
            """,
        ),
        (recursive_dict, 48, "{<class 'dict'>: {...}, <class 'list'>: [[...]]}"),
        (
            recursive_dict,
            47,
            """
            {
                <class 'dict'>: {...},
                <class 'list'>: [[...]],
            }
            """,
        ),
        (recursive_multi_object_list, None, "[{0: [...], 1: []}]"),
        (recursive_multi_object_dict, 19, "{0: [{...}], 1: []}"),
        (
            recursive_multi_object_dict,
            18,
            """
            {
                0: [{...}],
                1: [],
            }
            """,
        ),
        (partial_recursive_object, None, "([[...]], [[...]])"),
        (recursive_chainmap, None, "ChainMap({<class 'collections.ChainMap'>: ChainMap(...)})"),
        (
            ColoredMultilineObject([2, 2, 2]),
            None,
            """
            \x1b[31mAA\x1b[39m
            \x1b[34mBB\x1b[39m
            \x1b[32mCC\x1b[39m
            """,
        ),
        (recursive_dataclass, None, "RecursiveDataclass(recursive=RecursiveDataclass(...))"),
        (recursive_ast, None, "Set(elts=[Set(...)])"),
        (
            [ColoredMultilineObject([3]), ColoredMultilineObject([4])],
            None,
            "[\x1b[31mAAA\x1b[39m, \x1b[31mAAAA\x1b[39m]",
        ),
        (
            [ColoredMultilineObject([3]), ColoredMultilineObject([4])],
            11,
            "[\x1b[31mAAA\x1b[39m, \x1b[31mAAAA\x1b[39m]",
        ),
        (
            [ColoredMultilineObject([3]), ColoredMultilineObject([4])],
            10,
            """
            [
                \x1b[31mAAA\x1b[39m,
                \x1b[31mAAAA\x1b[39m,
            ]
            """,
        ),
        (
            (ColoredMultilineObject([4]), ColoredMultilineObject([3])),
            11,
            "(\x1b[31mAAAA\x1b[39m, \x1b[31mAAA\x1b[39m)",
        ),
        (
            (ColoredMultilineObject([5]), ColoredMultilineObject([2])),
            10,
            """
            (
                \x1b[31mAAAAA\x1b[39m,
                \x1b[31mAA\x1b[39m,
            )
            """,
        ),
        (defaultdict(list), None, "defaultdict(<class 'list'>, {})"),
        (defaultdict(list), 31, "defaultdict(<class 'list'>, {})"),
        (
            defaultdict(list),
            30,
            """
            defaultdict(
                <class 'list'>,
                {},
            )
            """,
        ),
        (
            defaultdict(list, {0: [1], "a": ["b", "c"]}),
            None,
            "defaultdict(<class 'list'>, {0: [1], 'a': ['b', 'c']})",
        ),
        (
            defaultdict(list, {0: [1], "a": ["b", "c"]}),
            54,
            "defaultdict(<class 'list'>, {0: [1], 'a': ['b', 'c']})",
        ),
        (
            defaultdict(list, {0: [1], "a": ["b", "c"]}),
            53,
            """
            defaultdict(
                <class 'list'>,
                {0: [1], 'a': ['b', 'c']},
            )
            """,
        ),
        (
            defaultdict(list, {0: [1], "a": ["b", "c"]}),
            30,
            """
            defaultdict(
                <class 'list'>,
                {0: [1], 'a': ['b', 'c']},
            )
            """,
        ),
        (
            defaultdict(list, {0: [1], "a": ["b", "c"]}),
            29,
            """
            defaultdict(
                <class 'list'>,
                {
                    0: [1],
                    'a': ['b', 'c'],
                },
            )
            """,
        ),
        (
            defaultdict(list, {0: [1], "a": ["b", "c"]}),
            24,
            """
            defaultdict(
                <class 'list'>,
                {
                    0: [1],
                    'a': ['b', 'c'],
                },
            )
            """,
        ),
        (
            defaultdict(list, {0: [1], "a": ["b", "c"]}),
            23,
            """
            defaultdict(
                <class 'list'>,
                {
                    0: [1],
                    'a': [
                        'b',
                        'c',
                    ],
                },
            )
            """,
        ),
        (Counter(), None, "Counter()"),
        (Counter("aaabbc"), None, "Counter({'a': 3, 'b': 2, 'c': 1})"),
        (Counter("aaabbc"), 33, "Counter({'a': 3, 'b': 2, 'c': 1})"),
        (Counter("cbbaaa"), 33, "Counter({'a': 3, 'b': 2, 'c': 1})"),
        (
            Counter("aaabbc"),
            32,
            """
            Counter({
                'a': 3,
                'b': 2,
                'c': 1,
            })
            """,
        ),
        (
            Counter({3: ["a", "b", "c"], 4: ("a", "b", "c")}),
            None,
            "Counter({3: ['a', 'b', 'c'], 4: ('a', 'b', 'c')})",
        ),
        (
            Counter({3: ["a", "b", "c"], 4: ("a", "b", "c")}),
            49,
            "Counter({3: ['a', 'b', 'c'], 4: ('a', 'b', 'c')})",
        ),
        (
            Counter({3: ["a", "b", "c"], 4: ("a", "b", "c")}),
            48,
            """
            Counter({
                3: ['a', 'b', 'c'],
                4: ('a', 'b', 'c'),
            })
            """,
        ),
        (
            Counter({3: ["a", "b", "c"], 4: ("a", "b", "c")}),
            23,
            """
            Counter({
                3: ['a', 'b', 'c'],
                4: ('a', 'b', 'c'),
            })
            """,
        ),
        (
            Counter({3: ["a", "b", "c"], 4: ("a", "b", "c")}),
            22,
            """
            Counter({
                3: [
                    'a',
                    'b',
                    'c',
                ],
                4: (
                    'a',
                    'b',
                    'c',
                ),
            })
            """,
        ),
        (ListSubclass(), None, "ListSubclass()"),
        (ListSubclass(), 0, "ListSubclass()"),
        (ListSubclass([]), None, "ListSubclass()"),
        (ListSubclass([]), 0, "ListSubclass()"),
        (ListSubclass([1]), None, "ListSubclass([1])"),
        (ListSubclass([1, (), set()]), None, "ListSubclass([1, (), set()])"),
        (ListSubclass([1, (), set()]), 28, "ListSubclass([1, (), set()])"),
        (
            ListSubclass([1, (), set()]),
            27,
            """
            ListSubclass([
                1,
                (),
                set(),
            ])
            """,
        ),
        (custom_repr_cls("SetSubclassCustomRepr", set), None, "SetSubclassCustomRepr!"),
        (custom_repr_cls("SetSubclassCustomRepr", set, [10, 20]), None, "SetSubclassCustomRepr!"),
        (custom_repr_cls("ListSubclassCustomRepr", list), None, "ListSubclassCustomRepr!"),
        (custom_repr_cls("DictSubclassCustomRepr", dict), None, "DictSubclassCustomRepr!"),
        (
            custom_repr_cls("DefaultDictSubclassCustomRepr", defaultdict),
            None,
            "DefaultDictSubclassCustomRepr!",
        ),
        (custom_repr_cls("CounterSubclassCustomRepr", Counter), None, "CounterSubclassCustomRepr!"),
        (
            custom_repr_cls("FrozenSetSubclassCustomRepr", frozenset),
            None,
            "FrozenSetSubclassCustomRepr!",
        ),
        (custom_repr_cls("ArraySubclassCustomRepr", array, "l"), None, "ArraySubclassCustomRepr!"),
        (
            custom_repr_cls("UserListSubclassCustomRepr", UserList),
            None,
            "UserListSubclassCustomRepr!",
        ),
        (
            custom_repr_cls("UserDictSubclassCustomRepr", UserDict),
            None,
            "UserDictSubclassCustomRepr!",
        ),
        (
            custom_repr_cls("OrderedDictSubclassCustomRepr", OrderedDict),
            None,
            "OrderedDictSubclassCustomRepr!",
        ),
        (
            custom_repr_cls("ChainMapSubclassCustomRepr", ChainMap),
            None,
            "ChainMapSubclassCustomRepr!",
        ),
        (custom_repr_cls("ASTNode", ast.Constant, 15), None, "ASTNode!"),
        (custom_repr_cls("DequeSubclassCustomRepr", deque), None, "DequeSubclassCustomRepr!"),
        (
            custom_repr_cls("NumpyArraySubclassCustomRepr", np.ndarray, ()),
            None,
            "NumpyArraySubclassCustomRepr!",
        ),
        (
            custom_repr_cls("BidictSubclassCustomRepr", bidict.bidict),
            None,
            "BidictSubclassCustomRepr!",
        ),
        (DataclassNoField(), None, "DataclassNoField()"),
        (DataclassNoField, None, "<class '_debug.format_test.DataclassNoField'>"),
        (DataclassNoField(), 0, "DataclassNoField()"),
        (DataclassOneField("string"), None, "DataclassOneField(single_field='string')"),
        (DataclassOneField("string"), 40, "DataclassOneField(single_field='string')"),
        (
            DataclassOneField("string"),
            39,
            """
            DataclassOneField(
                single_field='string',
            )
            """,
        ),
        (DataclassMultipleFields(1000), None, "DataclassMultipleFields(field1=1000, field2=[])"),
        (DataclassMultipleFields(1000), 47, "DataclassMultipleFields(field1=1000, field2=[])"),
        (
            DataclassMultipleFields(1000),
            46,
            """
            DataclassMultipleFields(
                field1=1000,
                field2=[],
            )
            """,
        ),
        (
            DataclassMultipleFields(1000, field2=[1, 2, 3, 4, 5, 6]),
            30,
            """
            DataclassMultipleFields(
                field1=1000,
                field2=[1, 2, 3, 4, 5, 6],
            )
            """,
        ),
        (
            DataclassMultipleFields(1000, field2=[1, 2, 3, 4, 5, 6]),
            29,
            """
            DataclassMultipleFields(
                field1=1000,
                field2=[
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                ],
            )
            """,
        ),
        (
            DataclassNoRepr.instance,
            None,
            f"<_debug.format_test.DataclassNoRepr object at {id(DataclassNoRepr.instance):0>#12x}>",
        ),
        (DataclassCustomRepr(), None, "DataclassCustomRepr!"),
        (frozenset(), None, "frozenset()"),
        (frozenset([10]), None, "frozenset({10})"),
        (
            frozenset([frozenset([5, 5, 10])]),
            None,
            ["frozenset({frozenset({10, 5})})", "frozenset({frozenset({5, 10})})"],
        ),
        (
            frozenset([frozenset([5, 5, 10])]),
            31,
            ["frozenset({frozenset({10, 5})})", "frozenset({frozenset({5, 10})})"],
        ),
        (
            frozenset([frozenset([5, 5, 10])]),
            30,
            [
                """
                frozenset({
                    frozenset({10, 5}),
                })
                """,
                """
                frozenset({
                    frozenset({5, 10}),
                })
                """,
            ],
        ),
        (
            frozenset([frozenset([5, 5, 10])]),
            23,
            [
                """
                frozenset({
                    frozenset({10, 5}),
                })
                """,
                """
                frozenset({
                    frozenset({5, 10}),
                })
                """,
            ],
        ),
        (
            frozenset([frozenset([5, 5, 10])]),
            22,
            [
                """
                frozenset({
                    frozenset({
                        10,
                        5,
                    }),
                })
                """,
                """
                frozenset({
                    frozenset({
                        5,
                        10,
                    }),
                })
                """,
            ],
        ),
        (type("freezeset", (frozenset,), {})(), None, "freezeset()"),
        (
            {frozenset([1, 2, 3]): {frozenset([4, 5, 6]): None}},
            29,
            """
            {
                frozenset({1, 2, 3}): {
                    frozenset({4, 5, 6}): None,
                },
            }
            """,
        ),
        (array("l"), None, "array('l')"),
        (array("i"), 10, "array('i')"),
        (
            array("f"),
            9,
            """
            array(
                'f',
            )
            """,
        ),
        (array("q", []), None, "array('q')"),
        (array("l", [100]), None, "array('l', [100])"),
        (array("u", "abracadabra"), None, "array('u', 'abracadabra')"),
        (array("u", "abracadabra"), 25, "array('u', 'abracadabra')"),
        (
            array("u", "abracadabra"),
            24,
            """
            array(
                'u',
                'abracadabra',
            )
            """,
        ),
        (
            array("u", "abracadabra"),
            1,
            """
            array(
                'u',
                'abracadabra',
            )
            """,
        ),
        (array("b", b"abc"), None, "array('b', [97, 98, 99])"),
        (array("b", b"abc"), 24, "array('b', [97, 98, 99])"),
        (
            array("b", b"abc"),
            23,
            """
            array(
                'b',
                [97, 98, 99],
            )
            """,
        ),
        (
            array("b", b"abc"),
            17,
            """
            array(
                'b',
                [97, 98, 99],
            )
            """,
        ),
        (
            array("b", b"abc"),
            16,
            """
            array(
                'b',
                [
                    97,
                    98,
                    99,
                ],
            )
            """,
        ),
        (array("d", [0.0, 0.5, 1.0]), None, "array('d', [0.0, 0.5, 1.0])"),
        (array("d", [0.0, 0.5, 1.0]), 27, "array('d', [0.0, 0.5, 1.0])"),
        (
            array("d", [0.0, 0.5, 1.0]),
            26,
            """
            array(
                'd',
                [0.0, 0.5, 1.0],
            )
            """,
        ),
        (
            array("d", [0.0, 0.5, 1.0]),
            20,
            """
            array(
                'd',
                [0.0, 0.5, 1.0],
            )
            """,
        ),
        (
            array("d", [0.0, 0.5, 1.0]),
            19,
            """
            array(
                'd',
                [
                    0.0,
                    0.5,
                    1.0,
                ],
            )
            """,
        ),
        (type("subarray", (array,), {})("h", [-2]), None, "subarray('h', [-2])"),
        (frozendict(), None, "frozendict({})"),
        (frozendict(Counter("aaabbc")), None, "frozendict({'a': 3, 'b': 2, 'c': 1})"),
        (frozendict(Counter("aaabbc")), 36, "frozendict({'a': 3, 'b': 2, 'c': 1})"),
        (
            frozendict(Counter("aaabbc")),
            35,
            """
            frozendict({
                'a': 3,
                'b': 2,
                'c': 1,
            })
            """,
        ),
        (frozendict(long=list("long")), None, "frozendict({'long': ['l', 'o', 'n', 'g']})"),
        (frozendict(long=list("long")), 42, "frozendict({'long': ['l', 'o', 'n', 'g']})"),
        (
            frozendict(long=list("long")),
            41,
            """
            frozendict({
                'long': ['l', 'o', 'n', 'g'],
            })
            """,
        ),
        (
            frozendict(long=list("long")),
            33,
            """
            frozendict({
                'long': ['l', 'o', 'n', 'g'],
            })
            """,
        ),
        (
            frozendict(long=list("long")),
            32,
            """
            frozendict({
                'long': [
                    'l',
                    'o',
                    'n',
                    'g',
                ],
            })
            """,
        ),
        (type("freezedict", (frozendict,), {})(), None, "freezedict({})"),
        (EmptyRepr(), None, ""),
        (EmptyRepr(), 1, ""),
        (dict.fromkeys([8, 6, 4]).keys(), None, "dict_keys([8, 6, 4])"),
        (dict.fromkeys([8, 6, 4]).keys(), 20, "dict_keys([8, 6, 4])"),
        (
            dict.fromkeys([8, 6, 4]).keys(),
            19,
            """
            dict_keys([
                8,
                6,
                4,
            ])
            """,
        ),
        (
            dict.fromkeys([]).keys(),
            None,
            """
            dict_keys([])
            """,
        ),
        ({(): (), None: None}.values(), None, "dict_values([(), None])"),
        ({(): (), None: None}.values(), 23, "dict_values([(), None])"),
        (
            {(): (), None: None}.values(),
            22,
            """
            dict_values([
                (),
                None,
            ])
            """,
        ),
        (
            {(): (), None: [1, 2, 3, 4, 5]}.values(),
            20,
            """
            dict_values([
                (),
                [1, 2, 3, 4, 5],
            ])
            """,
        ),
        (
            {(): (), None: [1, 2, 3, 4, 5]}.values(),
            19,
            """
            dict_values([
                (),
                [
                    1,
                    2,
                    3,
                    4,
                    5,
                ],
            ])
            """,
        ),
        ({1: 2, 3: 4, 5: 6}.items(), None, "dict_items([(1, 2), (3, 4), (5, 6)])"),
        ({1: 2, 3: 4, 5: 6}.items(), 36, "dict_items([(1, 2), (3, 4), (5, 6)])"),
        (
            {1: 2, 3: 4, 5: 6}.items(),
            35,
            """
            dict_items([
                (1, 2),
                (3, 4),
                (5, 6),
            ])
            """,
        ),
        (UserLister(), None, "UserLister([])"),
        (
            UserLister([[], [1, 2], [3, 4, 5], [6, 7, 8, 9]]),
            None,
            "UserLister([[], [1, 2], [3, 4, 5], [6, 7, 8, 9]])",
        ),
        (
            UserLister([[], [1, 2], [3, 4, 5], [6, 7, 8, 9]]),
            49,
            "UserLister([[], [1, 2], [3, 4, 5], [6, 7, 8, 9]])",
        ),
        (
            UserLister([[], [1, 2], [3, 4, 5], [6, 7, 8, 9]]),
            48,
            """
            UserLister([
                [],
                [1, 2],
                [3, 4, 5],
                [6, 7, 8, 9],
            ])
            """,
        ),
        (
            UserLister([[], [1, 2], [3, 4, 5], [6, 7, 8, 9]]),
            17,
            """
            UserLister([
                [],
                [1, 2],
                [3, 4, 5],
                [6, 7, 8, 9],
            ])
            """,
        ),
        (
            UserLister([[], [1, 2], [3, 4, 5], [6, 7, 8, 9]]),
            16,
            """
            UserLister([
                [],
                [1, 2],
                [3, 4, 5],
                [
                    6,
                    7,
                    8,
                    9,
                ],
            ])
            """,
        ),
        (UserDicter(), None, "UserDicter({})"),
        (
            UserDicter({1: [2, 3], 4: [5, 6, 7, 8]}),
            None,
            "UserDicter({1: [2, 3], 4: [5, 6, 7, 8]})",
        ),
        (UserDicter({1: [2, 3], 4: [5, 6, 7, 8]}), 40, "UserDicter({1: [2, 3], 4: [5, 6, 7, 8]})"),
        (
            UserDicter({1: [2, 3], 4: [5, 6, 7, 8]}),
            39,
            """
            UserDicter({
                1: [2, 3],
                4: [5, 6, 7, 8],
            })
            """,
        ),
        (
            UserDicter({1: [2, 3], 4: [5, 6, 7, 8]}),
            20,
            """
            UserDicter({
                1: [2, 3],
                4: [5, 6, 7, 8],
            })
            """,
        ),
        (
            UserDicter({1: [2, 3], 4: [5, 6, 7, 8]}),
            19,
            """
            UserDicter({
                1: [2, 3],
                4: [
                    5,
                    6,
                    7,
                    8,
                ],
            })
            """,
        ),
        (OrderedDict(), None, "OrderedDict()"),
        (
            OrderedDict({0: [], 1: [2, 3, 4], 5: [6, 7, 8]}),
            None,
            "OrderedDict({0: [], 1: [2, 3, 4], 5: [6, 7, 8]})",
        ),
        (
            OrderedDict({0: [], 1: [2, 3, 4], 5: [6, 7, 8]}),
            48,
            "OrderedDict({0: [], 1: [2, 3, 4], 5: [6, 7, 8]})",
        ),
        (
            OrderedDict({0: [], 1: [2, 3, 4], 5: [6, 7, 8]}),
            47,
            """
            OrderedDict({
                0: [],
                1: [2, 3, 4],
                5: [6, 7, 8],
            })
            """,
        ),
        (
            OrderedDict({0: [], 1: [2, 3, 4], 5: [6, 7, 8]}),
            17,
            """
            OrderedDict({
                0: [],
                1: [2, 3, 4],
                5: [6, 7, 8],
            })
            """,
        ),
        (
            OrderedDict({0: [], 1: [2, 3, 4], 5: [6, 7, 8]}),
            16,
            """
            OrderedDict({
                0: [],
                1: [
                    2,
                    3,
                    4,
                ],
                5: [
                    6,
                    7,
                    8,
                ],
            })
            """,
        ),
        (ChainMap(), None, "ChainMap({})"),
        (
            ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]}),
            None,
            "ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]})",
        ),
        (
            ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]}),
            48,
            "ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]})",
        ),
        (
            ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]}),
            47,
            """
            ChainMap(
                {0: [1, 2, 3], 4: [5, 6, 7]},
                {8: [9]},
            )""",
        ),
        (
            ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]}),
            33,
            """
            ChainMap(
                {0: [1, 2, 3], 4: [5, 6, 7]},
                {8: [9]},
            )""",
        ),
        (
            ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]}),
            32,
            """
            ChainMap(
                {
                    0: [1, 2, 3],
                    4: [5, 6, 7],
                },
                {8: [9]},
            )""",
        ),
        (
            ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]}),
            21,
            """
            ChainMap(
                {
                    0: [1, 2, 3],
                    4: [5, 6, 7],
                },
                {8: [9]},
            )""",
        ),
        (
            ChainMap({0: [1, 2, 3], 4: [5, 6, 7]}, {8: [9]}),
            20,
            """
            ChainMap(
                {
                    0: [
                        1,
                        2,
                        3,
                    ],
                    4: [
                        5,
                        6,
                        7,
                    ],
                },
                {8: [9]},
            )""",
        ),
        (deque(), None, "deque([])"),
        (deque([[1, 2], [3, 4]]), None, "deque([[1, 2], [3, 4]])"),
        (deque([[1, 2], [3, 4]]), 23, "deque([[1, 2], [3, 4]])"),
        (
            deque([[1, 2], [3, 4]]),
            22,
            """
            deque([
                [1, 2],
                [3, 4],
            ])
            """,
        ),
        (
            deque([[1, 2], [3, 4]]),
            11,
            """
            deque([
                [1, 2],
                [3, 4],
            ])
            """,
        ),
        (
            deque([[1, 2], [3, 4]]),
            10,
            """
            deque([
                [
                    1,
                    2,
                ],
                [
                    3,
                    4,
                ],
            ])
            """,
        ),
        (ast.Load(), None, "Load()"),
        (ast.Name("id", ctx=ast.Load()), None, ["Name(id='id', ctx=Load())", "Name(id='id')"]),
        (
            nested_ast_expression,
            None,
            "Expression(body=List(elts=[Constant(value=1), Name(id='x')]))",
        ),
        (
            nested_ast_expression,
            61,
            "Expression(body=List(elts=[Constant(value=1), Name(id='x')]))",
        ),
        (
            nested_ast_expression,
            60,
            """
            Expression(
                body=List(elts=[Constant(value=1), Name(id='x')]),
            )
            """,
        ),
        (
            nested_ast_expression,
            54,
            """
            Expression(
                body=List(elts=[Constant(value=1), Name(id='x')]),
            )
            """,
        ),
        (
            nested_ast_expression,
            53,
            """
            Expression(
                body=List(
                    elts=[Constant(value=1), Name(id='x')],
                ),
            )
            """,
        ),
        (
            nested_ast_expression,
            47,
            """
            Expression(
                body=List(
                    elts=[Constant(value=1), Name(id='x')],
                ),
            )
            """,
        ),
        (
            nested_ast_expression,
            46,
            """
            Expression(
                body=List(
                    elts=[
                        Constant(value=1),
                        Name(id='x'),
                    ],
                ),
            )
            """,
        ),
        (ast.Constant(0), None, "Constant(value=0)"),
        (ast.Constant(1, None), None, "Constant(value=1)"),
        (ast.Constant(None), None, "Constant(value=None)"),
        (ast.MatchSingleton(None), None, "MatchSingleton(value=None)"),
        (ast.MatchSingleton(False), None, "MatchSingleton(value=False)"),
        (ast.MatchSingleton([]), None, "MatchSingleton(value=[])"),  # type: ignore
        (ast.Constant([]), None, "Constant(value=[])"),  # type: ignore
        (
            ast.Dict(keys=[None], values=[ast.Name("d")]),
            None,
            "Dict(keys=[None], values=[Name(id='d')])",
        ),
        (ast.List(elts=[]), None, "List()"),
        (
            ast.If(
                ast.Constant(value=True),
                body=[ast.Expr(value=ast.Constant(value=Ellipsis))],
                orelse=[],
            ),
            None,
            "If(test=Constant(value=True), body=[Expr(value=Constant(value=Ellipsis))])",
        ),
        (np.array(5), None, "array(5, dtype='int64')"),
        (np.array(5), 23, "array(5, dtype='int64')"),
        (
            np.array(5),
            22,
            """
            array(
                5,
                dtype='int64',
            )
            """,
        ),
        (
            np.array(5),
            18,
            """
            array(
                5,
                dtype='int64',
            )
            """,
        ),
        (
            np.arange(6, dtype=np.float32),
            None,
            "array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0], dtype='float32')",
        ),
        (
            np.arange(6, dtype=np.float32),
            54,
            "array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0], dtype='float32')",
        ),
        (
            np.arange(6, dtype=np.float32),
            53,
            """
            array(
                [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
                dtype='float32',
            )
            """,
        ),
        (
            np.arange(6, dtype=np.float32),
            35,
            """
            array(
                [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
                dtype='float32',
            )
            """,
        ),
        (
            np.arange(6, dtype=np.float32),
            34,
            """
            array(
                [
                    0.0,
                    1.0,
                    2.0,
                    3.0,
                    4.0,
                    5.0,
                ],
                dtype='float32',
            )
            """,
        ),
        (
            np.array([[4, 3], [2, 1]], dtype=np.uint8),
            None,
            "array([[4, 3], [2, 1]], dtype='uint8')",
        ),
        (np.array([[4, 3], [2, 1]], dtype=np.uint8), 38, "array([[4, 3], [2, 1]], dtype='uint8')"),
        (
            np.array([[4, 3], [2, 1]], dtype=np.uint8),
            37,
            """
            array(
                [[4, 3], [2, 1]],
                dtype='uint8',
            )
            """,
        ),
        (
            np.array([[4, 3], [2, 1]], dtype=np.uint8),
            21,
            """
            array(
                [[4, 3], [2, 1]],
                dtype='uint8',
            )
            """,
        ),
        (
            np.array([[4, 3], [2, 1]], dtype=np.uint8),
            20,
            """
            array(
                [
                    [4, 3],
                    [2, 1],
                ],
                dtype='uint8',
            )
            """,
        ),
        (
            np.array([[4, 3], [2, 1]], dtype=np.uint8),
            15,
            """
            array(
                [
                    [4, 3],
                    [2, 1],
                ],
                dtype='uint8',
            )
            """,
        ),
        (
            np.array([[4, 3], [2, 1]], dtype=np.uint8),
            14,
            """
            array(
                [
                    [
                        4,
                        3,
                    ],
                    [
                        2,
                        1,
                    ],
                ],
                dtype='uint8',
            )
            """,
        ),
        (np.array((), dtype=np.int64), None, "array([], dtype='int64')"),
        (recursive_numpy_array, None, "array([array(..., dtype='object')], dtype='object')"),
        (recursive_numpy_array, 51, "array([array(..., dtype='object')], dtype='object')"),
        (
            recursive_numpy_array,
            50,
            """
            array(
                [array(..., dtype='object')],
                dtype='object',
            )
            """,
        ),
        (
            recursive_numpy_array,
            33,
            """
            array(
                [array(..., dtype='object')],
                dtype='object',
            )
            """,
        ),
        (
            recursive_numpy_array,
            32,
            """
            array(
                [
                    array(
                        ...,
                        dtype='object',
                    ),
                ],
                dtype='object',
            )
            """,
        ),
        (bidict.bidict(), None, "bidict()"),
        (bidict.bidict({1: 2}), None, "bidict({1: 2})"),
        (bidict.bidict({1: 2}), 14, "bidict({1: 2})"),
        (
            bidict.bidict({1: 2}),
            13,
            """
            bidict({
                1: 2,
            })
            """,
        ),
        (
            bidict.frozenbidict({bidict.frozenbidict(a="b"): bidict.frozenbidict(c="d")}),
            None,
            "frozenbidict({frozenbidict({'a': 'b'}): frozenbidict({'c': 'd'})})",
        ),
        (
            bidict.frozenbidict({bidict.frozenbidict(a="b"): bidict.frozenbidict(c="d")}),
            66,
            "frozenbidict({frozenbidict({'a': 'b'}): frozenbidict({'c': 'd'})})",
        ),
        (
            bidict.frozenbidict({bidict.frozenbidict(a="b"): bidict.frozenbidict(c="d")}),
            65,
            """
            frozenbidict({
                frozenbidict({'a': 'b'}): frozenbidict({'c': 'd'}),
            })
            """,
        ),
        (
            bidict.frozenbidict({bidict.frozenbidict(a="b"): bidict.frozenbidict(c="d")}),
            55,
            """
            frozenbidict({
                frozenbidict({'a': 'b'}): frozenbidict({'c': 'd'}),
            })
            """,
        ),
        (
            bidict.frozenbidict({bidict.frozenbidict(a="b"): bidict.frozenbidict(c="d")}),
            54,
            """
            frozenbidict({
                frozenbidict({'a': 'b'}): frozenbidict({
                    'c': 'd',
                }),
            })
            """,
        ),
        (
            bidict.frozenbidict({bidict.frozenbidict(a="b"): bidict.frozenbidict(c="d")}),
            26,
            """
            frozenbidict({
                frozenbidict({
                    'a': 'b',
                }): frozenbidict({
                    'c': 'd',
                }),
            })
            """,
        ),
        (namedtuple("Point", ["x", "y"])(0, 1), None, "Point(x=0, y=1)"),  # type: ignore [call-arg,arg-type]
        (namedtuple("Point", ["x", "y"])(0, 1), 15, "Point(x=0, y=1)"),  # type: ignore [call-arg,arg-type]
        (
            namedtuple("Point", ["x", "y"])(0, 1),  # type: ignore [call-arg,arg-type]
            14,
            """
            Point(
                x=0,
                y=1,
            )
            """,
        ),
        (namedtuple("wrapper", ["list"])([1, 2, 3]), None, "wrapper(list=[1, 2, 3])"),
        (namedtuple("wrapper", ["list"])([1, 2, 3]), 23, "wrapper(list=[1, 2, 3])"),
        (
            namedtuple("wrapper", ["list"])([1, 2, 3]),
            22,
            """
            wrapper(
                list=[1, 2, 3],
            )
            """,
        ),
        (
            namedtuple("wrapper", ["list"])([1, 2, 3]),
            19,
            """
            wrapper(
                list=[1, 2, 3],
            )
            """,
        ),
        (
            namedtuple("wrapper", ["list"])([1, 2, 3]),
            18,
            """
            wrapper(
                list=[
                    1,
                    2,
                    3,
                ],
            )
            """,
        ),
        (recursive_named_tuple, None, "RecursiveNamedTuple(attr=[RecursiveNamedTuple(...)])"),
        (
            custom_repr_cls(
                "NamedTupleSubclassCustomRepr", namedtuple("namedtuple", ["field"]), "1"
            ),
            None,
            "NamedTupleSubclassCustomRepr!",
        ),
        (namedtuple("Empty", [])(), None, "Empty()"),
        (namedtuple("Empty", [])(), 0, "Empty()"),
    ],
)
def test_format(obj: Any, width: int | None, expected: list | str) -> None:
    string = pformat(obj, style="monokai", width=width, indent=4)
    if not isinstance(expected, str) or not ANSI_PATTERN.search(expected):
        string = strip_ansi(string)
    if not isinstance(expected, list):
        expected = [expected]
    expected = [textwrap.dedent(output).strip() for output in expected]
    if len(expected) == 1:
        [expected] = expected
        assert string == expected
    else:
        assert string in expected


@pytest.mark.parametrize(
    "obj, width, expected",
    [
        ({}, None, "{}"),
        ({3: 1, 2: 2, 1: 3}, None, "{1: 3, 2: 2, 3: 1}"),
        ({3: 1, 2: 2, 1: 3}, 18, "{1: 3, 2: 2, 3: 1}"),
        (
            {3: 1, 2: 2, 1: 3},
            17,
            """
            {
                1: 3,
                2: 2,
                3: 1,
            }
            """,
        ),
        (
            {2: {2: 1, 1: 2}, 1: {2: 1, 1: 2}},
            20,
            """
            {
                1: {1: 2, 2: 1},
                2: {1: 2, 2: 1},
            }
            """,
        ),
        (
            frozendict({2: frozendict({2: 1, 1: 2}), 1: frozendict({2: 1, 1: 2})}),
            32,
            """
            frozendict({
                1: frozendict({1: 2, 2: 1}),
                2: frozendict({1: 2, 2: 1}),
            })
            """,
        ),
        (Counter("abbccc"), None, "Counter({'c': 3, 'b': 2, 'a': 1})"),
        (Counter([frozendict({2: 1, 1: 2})] * 2), None, "Counter({frozendict({1: 2, 2: 1}): 2})"),
        (OrderedDict([(3, 1), (2, 2), (1, 3)]), None, "OrderedDict({3: 1, 2: 2, 1: 3})"),
        ((3, 2, 1), None, "(3, 2, 1)"),
        ([3, 2, 1], None, "[3, 2, 1]"),
        ({5, 4, 3, 2, 1}, None, "{1, 2, 3, 4, 5}"),
        ({"5", "4", "3", "2", "1"}, None, "{'1', '2', '3', '4', '5'}"),
        (frozenset({"5", "4", "3", "2", "1"}), None, "frozenset({'1', '2', '3', '4', '5'})"),
        (
            frozenset([frozenset({"4", "3", "2", "1"}), frozenset({"3", "2", "1"})]),
            36,
            [
                """
                frozenset({
                    frozenset({'1', '2', '3'}),
                    frozenset({'1', '2', '3', '4'}),
                })
                """,
                """
                frozenset({
                    frozenset({'1', '2', '3', '4'}),
                    frozenset({'1', '2', '3'}),
                })
                """,
            ],
        ),
        ({None, 1}, None, ["{None, 1}", "{1, None}"]),
        (
            {"a", "b", "c", 1.0, 2.0, 3.0},
            None,
            ["{'a', 'b', 'c', 1.0, 2.0, 3.0}", "{1.0, 2.0, 3.0, 'a', 'b', 'c'}"],
        ),
    ],
)
def test_sorted_format(obj: Any, width: int | None, expected: list | str) -> None:
    string = pformat(obj, style=None, width=width, indent=4, sort_unordered_collections=True)
    if not isinstance(expected, list):
        expected = [expected]
    expected = [textwrap.dedent(output).strip() for output in expected]
    if len(expected) == 1:
        [expected] = expected
        assert string == expected
    else:
        assert string in expected


@pytest.mark.parametrize(
    "obj, module, width, expected",
    [
        (recursive_dict, "frozendict", 48, "{<class 'dict'>: {...}, <class 'list'>: [[...]]}"),
        (
            recursive_dict,
            "frozendict",
            47,
            """
            {
                <class 'dict'>: {...},
                <class 'list'>: [[...]],
            }
            """,
        ),
        (recursive_list, "numpy", 7, "[[...]]"),
        (
            recursive_list,
            "numpy",
            6,
            """
            [
                [...],
            ]
            """,
        ),
        ({}, "bidict", None, "{}"),
    ],
)
def test_format_without_module(obj: Any, module: str, width: int | None, expected: str) -> None:
    with mock.patch.dict(sys.modules, {module: None}):
        importlib.reload(sys.modules["_debug.format"])
        string = pformat(obj, style="monokai", width=width, indent=4)
    importlib.reload(sys.modules["_debug.format"])
    string = strip_ansi(string)
    expected = textwrap.dedent(expected).strip()
    assert string == expected


@pytest.mark.parametrize(
    "obj, initial_width, width, expected",
    [
        (True, 2, None, "*_True"),
        (2.5, 3, None, "**_2.5"),
        (["aaa", "bbb"], 6, 20, "*****_['aaa', 'bbb']"),
        (
            ["aaa", "bbb"],
            7,
            20,
            """
            ******_[
                'aaa',
                'bbb',
            ]
            """,
        ),
        (
            MultilineObject([1, 1, 1]),
            4,
            None,
            """
            ***_A
                B
                C
            """,
        ),
        (
            MultilineObject([4, 4, 4]),
            4,
            8,
            """
            ***_AAAA
                BBBB
                CCCC
            """,
        ),
        (
            MultilineObject([4, 4, 4]),
            4,
            7,
            """
            ***_[ENTER]
            AAAA
            BBBB
            CCCC
            """,
        ),
        (
            MultilineObject([4, 4, 4]),
            4,
            5,
            """
            ***_[ENTER]
            AAAA
            BBBB
            CCCC
            """,
        ),
        (
            MultilineObject([4, 4, 4]),
            4,
            4,
            """
            ***_
            AAAA
            BBBB
            CCCC
            """,
        ),
        (
            ColoredMultilineObject([2, 2, 2]),
            2,
            None,
            """
            *_\x1b[31mAA\x1b[39m
              \x1b[34mBB\x1b[39m
              \x1b[32mCC\x1b[39m
            """,
        ),
        (
            ColoredMultilineObject([2, 2, 2]),
            2,
            4,
            """
            *_\x1b[31mAA\x1b[39m
              \x1b[34mBB\x1b[39m
              \x1b[32mCC\x1b[39m
            """,
        ),
        (
            ColoredMultilineObject([2, 2, 2]),
            3,
            4,
            """
            **_[ENTER]
            \x1b[31mAA\x1b[39m
            \x1b[34mBB\x1b[39m
            \x1b[32mCC\x1b[39m
            """,
        ),
        (
            ColoredMultilineObject([2, 2, 2]),
            4,
            4,
            """
            ***_
            \x1b[31mAA\x1b[39m
            \x1b[34mBB\x1b[39m
            \x1b[32mCC\x1b[39m
            """,
        ),
    ],
)
def test_format_offset(
    obj: Any, initial_width: int, width: int | None, expected: list | str
) -> None:
    prefix = (initial_width - 1) * "*" + "_"
    string = pformat(obj, width=width, indent=4, style="monokai", prefix=prefix)
    if not isinstance(expected, str) or not ANSI_PATTERN.search(expected):
        string = strip_ansi(string)
    if not isinstance(expected, list):
        expected = [expected]
    assert initial_width > 1
    expected = [textwrap.dedent(output).strip().replace("[ENTER]", "⏎") for output in expected]
    if len(expected) == 1:
        [expected] = expected
        assert string == expected
    else:
        assert string in expected


@pytest.mark.parametrize(
    "prefix, obj, width, expected",
    [
        ("======", "hello", 6, "======\n'hello'"),
        ("=====", "hello", 6, "=====[ENTER]\n'hello'"),
        ("=======\n", "hello", 7, "=======\n'hello'"),
        ("========\n\x1b[34m=\x1b[39m", "hello", 8, "========\n\x1b[34m=\x1b[39m'hello'"),
    ],
)
def test_format_with_prefix(prefix: str, obj: Any, width: int, expected: str) -> None:
    expected = textwrap.dedent(expected).strip().replace("[ENTER]", "⏎")
    assert pformat(obj, width=width, prefix=prefix, style=None) == expected


def test_format_with_invalid_style() -> None:
    with pytest.raises(
        ValueError, match=r"Unknown style 'unknown'\. Please, choose one of \[.*\]\."
    ):
        pformat((), style="unknown")


def test_pprint_default_file_is_stdout(capsys: pytest.CaptureFixture) -> None:
    pprint("test", color=False, style=None)
    out, err = capsys.readouterr()
    assert out == "'test'\n"
    assert err == ""


def test_pprint_write_to_custom_file() -> None:
    original_pformat = pformat
    saved_kwargs: dict[str, Any] | None = None

    def mock_pformat(obj: Any, **kwargs: Any) -> str:
        nonlocal saved_kwargs
        saved_kwargs = kwargs
        return original_pformat(obj, **kwargs)

    with io.StringIO() as file:
        with mock.patch("_debug.format.pformat", mock_pformat):
            pprint("test", color="auto", width="auto", file=file)

        assert file.getvalue() == "'test'\n"

    assert saved_kwargs is not None
    assert saved_kwargs["style"] is None
    assert saved_kwargs["width"] == defaults.DEFAULT_WIDTH


@pytest.mark.parametrize(
    "kwargs, warning",
    [
        ({}, None),
        (
            dict(color=True, style=None),
            r"^`color` was set to True, but `style` was set to None\. "
            r"The output will not be colored\.$",
        ),
        (dict(color=False, style=None), None),
        (
            dict(color=False, style="monokai"),
            r"`color` was set to False, but `style` was set to 'monokai'\. "
            r"The output will not be colored\.$",
        ),
        (dict(color=True, style="monokai"), None),
        (dict(color=False, style="config"), None),
        (dict(color=True, style="config"), None),
    ],
)
@pytest.mark.filterwarnings("error")
def test_pprint_argument_validation(kwargs: dict[str, Any], warning: None | str) -> None:
    if warning is None:
        pprint((), **kwargs)
    else:
        with pytest.warns(match=warning):
            pprint((), **kwargs)


@pytest.mark.parametrize(
    "kwargs, color",
    [
        (dict(color=True, style=None), False),
        (dict(color=False, style="monokai"), False),
        (dict(color=True, style="monokai"), True),
    ],
)
@pytest.mark.filterwarnings("ignore")
def test_pprint_color_calculation(kwargs: dict[str, Any], color: bool) -> None:
    with io.StringIO() as file:
        pprint(100, **kwargs, file=file)
        assert strip_ansi(file.getvalue()) == "100\n"
        assert (file.getvalue() == "100\n") == (not color)
