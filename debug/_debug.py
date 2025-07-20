import ast
import inspect
import os.path
import re
import sys
import types

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


def display_code(frame: None | types.FrameType) -> None | str:
    if frame is None:
        source = None
    else:
        source = get_source(frame)
    if source is None:
        return UNKNOWN_MESSAGE
    tree: ast.Expression = ast.parse(source, mode="eval")
    assert isinstance(tree.body, ast.Call)
    fn_call = tree.body
    [arg] = fn_call.args
    code = ast.unparse(arg)
    return code


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


def dbg[T](expr: T, /) -> T:
    frame = inspect.currentframe()
    if frame is not None:
        frame = frame.f_back
    try:
        code = display_code(frame)
        position = display_position(frame)
        print(f"[{position}] {code} = {expr!r}", file=sys.stderr)
    finally:
        del frame
    return expr
