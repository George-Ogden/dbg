from debug import dbg

print(dbg([
    8,9,10
]))

print(dbg([
    8,9,10,
]))

class MultilineObject:
    def __repr__(self) -> str:
        return "A\nB"

print(dbg([MultilineObject(), "A\nB"]))

print(dbg([1,2,3]))
