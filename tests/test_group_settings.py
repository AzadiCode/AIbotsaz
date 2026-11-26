# -*- coding: utf-8 -*-
"""تست‌های هدفمند تنظیمات مستقل گروه و طبقه‌بندی کاتالوگ."""
import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._env  # noqa: F401
import core


def test_group_manager_contract():
    import coverage
    d = coverage.classify_uncovered({"id": "r1", "want": "مدیریت گروه در محیط گروه",
                                     "part": "گروه", "status": "catalog_missing"})
    assert d["kind"] == "BUILD_DEFECT", d
    assert d["feature"] == "group_manager", d
    group_prompt = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه انجام داد"
    dm = coverage.classify_uncovered({"id": "r2", "want": "تنظیمات ربات در پیوی",
                                      "part": "تنظیمات خصوصی گروه", "status": "catalog_missing"},
                                     prompt=group_prompt)
    assert dm["kind"] == "BUILD_DEFECT" and dm["feature"] == "group_manager", dm
    unknown = coverage.classify_uncovered({"id": "r3", "want": "قابلیت ویژه آزمایشی", "status": "catalog_missing"}, prompt=group_prompt)
    assert unknown["kind"] == "CATALOG_MISSING", unknown
    generic_only = coverage.classify_uncovered({"id": "r3b", "want": "قابلیت ویژه آزمایشی",
                                                  "features": ["about"], "status": "catalog_missing"},
                                                 prompt=group_prompt)
    assert generic_only["kind"] == "CATALOG_MISSING", generic_only
    unsupported = coverage.classify_uncovered({"id": "r4", "want": "درگاه بانکی", "features": ["pay.bank_gateway"]})
    assert unsupported["kind"] == "ENGINE_LIMIT", unsupported
    from caps import capability
    private_cap = capability("group.settings.private")
    assert private_cap["status"] == "ready" and private_cap.get("catalog_ready") is True, private_cap


def test_group_settings_are_isolated():
    import engine
    bot_id = "test-" + uuid.uuid4().hex
    chat_a, chat_b = -100123450001, -100123450002
    try:
        core.db.groups.insert_many([
            {"_id": f"{bot_id}:{chat_a}", "bot": bot_id, "chat": chat_a, "type": "supergroup",
             "mod_settings": {"captcha_on": False, "flood_on": False, "lock": ["forward"],
                              "clean_join": False, "clean_leave": True, "report": False,
                              "welcome": "سلام گروه اول", "rules": "قوانین اول"}},
            {"_id": f"{bot_id}:{chat_b}", "bot": bot_id, "chat": chat_b, "type": "supergroup",
             "mod_settings": {"captcha_on": True, "flood_on": True, "lock": ["link"]}},
        ])
        cfg = {"mod": {"captcha": {"mins": 3}, "lock": ["link", "forward"],
                       "flood": {"n": 6, "secs": 8}, "warns": {"max": 3, "then": "mute", "mins": 60},
                       "clean": ["join"], "welcome": "خوش آمدی", "rules": "قوانین", "report": True}}
        a = engine.group_mod_config(bot_id, chat_a, cfg)
        b = engine.group_mod_config(bot_id, chat_b, cfg)
        assert a["captcha"] is None and a["flood"] is None
        assert a["lock"] == ["forward"] and a["welcome"] == "سلام گروه اول"
        assert a["rules"] == "قوانین اول" and a["report"] is False
        assert "join" not in a["clean"] and "leave" in a["clean"]
        assert b["captcha"] == {"mins": 3, "on": True} and b["lock"] == ["link"]
        assert b["flood"] == cfg["mod"]["flood"]
        assert cfg["mod"]["captcha"] == {"mins": 3}, "تنظیمات پایه نباید mutate شود"
        assert cfg["mod"]["lock"] == ["link", "forward"], "قفل پایه نباید mutate شود"
    finally:
        core.db.groups.delete_many({"bot": bot_id})


def test_group_settings_authorization_contract():
    import engine
    assert callable(engine._group_settings_authorized)
    assert callable(engine._group_settings_required_permission)
    required = {
        "captcha": "can_restrict_members",
        "flood": "can_delete_messages",
        "link": "can_delete_messages",
        "forward": "can_delete_messages",
        "join_clean": "can_delete_messages",
        "leave_clean": "can_delete_messages",
    }
    source = open(engine.__file__, encoding="utf-8").read()
    for key, permission in required.items():
        assert f'"{key}": (("{permission}"' in source or f'"{key}": (("{permission}",' in source
    assert '"flood": (("can_delete_messages", "can_restrict_members")' in source
    assert '"link": (("can_delete_messages", "can_restrict_members")' in source
    assert '"forward": (("can_delete_messages", "can_restrict_members")' in source
    original = engine.tg
    def fake_tg(_token, method, **kwargs):
        if method == "getMe":
            return {"ok": True, "result": {"id": 100}}
        if method == "getChatMember":
            uid = kwargs.get("user_id")
            if uid == 100:
                return {"ok": True, "result": {"status": "administrator", "can_delete_messages": True,
                                                 "can_restrict_members": False}}
            if uid == 200:
                return {"ok": True, "result": {"status": "administrator"}}
            return {"ok": True, "result": {"status": "member"}}
        raise AssertionError(method)
    try:
        engine.tg = fake_tg
        assert engine._group_settings_authorized("token", -100123456, 200)[0] is True
        assert engine._group_settings_authorized("token", -100123456, 300)[0] is False
        assert engine._group_settings_required_permission("token", -100123456, "captcha")
        assert engine._group_settings_required_permission("token", -100123456, "flood")
        assert engine._group_settings_required_permission("token", -100123456, "link")
        assert engine._group_settings_required_permission("token", -100123456, "join_clean") == ""
        def fake_tg_with_restrict(_token, method, **kwargs):
            if method == "getMe":
                return {"ok": True, "result": {"id": 100}}
            if method == "getChatMember":
                return {"ok": True, "result": {"status": "administrator", "can_delete_messages": True,
                                                  "can_restrict_members": True}}
            raise AssertionError(method)
        engine.tg = fake_tg_with_restrict
        assert engine._group_settings_required_permission("token", -100123456, "link") == ""
    finally:
        engine.tg = original


