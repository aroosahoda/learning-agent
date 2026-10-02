import pytest

from modules.config import Config
from modules.state.paths import AlvarPaths


@pytest.fixture
def paths(tmp_path):
    p = AlvarPaths.for_project(tmp_path)
    p.init()
    return p


@pytest.fixture
def cfg():
    return Config()
