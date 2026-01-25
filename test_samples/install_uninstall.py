import contextlib

from debug import install, uninstall

install()

print(dbg("success"))

uninstall()

with contextlib.suppress(NameError):
    print(dbg("failure"))
