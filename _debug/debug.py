import inspect
import sys
from typing import TypeVar, TypeVarTuple, overload

from .code import display_codes
from .config import CONFIG
from .file import FileWrapper
from .format import pprint
from .position import display_position

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
        with FileWrapper.lock(sys.stderr) as file_wrapper:
            style = CONFIG.style if file_wrapper.supports_color else None
            position = display_position(frame, style=style)
            if num_args == 0:
                print(position, file=sys.stderr)
            else:
                codes = display_codes(frame, num_codes=num_args, style=style)
                for (code, symbol), value in zip(codes, values, strict=True):
                    prefix = f"{position} {code} {symbol} "
                    pprint(
                        value,
                        prefix=prefix,
                        style="config",
                        indent="config",
                        width="auto",
                        file="upper",  # type: ignore
                    )
    finally:
        del frame
    if len(values) == 1:
        [value] = values
        return value
    return values
