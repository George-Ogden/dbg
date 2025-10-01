import inspect
import os.path
import re
import types
from typing import TypeAlias

from pygments.token import Token

from ._code import UNKNOWN_MESSAGE
from ._config import CONFIG

Position: TypeAlias = tuple[str, None | tuple[int, None | int]]


def get_position(frame: None | types.FrameType) -> Position:
    if frame is None:
        return (UNKNOWN_MESSAGE, None)
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
