import builtins
from collections.abc import Generator
import contextlib
import os
from pathlib import Path
import sys
from unittest import mock

import pytest

SAMPLE_DIR = "test_samples"
TEST_DATA_DIR = "test_data"


@pytest.fixture(autouse=True)
def reset_modules() -> None:
    for key in list(sys.modules.keys()):
        if key.startswith(SAMPLE_DIR):
            del sys.modules[key]


@pytest.fixture
def test_sample_dir() -> Generator[None]:
    os.chdir(Path.cwd() / SAMPLE_DIR)
    with mock.patch("_debug.position.cwd", Path.cwd()):  # type: ignore [name-defined]
        yield
    os.chdir(Path.cwd() / "..")


@pytest.fixture(autouse=True)
def uninstall_from_builtins() -> Generator[None]:
    assert not hasattr(builtins, "dbg")
    yield
    with contextlib.suppress(AttributeError):
        delattr(builtins, "dbg")
