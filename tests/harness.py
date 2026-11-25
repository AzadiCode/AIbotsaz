# -*- coding: utf-8 -*-
"""
harness.py — شبیه‌ساز بدونِ تلگرام برای موتور (engine.py)

هدف: تست پذیرش قابلیت‌های کاتالوگ «روی موتور واقعی» اجرا شود؛ دکمه واقعی بزنیم
(callback مثل خود تلگرام به /hook/<bot_id> می‌رسد) و تغییر متغیر/ارسال پیام را ببینیم.

  • db واقعی core در حالت حافظه‌ای (mongomock) — هیچ شبکه‌ای زده نمی‌شود.
  • tg جعل می‌شود: همه‌ی فراخوانی‌های تلگرام ثبت می‌شوند؛ sendDice مقدار قابل‌تنظیم برمی‌گرداند.
  • time.sleep حذف می‌شود (انیمیشن تاس در تست لازم نیست).

استفاده (از ریشه‌ی پروژه):
  python tests/test_catalog.py
  python tests/test_modules.py
"""

import os
import sys
import time as _time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_ENV = {
    "MOTHER_TOKEN": "12:test_mother",
    "BASE_URL": "https://test.example",
    "AI_BASE_URL": "https://test.example/v1",
    "AI_API_KEY": "test-key",
    "AI_MODEL": "test-model",
    "PAYMENTS": "0",
    "MONGO_URI": "",
    "SECRET_KEY": "test-secret",
}
for k, v in _ENV.items():
    os.environ.setdefault(k, v)


class _Sent(list):
    """فراخوانی‌های تلگرام: (method, kwargs) — خواندنی برای ادعاهای تست."""

    dice_value = 6            # مقدار تاسِ جعلی (sendDice)

    def call(self, token, method, **kw):
        self.append((method, kw))
        if method == "sendDice":
            return {"ok": True, "result": {"message_id": 1, "dice": {"value": int(self.dice_value)}}}
        if method == "getChatMember":
            return {"ok": True, "result": {"status": "member"}}
        if method == "getMe":
            return {"ok": True, "result": {"id": 1, "is_bot": True, "first_name": "bot", "username": "test_bot"}}
        return {"ok": True, "result": {"message_id": 1}}


SENT = _Sent()


class _FakeTime:
    """time.sleep را حذف می‌کند؛ بقیه‌ی رفتار time واقعی می‌ماند."""

    @staticmethod
    def time():
        return _time.time()

    @staticmethod
    def monotonic():
        return _time.monotonic()

    @staticmethod
    def sleep(sec):
        # انیمیشن/زمان‌بند در تست لازم نیست؛ خواب کوتاه برای جلوگیری از چرخش CPU
        _time.sleep(min(float(sec), 0.02)) if sec and sec > 0 else None
        return None


_ENGINE = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        import core
        import engine
        core.tg = SENT.call
        engine.tg = SENT.call
        engine.time = _FakeTime
        import app  # noqa: F401  — مثل پروداکشن: ثبت همه‌ی مسیرها (games/webapp/...) پیش از اولین درخواست
        _ENGINE = engine
    return _ENGINE


class Sim:
    """یک کاربرِ ساختگی داخل یک ربات ساختگی؛ updateها مثل تلگرام به هوک می‌روند."""

    _mid = 1000

    def __init__(self, cfg, name="ربات تست", username="test_bot"):
        import core
        from bson import ObjectId
        self.engine = get_engine()
        self.db = core.db
        self.uid = 555001
        self.bot_id = str(ObjectId())
        self.secret = "test-secret"
        token = "12:abc" + self.bot_id[-6:]
        self.db.bots.insert_one({
            "_id": ObjectId(self.bot_id), "owner": self.uid, "active": True,
            "name": name, "username": username, "secret": self.secret,
            "token_enc": core.enc(token), "token_hash": core.thash(token), "config": cfg,
        })
        self.client = core.app.test_client()
        self.user = {"id": self.uid, "is_bot": False, "first_name": "تست", "username": "tester",
                     "language_code": "fa"}

    # ── ارسال آپدیت واقعی به هوک (همان مسیر پروداکشن) ──
    def _post(self, upd):
        SENT.clear()
        r = self.client.post(f"/hook/{self.bot_id}", json=upd,
                             headers={"X-Telegram-Bot-Api-Secret-Token": self.secret})
        assert r.status_code == 200, f"hook failed: {r.status_code} {r.data[:200]}"
        return r

    def send(self, text):
        Sim._mid += 1
        return self._post({"update_id": Sim._mid, "message": {
            "message_id": Sim._mid, "from": self.user, "chat": {"id": self.uid, "type": "private"}, "text": text}})

    def start(self):
        return self.send("/start")

    def _callback_data(self, node_id, row, col):
        """همان منطق keyboard() موتور برای ساختن callback_data یک دکمه."""
        b = self.cfg()["nodes"][node_id]["buttons"][row][col]
        if "goto" in b:
            return f"g:{node_id}:{row}:{col}" if (b.get("do") or b.get("join")) else f"n:{b['goto']}"
        if "alert" in b:
            return f"a:{node_id}:{row}:{col}"
        return None

    def press(self, node_id, row, col):
        data = self._callback_data(node_id, row, col)
        assert data, "این دکمه callback ندارد (url/copy است؟)"
        Sim._mid += 1
        return self._post({"update_id": Sim._mid, "callback_query": {
            "id": str(Sim._mid), "from": self.user, "data": data,
            "message": {"message_id": Sim._mid - 1, "chat": {"id": self.uid, "type": "private"}, "text": "."}}})

    def press_label(self, node_id, label):
        """دکمه‌ای با این متن در این بخش پیدا کن و بزنش."""
        rows = self.cfg()["nodes"][node_id].get("buttons") or []
        for ri, row in enumerate(rows):
            for ci, b in enumerate(row):
                if isinstance(b, dict) and str(b.get("text", "")).strip() == label.strip():
                    return self.press(node_id, ri, ci)
        raise AssertionError(f"دکمه «{label}» در بخش {node_id} پیدا نشد؛ دکمه‌ها: "
                             f"{[b.get('text') for r in rows for b in r]}")

    def buttons(self, node_id):
        return [b.get("text") for r in (self.cfg()["nodes"][node_id].get("buttons") or []) for b in r]

    # ── خواندن وضعیت ──
    def _oid(self):
        from bson import ObjectId
        return ObjectId(self.bot_id)

    def cfg(self):
        return self.db.bots.find_one({"_id": self._oid()})["config"]

    def vars(self):
        doc = self.db.uvars.find_one({"_id": f"{self.bot_id}:{self.uid}"}) or {}
        return {k: str(v) for k, v in (doc.get("v") or {}).items()}

    def var(self, k):
        v = self.vars().get(k)
        if v is not None:
            return v
        # مثل Env.get: مقدار پیش‌فرضِ اعلان‌شدهٔ کانفیگ
        return str((self.cfg().get("vars") or {}).get(k, ""))

    def sent_texts(self):
        return [str(kw.get("text") or kw.get("caption") or "") for m, kw in SENT if m in ("sendMessage", "editMessageText")]

    def sent_methods(self):
        return [m for m, _ in SENT]

    def last_text(self):
        texts = self.sent_texts()
        return texts[-1] if texts else ""
