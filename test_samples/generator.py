import itertools
from debug import dbg


def gen():
    return (
        None for _ in itertools.count() if dbg(True)
    )


print(next(gen()))
