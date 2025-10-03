import sys

from debug import dbg


class StatefulRepr:
    def __repr__(self) -> str:
        print("stdout")
        print("stderr", file=sys.stderr)
        return "repr"


dbg(StatefulRepr())
