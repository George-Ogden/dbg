import filecmp
import importlib
import os
import re
import sys
import tempfile
import textwrap
from typing import Any
from unittest import mock

from _pytest.capture import CaptureFixture
from colorama import Fore
from pygments.formatters import Terminal256Formatter
import pytest

from debug import CONFIG
from debug._config import DbgConfig
from debug._format import ANSI_PATTERN, Formatter, FormatterConfig, strip_ansi

SAMPLE_DIR = "test_samples"
TEST_DATA_DIR = "test_data"


@pytest.fixture(autouse=True)
def reset_modules() -> None:
    for key in list(sys.modules.keys()):
        if key.startswith(SAMPLE_DIR):
            del sys.modules[key]


@pytest.mark.parametrize(
    "name,expected_out,expected_err",
    [
        ("number", "12", "[number.py:3:7] 12 = 12"),
        ("variable", "17", "[variable.py:5:7] x = 17"),
        ("two_line", "-32", "[two_line.py:6:7] x * y = -32"),
        ("three_line", "14\n14", "[three_line.py:3:7] y := (10 + 4) = 14"),
        (
            "same_line",
            "7",
            """
            [same_line.py:6:7] x = 3
            [same_line.py:6:16] y = 4
            """,
        ),
        (
            "nested_expression",
            "4",
            """
            [nested_expression.py:5:11] x := x + 1 = 4
            [nested_expression.py:5:7] dbg(x := x + 1) = 4
            """,
        ),
        ("nested.file", "foo", "[nested/file.py:5:7] x = 'foo'"),
        ("offset", "5", "[offset.py:7:12] arg = 5"),
        ("no_offset", "-5", "[no_offset.py:3:12] arg = -5"),
        (
            "nested_function",
            "8",
            """
            [nested_function.py:8:16] a = 2
            [nested_function.py:8:25] b = 6
            """,
        ),
        (
            "multiple_arguments",
            "('hello', 8.5)",
            """
            [multiple_arguments.py:6:7] x = 'hello'
            [multiple_arguments.py:6:7] y = 8.5
            """,
        ),
        ("singleton", "False", "[singleton.py:4:7] v = False"),
        ("no_arguments", "()", "[no_arguments.py:3:7]"),
        (
            "multiline_arguments",
            "('bye', 0.25, -5)",
            """
            [multiline_arguments.py:7:7] x = 'bye'
            [multiline_arguments.py:7:7] y = 0.25
            [multiline_arguments.py:7:7] z + 4 = -5
            """,
        ),
        (
            "string",
            """
            foo
            bar
            """,
            """
            [string.py:3:7] 'foo' = 'foo'
            [string.py:4:7] "bar" = 'bar'
            """,
        ),
        ("brackets", "()", "[brackets.py:3:7] ((())) = ()"),
        (
            "generator",
            "None",
            ["[generator.py:7:44] True = True", "[generator.py:7:44] <unknown> = True"],
        ),
        (
            "lists",
            """
            [8, 9, 10]
            [8, 9, 10]
            [A
            B, 'A\\nB']
            """,
            """
            [lists.py:3:7] [8, 9, 10] = [8, 9, 10]
            [lists.py:7:7] [
                8,
                9,
                10,
            ] = [8, 9, 10]
            [lists.py:15:7] [MultilineObject(), "A\\nB"] = [
                A
                B,
                'A\\nB',
            ]
            """,
        ),
        ("colored_repr", "[0]", "[colored_repr.py:8:7] ColoredRepr() = [0]"),
    ],
)
def test_samples(
    name: str, expected_out: str, expected_err: str | list[str], capsys: CaptureFixture
) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.{name}"
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        importlib.import_module(module)
        CONFIG.indent = 4

    expected_out = textwrap.dedent(expected_out).strip()
    if not isinstance(expected_err, list):
        expected_err = [expected_err]
    expected_err = [textwrap.dedent(possible_err).strip() for possible_err in expected_err]

    out, err = capsys.readouterr()
    assert strip_ansi(out.strip()) == expected_out
    err = strip_ansi(err.strip())
    if len(expected_err) == 1:
        [expected_err] = expected_err
        assert err == expected_err
    else:
        assert err in expected_err


