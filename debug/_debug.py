import ast
import inspect
import os.path
import re
import sys
import types
from typing import Any, TypeVar, TypeVarTuple, Unpack, overload

import black

UNKNOWN_MESSAGE: str = "<unknown>"


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


def display_codes(frame: None | types.FrameType, *, num_codes: int) -> list[str]:
    if frame is None:
        source = None
    else:
        source = get_source(frame)
    if source is None:
        return [UNKNOWN_MESSAGE] * num_codes
    source = black.format_str(
        source, mode=black.FileMode(string_normalization=False, line_length=len(source))
    )
    tree: ast.Expression = ast.parse(source, mode="eval")
    assert isinstance(tree.body, ast.Call)
    fn_call = tree.body
    codes = [
        ast.get_source_segment(source=source, node=arg) or UNKNOWN_MESSAGE for arg in fn_call.args
    ]
    return codes


def get_position(frame: types.FrameType) -> tuple[str, None | int]:
    filepath = frame.f_code.co_filename
    if re.match(r"<.*>", filepath):
        path = filepath
    else:
        root = os.getcwd()
        path = os.path.relpath(filepath, start=root)
    lineno = frame.f_lineno
    return path, lineno


def display_position(frame: None | types.FrameType) -> str:
    if frame is None:
        return UNKNOWN_MESSAGE
    filepath, lineno = get_position(frame)
    if lineno is None:
        return filepath
    return f"{filepath}:{lineno}"


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
            print(f"[{position}]", file=sys.stderr)
        else:
            codes = display_codes(frame, num_codes=num_args)
            for code, value in zip(codes, values, strict=True):
                print(f"[{position}] {code} = {value!r}", file=sys.stderr)
    finally:
        del frame
    if len(values) == 1:
        [value] = values
        return value
    else:
        return values
