import sys
import tempfile

from debug import pprint

pprint("stdout", file=sys.stdout)
pprint("stderr", file=sys.stderr)

_, filename = tempfile.mkstemp()
with open(filename, "w") as f:
    pprint("tempfile", file=f, color="auto")


class StatefulRepr:
    def __repr__(self) -> str:
        pprint("stdout")
        pprint("stderr", file=sys.stderr)
        return "repr"

pprint(StatefulRepr(), file=sys.stdout)
pprint(StatefulRepr(), file=sys.stderr)