@pytest.mark.parametrize(
    "name,expected_out,expected_err",
    [
        ("variable", "17", "[<string>:5:7] <unknown> = 17"),
        (
            "multiple_arguments",
            "('hello', 8.5)",
            """
            [<string>:6:7] <unknown> = 'hello'
            [<string>:6:7] <unknown> = 8.5
            """,
        ),
        ("no_arguments", "()", "[<string>:3:7]"),
    ],
)
def test_run_from_exec(name: str, expected_out: str, expected_err, capsys: CaptureFixture) -> None:
    filepath = os.path.join(SAMPLE_DIR, *name.split("."))
    filepath += ".py"
    with open(filepath) as f:
        source = f.read()

    cwd = os.getcwd()
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        exec(source)

    expected_out = textwrap.dedent(expected_out).strip()
    expected_err = textwrap.dedent(expected_err).strip()

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert strip_ansi(err.strip()) == expected_err


@pytest.mark.parametrize(
    "name,expected_out,expected_err",
    [
        ("variable", "17", "[<unknown>] <unknown> = 17"),
        (
            "multiple_arguments",
            "('hello', 8.5)",
            """
                [<unknown>] <unknown> = 'hello'
                [<unknown>] <unknown> = 8.5
                """,
        ),
        ("no_arguments", "()", "[<unknown>]"),
    ],
)
def test_with_no_frames(name: str, expected_out: str, expected_err, capsys: CaptureFixture) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.{name}"
    with (
        mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))),
        mock.patch("inspect.currentframe", mock.Mock(return_value=None)),
    ):
        importlib.import_module(module)

    expected_out = textwrap.dedent(expected_out).strip()
    expected_err = textwrap.dedent(expected_err).strip()

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert strip_ansi(err.strip()) == expected_err


@pytest.mark.parametrize("style", ["github-dark", "default"])
def test_config_formatter_valid_style_and_background(style: str):
    CONFIG.style = style
    formatter = CONFIG._formatter
    assert isinstance(formatter, Terminal256Formatter)
    assert formatter.style.name == style


def test_config_style_changes_code_highlighting(capsys: CaptureFixture) -> None:
    module = f"{SAMPLE_DIR}.string"

    CONFIG.color = True
    CONFIG.style = "github-dark"
    importlib.import_module(module)

    out_1, err_1 = capsys.readouterr()

    del sys.modules[module]

    CONFIG.color = True
    CONFIG.style = "bw"
    importlib.import_module(module)

    out_2, err_2 = capsys.readouterr()

    assert out_1 == out_2
    assert strip_ansi(err_1.strip()) == strip_ansi(err_2.strip())
    assert err_1.strip() != err_2.strip()


def test_highlighting_avoided_with_ansi(capsys: CaptureFixture) -> None:
    cwd = os.getcwd()

    module = f"{SAMPLE_DIR}.colored_repr"
    with mock.patch("os.getcwd", mock.Mock(return_value=os.path.join(cwd, SAMPLE_DIR))):
        from debug import CONFIG

        CONFIG.color = True
        CONFIG.style = "solarized-dark"
        importlib.import_module(module)

    expected_out = "\x1b[40m\x1b[97m[0]\x1b[0m"
    expected_err = "[colored_repr.py:8:7] ColoredRepr() = \x1b[40m\x1b[97m[0]\x1b[0m"

    out, err = capsys.readouterr()
    assert out.strip() == expected_out
    assert strip_ansi(err.strip().split(" = ")[0]) == expected_err.split(" = ")[0]
    assert err.strip().split(" = ")[1] == expected_err.split(" = ")[1]


@pytest.mark.parametrize(
    "name, settings",
    [
        ("disabled", dict(color=False)),
        ("monokai", dict(style="monokai", color=True)),
        ("extra_section", dict(style="default", color=False)),
        ("unused_field", dict(style="default")),
        ("quotes", dict(style="algol")),
        ("syntax_error", dict()),
        ("location_error", dict()),
        ("empty", dict()),
        ("../debug/default", dict()),
        ("wide_indent", dict(indent=4)),
    ],
)
@pytest.mark.filterwarnings("ignore")
def test_load_config(name: str, settings: dict[str, Any]) -> None:
    config = DbgConfig()
    filename = os.path.join(TEST_DATA_DIR, name + ".conf")
    config._use_config(filename)

    expected_config = DbgConfig()
    for k, v in settings.items():
        setattr(expected_config, k, v)
    assert config == expected_config


