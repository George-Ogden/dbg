from typing import Callable

from debug import dbg


def add(a: int) -> Callable[[int], int]:
    def adder(b: int) -> int:
        return dbg(a) + dbg(b)

    return adder


print(add(2)(6))
