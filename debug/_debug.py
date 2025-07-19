import ast
import inspect
import os.path
import sys
import types


def get_source(frame: types.FrameType) -> None | str:
    lines, offset = inspect.getsourcelines(frame)
    traceback = inspect.getframeinfo(frame, context=0)
    positions = traceback.positions
    lineno = traceback.lineno - 1
    if positions.lineno == positions.end_lineno:
        source = lines[lineno - offset][positions.col_offset : positions.end_col_offset]
    else:
        source = lines[lineno - offset][positions.col_offset :]
        end_lineno = positions.end_lineno - 1
        lineno += 1
        while lineno < end_lineno:
            source += lines[lineno - offset]
            lineno += 1
        source += lines[lineno - offset][: positions.end_col_offset]
    return source


def get_code(frame: types.FrameType) -> None | str:
    source = get_source(frame)
    tree: ast.Expression = ast.parse(source, mode="eval")
    fn_call: ast.Call = tree.body
    [arg] = fn_call.args
    code = ast.unparse(arg)
    return code


def get_position(frame: types.FrameType) -> None | tuple[str, None] | tuple[str, int]:
    filepath = inspect.getsourcefile(frame)
    lineno = frame.f_lineno
    return os.path.basename(filepath), lineno


def dbg[T](expr: T, /) -> T:
    frame = inspect.currentframe()
    frame = frame.f_back
    try:
        code = get_code(frame)
        filepath, lineno = get_position(frame)
        print(f"[{filepath}:{lineno}] {code} = {expr}", file=sys.stderr)
    finally:
        del frame
    return expr
