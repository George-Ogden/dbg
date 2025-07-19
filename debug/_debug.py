import ast
import inspect
import os.path
import sys


def dbg[T](expr: T, /) -> T:
    frame = inspect.currentframe()
    frame = frame.f_back
    try:
        traceback = inspect.getframeinfo(frame, context=0)
        filename = traceback.filename
        with open(filename) as f:
            lines = f.readlines()
        positions = traceback.positions
        lineno = traceback.lineno - 1
        if positions.lineno == positions.end_lineno:
            source = lines[lineno][positions.col_offset : positions.end_col_offset]
        else:
            source = lines[lineno][positions.col_offset :]
            end_lineno = positions.end_lineno - 1
            lineno += 1
            while lineno < end_lineno:
                source += lines[lineno]
                lineno += 1
            source += lines[lineno][: positions.end_col_offset]
        tree: ast.Expression = ast.parse(source, mode="eval")
        fn_call: ast.Call = tree.body
        [arg] = fn_call.args
        code = ast.unparse(arg)
        basename = os.path.basename(filename)
        print(f"[{basename}:{frame.f_lineno}] {code} = {expr}", file=sys.stderr)
    finally:
        del frame
    return expr
