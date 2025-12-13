import os
from pathlib import Path

from debug import dbg

cwd = Path.cwd()
os.chdir(cwd / "..")
print(dbg(os.path.relpath(__file__)))
os.chdir(cwd)
