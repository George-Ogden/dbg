import inspect
import sys
from typing import TypeVar, TypeVarTuple, overload

from ._code import display_codes
from ._config import CONFIG
from ._format import pformat
from ._position import display_position

T = TypeVar("T")
Ts = TypeVarTuple("Ts")


@overload
def dbg(value: T, /) -> T: ...


@overload
def dbg(*values: *Ts) -> tuple[*Ts]: ...


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
            codes = display_codes(frame, num_codes=num_args, style=CONFIG.style)
            if CONFIG.color:
                style = CONFIG.style
            else:
                style = None
            for (code, symbol), value in zip(codes, values, strict=True):
                prefix = f"{position} {code} {symbol} "
                print(
                    pformat(
                        value,
                        prefix=prefix,
                        style=style,
                        indent=CONFIG.indent,
                        width=CONFIG._get_terminal_width(),
                    ),
                    file=sys.stderr,
                )
    finally:
        del frame
    if len(values) == 1:
        [value] = values
        return value
    else:
        return values
