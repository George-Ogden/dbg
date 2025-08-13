from debug import dbg


class ColoredRepr:
    def __repr__(self) -> str:
        return "\x1b[40m\x1b[97m[0]\x1b[0m"

print(dbg(ColoredRepr()))