def test_group_settings_markup():
    import engine
    values = {"captcha": True, "flood": False, "link": True, "forward": False,
              "join_clean": True, "leave_clean": False, "report": True}
    markup = engine._group_settings_markup(-100123456, values)
    buttons = [b for row in markup["inline_keyboard"] for b in row]
    assert len(buttons) == 10
    assert all(len(b["callback_data"]) <= 64 for b in buttons)


def test_group_list_only_exposes_authorized_groups():
    import engine

    class Cursor:
        def __init__(self, rows): self.rows = rows
        def sort(self, *_args): return self
        def limit(self, n): self.rows = self.rows[:n]; return self
        def __iter__(self): return iter(self.rows)
    class Groups:
        def find(self, _query):
            return Cursor([
                {"chat": -100111, "title": "گروه مجاز"},
                {"chat": -100222, "title": "گروه غیرمجاز"},
            ])
    class FakeDB:
        groups = Groups()

    original_db, original_tg, original_tg_html = engine.db, engine.tg, engine.tg_html
    sent = []
    try:
        engine.db = FakeDB()
        def fake_tg(_token, method, **kwargs):
            if method == "getChatMember":
                status = "administrator" if kwargs.get("chat_id") == -100111 else "member"
                return {"ok": True, "result": {"status": status}}
            sent.append((method, kwargs))
            return {"ok": True}
        engine.tg = fake_tg
        engine.tg_html = lambda _token, method, **kwargs: sent.append((method, kwargs)) or {"ok": True}
        engine._group_settings_list("token", "bot", 200, 200, {"mod": {}})
        text_payloads = [str(kwargs) for method, kwargs in sent if method == "sendMessage"]
        assert text_payloads and "گروه مجاز" in text_payloads[0]
        assert "گروه غیرمجاز" not in text_payloads[0]
        assert "-100222" not in text_payloads[0]
    finally:
        engine.db, engine.tg, engine.tg_html = original_db, original_tg, original_tg_html


def test_group_settings_edit_accepts_mongo_utc_naive_timestamp():
    """MongoDB may return UTC datetimes as naive; a fresh edit state must remain usable."""
    from datetime import datetime, timezone
    import engine

    bot_id, chat_id, uid = "test-edit", -100333, 200
    current = datetime.now(timezone.utc)
    state = {"_id": f"gset:{bot_id}:{uid}",
             "gset": {"chat": chat_id, "field": "welcome"},
             "t": current.replace(tzinfo=None)}
    updates, sent = [], []
    class States:
        def find_one(self, _query): return state
        def delete_one(self, _query): state.clear()
    class Groups:
        def find_one(self, _query): return {"_id": f"{bot_id}:{chat_id}", "bot": bot_id, "type": "supergroup"}
        def update_one(self, _query, update, upsert=False): updates.append(update)
    class FakeDB:
        states, groups = States(), Groups()

    attrs = {name: getattr(engine, name) for name in ("db", "now", "naive", "tg",
             "_group_settings_authorized", "_group_settings_show")}
    try:
        engine.db = FakeDB()
        engine.now = lambda: current
        engine.naive = lambda value=None: (value or current).replace(tzinfo=None)
        engine.tg = lambda _token, method, **kwargs: sent.append((method, kwargs)) or {"ok": True}
        engine._group_settings_authorized = lambda *_args: (True, "")
        engine._group_settings_show = lambda *_args, **_kwargs: None
        msg = {"from": {"id": uid}, "chat": {"id": uid, "type": "private"}}
        assert engine._group_settings_message({}, bot_id, "token", {"mod": {}}, msg, "سلام مدیر") is True
        assert updates and updates[0]["$set"]["mod_settings.welcome"] == "سلام مدیر"
        assert not state, "edit state should be cleared after successful save"
    finally:
        for name, value in attrs.items():
            setattr(engine, name, value)


if __name__ == "__main__":
    test_group_manager_contract()
    test_group_settings_are_isolated()
    test_group_settings_markup()
    test_group_settings_authorization_contract()
    test_group_list_only_exposes_authorized_groups()
    test_group_settings_edit_accepts_mongo_utc_naive_timestamp()
    print("PASS group settings")
