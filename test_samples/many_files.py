import sys
import tempfile

from debug import pprint

pprint("stdout", file=sys.stdout, conversion="repr")
pprint("stderr", file=sys.stderr, conversion="repr")

_, filename = tempfile.mkstemp()
with open(filename, "w") as f:
    pprint("tempfile", file=f, color="auto", conversion="repr")


class StatefulRepr:
    def __repr__(self) -> str:
        pprint("stdout", conversion="repr")
        pprint("stderr", file=sys.stderr, conversion="repr")
        return "repr"


pprint(StatefulRepr(), file=sys.stdout, conversion="repr")
pprint(StatefulRepr(), file=sys.stderr, conversion="repr")
