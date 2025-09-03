from collections.abc import Iterable
import inspect
import re
import textwrap
import types

import black
import libcst as cst
import pygments
from pygments.lexers import PythonLexer

from ._config import CONFIG


def highlight_code(code: str) -> str:
    if not CONFIG.color:
        return code
    lexer = PythonLexer()
    formatter = CONFIG._formatter
    code = pygments.highlight(code, lexer, formatter).strip()
    return code


def format_code(code: str) -> str:
    code = code.replace(",", " , ")
    black_formatted_code = black.format_str(
        f"({' '.join(code.strip().splitlines())})",
        mode=black.FileMode(string_normalization=False, line_length=len(code) + 2),
    ).strip()
    match = re.match(r"^\((.*)\)$", black_formatted_code, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        return black_formatted_code
    return textwrap.dedent(match.group(1)).strip()


def display_code(code: str) -> str:
    return highlight_code(format_code(code))


def get_source_segments(source: str) -> None | Iterable[str]:
    tree = cst.parse_expression(source)
    module = cst.Module([])
    if not isinstance(tree, cst.Call):
        return None
    args = [
        module.code_for_node(arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)) for arg in tree.args
    ]
    return args


def get_source(frame: types.FrameType) -> None | str:
    try:
        lines, offset = inspect.getsourcelines(frame)
    except OSError:
        return None
    offset = max(offset, 1)
    traceback = inspect.getframeinfo(frame, context=0)
    positions = traceback.positions
    if positions is None:
        return None
    lineno = traceback.lineno - offset
    if positions.lineno is None or positions.end_lineno is None:
        return None
    try:
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
    except IndexError:
        # Edge case caused by `inspect` bug.
        return None
    return source


def display_codes(frame: None | types.FrameType, *, num_codes: int) -> list[str]:
    if frame is None:
        source = None
    else:
        source = get_source(frame)
    if source is None:
        return [CONFIG._unknown_message] * num_codes
    source_segments = get_source_segments(source)
    if source_segments is None:
        return [CONFIG._unknown_message] * num_codes
    codes = [display_code(source_segment) for source_segment in (source_segments)]
    return codes
