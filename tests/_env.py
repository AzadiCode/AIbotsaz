# -*- coding: utf-8 -*-
"""Test-only environment defaults; no production settings are changed."""
import os

_DEFAULTS = {
    "MOTHER_TOKEN": "test-token",
    "BASE_URL": "https://test.local",
    "AI_BASE_URL": "https://ai.test.local",
    "AI_API_KEY": "test-key",
    "AI_MODEL": "test-model",
    "MONGO_URI": "",  # Empty URI selects mongomock in core.
    "AI_MODULES": "1",
}
for _key, _value in _DEFAULTS.items():
    os.environ.setdefault(_key, _value)
