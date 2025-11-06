from collections.abc import Iterable
import functools
import inspect
import re
import textwrap
import token
import tokenize
import types

import black
import libcst as cst
import pygments
from pygments.formatters import Terminal256Formatter
from pygments.lexers import PythonLexer
from pygments.styles import get_all_styles, get_style_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

UNKNOWN_MESSAGE = "<unknown>"


@functools.cache
def validate_style(style: str) -> None:
    try:
        get_style_by_name(style)
    except ClassNotFound:
        all_styles = list(get_all_styles())
        raise ValueError(f"Unknown style {style!r}. Please, choose one of {all_styles}.") from None


@functools.cache
def get_formatter(style: str) -> Terminal256Formatter:
    return Terminal256Formatter(style=style, noitalic=True, nobold=True, nounderline=True)


def highlight_text(text: str, style: str) -> str:
    formatter = get_formatter(style)
    on, off = formatter.style_string[str(Token.Comment.Single)]
    return on + text + off


def highlight_code(code: str, style: str) -> str:
    lexer = PythonLexer()
    if code is UNKNOWN_MESSAGE:
        code = highlight_text(code, style)
    else:
        formatter = get_formatter(style)
        code = pygments.highlight(code, lexer, formatter).strip()
    return code


def format_code(code: str) -> str:
    if code is UNKNOWN_MESSAGE:
        return code
    lines = (line for line in code.splitlines() if line)
    toks = tokenize.generate_tokens(functools.partial(next, iter(lines)))
    code = "".join(tok.string for tok in toks if tok.type != token.COMMENT)
    black_formatted_code = black.format_str(
        f"({code})",
        mode=black.FileMode(string_normalization=False, line_length=len(code) * 2 + 2),
    ).strip()
    match = re.match(r"^\((.*)\)$", black_formatted_code, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        return black_formatted_code
    return textwrap.dedent(match.group(1)).strip()


@functools.lru_cache
def display_code(code: str, style: str | None) -> str:
    code = format_code(code)
    if style is not None:
        code = highlight_code(code, style=style)
    return code


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


def add_symbol_to_source_segments(
    segments: list[str], num_codes: int
) -> None | list[tuple[str, str]]:
    low_correct_index = -1
    for i, segment in enumerate(segments):
        if segment.startswith("*"):
            break
        low_correct_index = i
    else:
        if num_codes != len(segments):
            return None
    high_correct_index = 0
    for i, segment in enumerate(reversed(segments), 1):
        if segment.startswith("*"):
            break
        high_correct_index = i
    unmapped_code = ", ".join(segments[low_correct_index + 1 : len(segments) - high_correct_index])
    return [
        (segments[i], "=")
        if i <= low_correct_index
        else (
            (segments[i - num_codes], "=")
            if num_codes - i <= high_correct_index
            else (unmapped_code, "->")
        )
        for i in range(num_codes)
    ]


def display_codes(
    frame: None | types.FrameType, *, num_codes: int, style: str | None
) -> list[tuple[str, str]]:
    """Return code and symbols used to represent it."""
    unknown_codes = [(display_code(UNKNOWN_MESSAGE, style), "=")] * num_codes
    if frame is None:
        return unknown_codes
    source = get_source(frame)
    if source is None:
        return unknown_codes
    source_segments = get_source_segments(source)
    if source_segments is None:
        return unknown_codes
    symbol_segments = add_symbol_to_source_segments(list(source_segments), num_codes)
    if symbol_segments is None:
        return unknown_codes
    return [(display_code(code, style), symbol) for (code, symbol) in symbol_segments]
