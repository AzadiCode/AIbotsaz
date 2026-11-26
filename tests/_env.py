# -*- coding: utf-8 -*-
"""tests/_env.py — بوت‌استرپ محیط تست: متغیرهای الزامی قبل از importهای پروژه."""
import os

_DEFAULTS = {
    "MOTHER_TOKEN": "test-token",
    "BASE_URL": "https://test.local",
    "AI_BASE_URL": "https://ai.test.local",
    "AI_API_KEY": "test-key",
    "AI_MODEL": "test-model",
    "MONGO_URI": "",            # خالی = mongomock در core
    "AI_MODULES": "1",
}
for k, v in _DEFAULTS.items():
    os.environ.setdefault(k, v)
