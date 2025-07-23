from collections.abc import Iterable
from dataclasses import dataclass
import inspect
import os.path
import re
import sys
import types
from typing import Any, ClassVar, TypeVar, TypeVarTuple, Unpack, overload

import black
import libcst as cst
import pygments
from pygments.formatters import Terminal256Formatter
from pygments.lexers import PythonLexer
from pygments.token import Token

type Position = tuple[str, None | tuple[int, None | int]]


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


def get_source(frame: types.FrameType) -> None | str:
    try:
        lines, offset = inspect.getsourcelines(frame)
        offset = max(offset, 1)
    except OSError:
        return None
    traceback = inspect.getframeinfo(frame, context=0)
    positions = traceback.positions
    if positions is None:
        return None
    lineno = traceback.lineno - offset
    if positions.lineno is None or positions.end_lineno is None:
        return None
    if positions.lineno == positions.end_lineno:
        source = lines[lineno][positions.col_offset : positions.end_col_offset]
    else:
        source = lines[lineno][positions.col_offset :]
        end_lineno = positions.end_lineno - offset
        lineno += 1
        while lineno < end_lineno:
            source += lines[lineno]
            lineno += 1
        source += lines[lineno][: positions.end_col_offset]
    return source


def highlight_code(code: str) -> str:
    if not supports_color():
        return code
    lexer = PythonLexer()
    formatter = CONFIG.formatter
    code = pygments.highlight(code, lexer, formatter).strip()
    return code


def format_code(code: str) -> str:
    return black.format_str(
        code, mode=black.FileMode(string_normalization=False, line_length=len(code))
    )


def display_code(code: str) -> str:
    return highlight_code(format_code(code))


def get_source_segments(source: str) -> None | Iterable[str]:
    source = format_code(source)
    tree = cst.parse_expression(source)
    module = cst.Module([])
    if not isinstance(tree, cst.Call):
        return None
    args = [
        module.code_for_node(arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)) for arg in tree.args
    ]
    return args


def display_codes(frame: None | types.FrameType, *, num_codes: int) -> list[str]:
    if frame is None:
        source = None
    else:
        source = get_source(frame)
    if source is None:
        return [CONFIG.unknown_message] * num_codes
    source_segments = get_source_segments(source)
    if source_segments is None:
        return [CONFIG.unknown_message] * num_codes
    codes = [highlight_code(source_segment) for source_segment in (source_segments)]
    return codes


def get_position(frame: None | types.FrameType) -> Position:
    if frame is None:
        return (CONFIG.unknown_message, None)
    filepath = frame.f_code.co_filename
    if re.match(r"<.*>", filepath):
        path = filepath
    else:
        root = os.getcwd()
        path = os.path.relpath(filepath, start=root)
    traceback = inspect.getframeinfo(frame, context=0)
    positions = traceback.positions
    if positions is None or positions.lineno is None:
        lineno = frame.f_lineno
        return path, (lineno, None)
    col = positions.col_offset
    if col is not None:
        col += 1
    return path, (positions.lineno, col)


def format_position(position: Position) -> str:
    filepath, location = position
    if location is None:
        return filepath
    lineno, col = location
    if col is None:
        return f"{filepath}:{lineno}"
    else:
        return f"{filepath}:{lineno}:{col}"


def highlight_position(position: str) -> str:
    position = f"[{position}]"
    if supports_color():
        on, off = CONFIG.formatter.style_string[str(Token.Comment.Single)]
        position = on + position + off
    return position


def display_position(frame: None | types.FrameType) -> str:
    position = get_position(frame)
    return highlight_position(format_position(position))


T = TypeVar("T")
Ts = TypeVarTuple("Ts")


@overload
def dbg(value: T, /) -> T: ...


@overload
def dbg(*values: Unpack[Ts]) -> tuple[Unpack[Ts]]: ...


def dbg(*values: Any) -> Any:
    """Write an appropriate debugging message to the stderr for each expression.
    The value is returned (one argument)
    or values are returned as a tuple (zero or multiple arguments).
    """
    num_args = len(values)
    frame = inspect.currentframe()
    if frame is not None:
        frame = frame.f_back
    try:
        position = display_position(frame)
        if num_args == 0:
            print(position, file=sys.stderr)
        else:
            codes = display_codes(frame, num_codes=num_args)
            for code, value in zip(codes, values, strict=True):
                print(f"{position} {code} = {highlight_code(repr(value))}", file=sys.stderr)
    finally:
        del frame
    if len(values) == 1:
        [value] = values
        return value
    else:
        return values
