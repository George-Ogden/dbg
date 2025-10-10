import inspect
import os.path
import re
import types
from typing import TypeAlias

from .code import UNKNOWN_MESSAGE, highlight_text

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
        position_text = filepath
    else:
        lineno, col = location
        position_text = f"{filepath}:{lineno}" if col is None else f"{filepath}:{lineno}:{col}"
    return f"[{position_text}]"


def highlight_position(position: str, style: str) -> str:
    return highlight_text(position, style)


def display_position(frame: None | types.FrameType, style: str | None) -> str:
    position = get_position(frame)
    position_text = format_position(position)
    if style is not None:
        position_text = highlight_position(position_text, style)
    return position_text
