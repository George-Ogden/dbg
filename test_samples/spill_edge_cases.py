from debug import dbg

print(dbg(*()))

xs = [1, 2, 3]
print(dbg(*xs, 4))
print(dbg(4, *reversed(xs)))
print(dbg(*xs, *reversed(xs)))
print(dbg(*xs, 4, *reversed(xs)))
print(dbg(4, *reversed(xs), *xs, 4))