@pytest.mark.parametrize(
    "name, warning_message",
    [
        (
            "extra_section",
            "Extra section [extra] found in $. "
            "Please, use no sections or one section called [dbg].",
        ),
        ("unused_field", "Unused field 'extra' found in $"),
        (
            "quotes",
            'Quotes used around "algol" in $. '
            "They will be ignored, but please remove to silence this warning.",
        ),
        ("wrong_section", "Wrong section [debugging] used in $. Please, use [dbg] or no sections."),
        ("syntax_error", "Unable to load config from $. (ParsingError)"),
        ("location_error", "Unable to load config from $. (FileNotFoundError)"),
    ],
)
def test_load_config_displays_warning(name: str, warning_message: str) -> None:
    config = DbgConfig()
    filename = os.path.join(TEST_DATA_DIR, name + ".conf")

    filename_msg = f"'{os.path.abspath(filename)}'"
    warning_regex = re.escape(warning_message.replace("$", filename_msg))
    with pytest.warns(match=warning_regex):
        config._use_config(filename)


def test_invalid_style_warns() -> None:
    config = DbgConfig()
    config.style = "monokai"

    with pytest.warns(match=r"Invalid style 'invalid'\. Choose one of .*\."):
        config.style = "invalid"

    assert config.style == "monokai"


def test_creates_default_config() -> None:
    temp_dir = tempfile.mkdtemp()
    config_filename = os.path.join(temp_dir, "debug", "dbg.conf")

    def user_config_dir(appname: str) -> str:
        return os.path.join(temp_dir, appname)

    with mock.patch("platformdirs.user_config_dir", user_config_dir):
        importlib.reload(sys.modules["debug._config"])
        from debug import dbg

        _ = dbg

    assert os.path.exists(config_filename)
    assert os.path.getsize(config_filename) > 0
    assert filecmp.cmp(config_filename, "debug/default.conf")


def test_loads_default_config() -> None:
    temp_dir = tempfile.mkdtemp()
    config_filename = os.path.join(temp_dir, "debug", "dbg.conf")
    os.mkdir(os.path.dirname(config_filename))
    with open(config_filename, "w") as f:
        f.write("style = fruity")

    def user_config_dir(appname: str) -> str:
        return os.path.join(temp_dir, appname)

    with mock.patch("platformdirs.user_config_dir", user_config_dir):
        importlib.reload(sys.modules["debug._config"])
        importlib.reload(sys.modules["debug._debug"])
        importlib.reload(sys.modules["debug"])
        from debug import CONFIG

    assert CONFIG.style == "fruity"


def test_loads_default_config_over_user_config() -> None:
    user_dir = tempfile.mkdtemp()
    user_config_filename = os.path.join(user_dir, "debug", "dbg.conf")
    os.mkdir(os.path.dirname(user_config_filename))
    with open(user_config_filename, "w") as f:
        f.write("style = fruity")

    current_dir = tempfile.mkdtemp()
    local_config_filename = os.path.join(current_dir, "dbg.conf")
    with open(local_config_filename, "w") as f:
        f.write("style = vim")

    def user_config_dir(appname: str) -> str:
        return os.path.join(user_dir, appname)

    with (
        mock.patch("platformdirs.user_config_dir", user_config_dir),
        mock.patch("os.getcwd", mock.Mock(return_value=current_dir)),
    ):
        importlib.reload(sys.modules["debug._config"])
        importlib.reload(sys.modules["debug._debug"])
        importlib.reload(sys.modules["debug"])
        from debug import CONFIG

    assert CONFIG.style == "vim"


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
        RESET = "\033[39m"
        self._string = "\n".join(
            [
                f"{color}{chr(i) * length}{RESET}"
                for i, length, color in zip(
                    range(ord("A"), ord("A") + len(lengths)),
                    lengths,
                    [Fore.RED, Fore.BLUE, Fore.GREEN],
                )
            ]
        )

    def __repr__(self) -> str:
        return self._string


