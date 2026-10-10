"""Shared fixtures."""
from __future__ import annotations

import pytest

from cognitive_mirror.config import load_settings
from cognitive_mirror.engine.lexicons import load_lexicon
from cognitive_mirror.service import Service
from cognitive_mirror.store import Store


@pytest.fixture()
def settings():
    return load_settings({"CM_DB_PATH": ":memory:"})


@pytest.fixture()
def lex():
    return load_lexicon()


@pytest.fixture()
def store():
    return Store(":memory:")


@pytest.fixture()
def svc(settings, store, lex):
    return Service(settings, store, lex)
