# -*- coding: utf-8 -*-
"""قرارداد پذیرش ماژول‌های آماده؛ نام توابع با caps.CAPS_CONTRACT هم‌خوان است."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._env  # noqa: F401 — تنظیم محیط پیش از import core/engine


def _module_case(module_id):
    import ai
    import engine_accept
    import modules
    import planner
    import modlib  # noqa: F401 — ثبت تمام ماژول‌ها

    if module_id not in modules.MODULES:
        raise AssertionError(f"module is not registered: {module_id}")

    plan = planner.PlanResult()
    included = set()

    def add_with_dependencies(mid):
        if mid in included:
            return
        mod = modules.MODULES[mid]
        for dep in mod.requires:
            if dep not in modules.MODULES:
                raise AssertionError(f"{mid} requires missing module {dep}")
            add_with_dependencies(dep)
        included.add(mid)
        plan.items.append((mid, modules.clean_params(mod, {})))

    add_with_dependencies(module_id)
    plan.name = "تست پذیرش ماژول"
    plan.emoji = False
    plan.payments = False
    plan.confidence = 1.0
    _thinking, cfg, _ideas = planner.compile_plan(plan)
    cfg = ai.sanitize(cfg, strict=False, warns=[])
    issues = [issue for issue in ai.lint(cfg)
              if not issue.startswith("variables that are read but never set")]
    if issues:
        raise AssertionError(f"lint failed for {module_id}: {issues}")
    failures = engine_accept.run_acceptance(cfg, [module_id])
    if failures:
        raise AssertionError(f"acceptance failed for {module_id}: {failures[:5]}")
    return True


def start_menu(): return _module_case("start_menu")
def wallet(): return _module_case("wallet")
def daily(): return _module_case("daily")
def dice(): return _module_case("dice")
def guess(): return _module_case("guess")
def coinbet(): return _module_case("coinbet")
def quiz(): return _module_case("quiz")
def wheel(): return _module_case("wheel")
def leaderboard(): return _module_case("leaderboard")
def referral(): return _module_case("referral")
def shop(): return _module_case("shop")
def support(): return _module_case("support")
def forced_join(): return _module_case("forced_join")
def ai_assistant(): return _module_case("ai_assistant")
def group_manager(): return _module_case("group_manager")


def test_group_manager():
    assert group_manager()


def test_module_catalog_acceptance_contracts():
    """توابع پذیرش معرفی‌شده در caps.py باید برای تمام قابلیت‌های آماده موجود باشند."""
    import ast
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    caps_source = (root / "caps.py").read_text(encoding="utf-8")
    refs = re.findall(r'tests/test_modules\.py::([A-Za-z_][A-Za-z0-9_]*)', caps_source)
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    declared = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    missing = sorted(set(refs) - declared)
    assert not missing, f"acceptance functions missing: {missing}"
