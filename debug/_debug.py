import inspect
import os.path
import re
import sys
import types
from typing import TypeAlias, TypeVar, TypeVarTuple, Unpack, overload

from pygments.token import Token

from ._code import display_codes
from ._config import CONFIG
from ._format import BaseFormat, Formatter, FormatterConfig

Position: TypeAlias = tuple[str, None | tuple[int, None | int]]


def get_position(frame: None | types.FrameType) -> Position:
    if frame is None:
        return (CONFIG._unknown_message, None)
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
    if CONFIG.color:
        on, off = CONFIG._formatter.style_string[str(Token.Comment.Single)]
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


def dbg(*values: object) -> object:
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
            formatter_config = FormatterConfig._from_config(CONFIG)
            formatter = Formatter(formatter_config)
            for code, value in zip(codes, values, strict=True):
                prefix = f"{position} {code} = "
                *_, last_line = prefix.rsplit("\n", maxsplit=1)
                print(
                    prefix + formatter.format(value, initial_width=BaseFormat.len(last_line)),
                    file=sys.stderr,
                )
    finally:
        del frame
    if len(values) == 1:
        [value] = values
        return value
    else:
        return values
