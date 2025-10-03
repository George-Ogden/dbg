import sys

import pytest

SAMPLE_DIR = "test_samples"
TEST_DATA_DIR = "test_data"


@pytest.fixture(autouse=True)
def reset_modules() -> None:
    for key in list(sys.modules.keys()):
        if key.startswith(SAMPLE_DIR):
            del sys.modules[key]