recursive_list = []
recursive_list.append(recursive_list)

recursive_tree = []
recursive_tree.append(recursive_tree)
recursive_tree.append(recursive_tree)

recursive_dict = {}
recursive_dict[dict] = recursive_dict
recursive_dict[list] = recursive_list

recursive_multi_object_dict = {}
recursive_multi_object_list = []
recursive_multi_object_list.append(recursive_multi_object_dict)
recursive_multi_object_dict[0] = recursive_multi_object_list
recursive_multi_object_dict[1] = []

partial_recursive_object = (recursive_list, recursive_list)


@pytest.mark.parametrize(
    "obj, width, expected",
    [
        (10, None, "10"),
        (None, None, "None"),
        ("hello", None, "'hello'"),
        ("hello", 7, "'hello'"),
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
        (
            {"a", "b"},
            10,
            ["{'a', 'b'}", "{'b', 'a'}"],
        ),
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
        (
            set(),
            None,
            "{}",
        ),
        (
            (),
            None,
            "()",
        ),
        (
            (100,),
            None,
            "(100,)",
        ),
        (
            (100,),
            6,
            "(100,)",
        ),
        (
            (100,),
            5,
            """
            (
                100,
            )
            """,
        ),
        (
            ("a", "b"),
            None,
            "('a', 'b')",
        ),
        (
            ("a", "b"),
            10,
            "('a', 'b')",
        ),
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
        (
            {},
            None,
            "{}",
        ),
        (
            set(),
            1,
            "{}",
        ),
        (
            {},
            1,
            "{}",
        ),
        (
            {"a": 50, "b": 5},
            None,
            "{'a': 50, 'b': 5}",
        ),
        (
            {"a": 50, "b": 5},
            17,
            "{'a': 50, 'b': 5}",
        ),
        (
            {"a": 50, "b": 5},
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
            {"a": MultilineObject([3, 1, 3])},
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
            {"a": MultilineObject([3, 3]), "aa": MultilineObject([2, 1])},
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
        ({1: {"a": {}}, 2: {"b": {}, "c": []}}, None, "{1: {'a': {}}, 2: {'b': {}, 'c': []}}"),
        ({1: {"a": {}}, 2: {"b": {}, "c": []}}, 37, "{1: {'a': {}}, 2: {'b': {}, 'c': []}}"),
        (
            {1: {"a": {}}, 2: {"b": {}, "c": []}},
            36,
            """
            {
                1: {'a': {}},
                2: {'b': {}, 'c': []},
            }
            """,
        ),
        (
            {1: {"a": {}}, 2: {"b": {}, "c": []}},
            26,
            """
            {
                1: {'a': {}},
                2: {'b': {}, 'c': []},
            }
            """,
        ),
        (
            {1: {"a": {}}, 2: {"b": {}, "c": []}},
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
            {1: {"a": {}}, 2: {"b": {}, "c": []}},
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
            {1: {"a": {}}, 2: {"b": {}, "c": []}},
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
            {1: {"a": {}}, 2: {"b": {}, "c": []}},
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
                1: {"a": MultilineObject([2, 2])},
                2: {"b": MultilineObject([2, 2]), "c": MultilineObject([2, 2])},
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
                1: {"a": MultilineObject([2, 2])},
                2: {"b": MultilineObject([2, 2]), "c": MultilineObject([2, 2])},
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
        (
            ColoredMultilineObject([2, 2, 2]),
            None,
            """
            \x1b[31mAA\x1b[39m
            \x1b[34mBB\x1b[39m
            \x1b[32mCC\x1b[39m
            """,
        ),
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
    ],
)
def test_format(obj: Any, width: int | None, expected: list | str) -> None:
    config = FormatterConfig(_terminal_width=width, _indent_width=4)
    formatter = Formatter(config)
    string = formatter.format(obj, initial_width=0)
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
    config = FormatterConfig(_terminal_width=width, _indent_width=4)
    formatter = Formatter(config)
    string = (initial_width - 1) * "*" + "_" + formatter.format(obj, initial_width=initial_width)
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
