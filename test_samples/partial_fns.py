import functools

from debug import dbg

d = functools.partial(dbg)
print(d(0))

d = functools.partial(dbg, 10, 20, 30)
print(d())

d = functools.partial(dbg, 0)
print(d(*[1, 2, 3]))


d = functools.partial(dbg, 0)
print(d(1, *[2, 3]))
