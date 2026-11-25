# -*- coding: utf-8 -*-
"""Deterministic capability and configuration checks for the agentic builder.

This module deliberately does not call an LLM. It checks facts that must be
true before a generated bot configuration can be considered structurally safe.
"""
from __future__ import annotations

import re
from typing import Any

try:
    import caps as _caps
except Exception:  # pragma: no cover - keeps diagnostics usable during partial imports
    _caps = None

VAR_RE = re.compile(r"\{([a-z][a-z0-9_]{0,19})(?:\|[^{}]{0,60})?\}")
BUILTINS = {
    "name", "first_name", "last_name", "full_name", "username", "id", "lang",
    "premium", "is_owner", "is_admin", "bot_name", "bot_username", "text",
    "param", "visits", "refs", "ref_link", "date", "time", "hour", "weekday",
    "ticket_no",
}
ACTION_ARGS = {
    "set": ("var", "value"), "add": ("var", "value"), "clear": ("var",),
    "random": ("var", "value"), "pick": ("var", "value"), "dice": ("var", "emoji"),
    "notify": ("value",), "remind": ("minutes", "value"),
    "db_add": ("table", "data"), "db_get": ("table", "var"),
    "db_set": ("table", "data"), "db_inc": ("table", "var", "value"),
    "db_del": ("table",), "fetch": ("url", "var"), "game_play": ("game",),
    "calc": ("var", "value"), "disc": ("var", "price"),
    "sub_add": ("plan", "days"), "sub_del": ("plan",),
}
DYNAMIC_SUFFIXES = ("_ok", "_off", "_save", "_err")
CONDITION_OPS = {"==", "!=", ">", ">=", "<", "<=", "contains", "empty", "filled", "sub", "=", "eq", "ne", "gt", "gte", "lt", "lte"}
NON_ACTION_OPS = CONDITION_OPS | {"if", "else", "route"}


def capability_manifest() -> dict:
    """Return a compact, machine-readable snapshot of the engine's public registry."""
    if _caps is None:
        return {"available": False, "events": [], "conditions": [], "actions": [], "games": []}
    return {
        "available": True,
        "version": getattr(_caps, "BUILD", ""),
        "events": [x.get("k") for x in getattr(_caps, "CAPS_EVENTS", [])],
        "conditions": [x.get("k") for x in getattr(_caps, "CAPS_IF", [])],
        "actions": [x.get("k") for x in getattr(_caps, "CAPS_DO", [])],
        "buttons": [x.get("k") for x in getattr(_caps, "CAPS_BTNS", [])],
        "blocks": [x.get("k") for x in getattr(_caps, "CAPS_BLOCKS", [])],
        "games": [x.get("k") for x in getattr(_caps, "CAPS_GAMES", [])],
        "limits": getattr(_caps, "LIMITS", {}),
    }


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def audit_config(cfg: dict) -> list[dict]:
    """Find deterministic configuration defects; never infer feature coverage from labels."""
    issues: list[dict] = []
    if not isinstance(cfg, dict) or not isinstance(cfg.get("nodes"), dict):
        return [{"code": "invalid_config", "severity": "blocker",
                 "message": "ساختار کانفیگ یا مجموعه نودها معتبر نیست."}]

    nodes = cfg.get("nodes") or {}
    vars_declared = set((cfg.get("vars") or {}).keys()) | set((cfg.get("globals") or {}).keys())
    reads: set[str] = set()
    writes: set[str] = set()
    used_ops: set[str] = set()
    for item in _walk(nodes):
        op = str(item.get("op") or "")
        if op:
            used_ops.add(op)
            required = next((x.get("required", []) for x in getattr(_caps, "CAPS_DO", []) if x.get("k") == op), ACTION_ARGS.get(op, ()))
            if required:
                missing = [key for key in required if key not in item or item.get(key) in (None, "")]
                if missing:
                    issues.append({
                        "code": "action_missing_args", "severity": "blocker",
                        "message": f"اکشن «{op}» آرگومان‌های لازم را ندارد: {', '.join(missing)}.",
                        "node": "",
                    })
            elif op not in CONDITION_OPS and op not in {x.get("k") for x in getattr(_caps, "CAPS_DO", [])}:
                issues.append({"code": "unknown_action", "severity": "blocker",
                               "message": f"اکشن «{op}» در قرارداد شناخته‌شده موتور ثبت نشده است."})
        for value in _strings(item):
            reads.update(VAR_RE.findall(value))
        if op in CONDITION_OPS and item.get("var"):
            reads.add(str(item["var"]))
        if op in {"add", "clear", "disc"} and item.get("var"):
            reads.add(str(item["var"]))
        if op in {"set", "add", "random", "pick", "dice", "calc", "db_get", "db_inc"} and item.get("var"):
            writes.add(str(item["var"]))
        if op == "disc" and item.get("var"):
            base = str(item["var"])
            writes.update(base + suffix for suffix in DYNAMIC_SUFFIXES)

    undeclared = sorted(name for name in reads
                        if name not in vars_declared and name not in BUILTINS
                        and not any(name.endswith(suffix) and name[:-len(suffix)] in vars_declared
                                    for suffix in DYNAMIC_SUFFIXES))
    for name in undeclared:
        issues.append({
            "code": "undeclared_variable", "severity": "blocker",
            "message": f"متغیر «{name}» استفاده شده اما در vars یا globals تعریف نشده است.",
            "variable": name,
        })

    manifest = capability_manifest()
    allowed_ops = set(manifest.get("actions") or [])
    for op in sorted(used_ops - allowed_ops - CONDITION_OPS):
        issues.append({"code": "engine_capability_mismatch", "severity": "blocker",
                       "message": f"اکشن «{op}» در رجیستری قابلیت‌های موتور وجود ندارد."})

    # Deduplicate without losing stable order.
    result, seen = [], set()
    for issue in issues:
        key = (issue.get("code"), issue.get("message"))
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def gaps_from_issues(issues: list[dict]) -> list[dict]:
    """Convert deterministic findings to the existing user/admin gap-report contract."""
    return [{
        "want": issue.get("variable") and f"تعریف متغیر {issue['variable']}" or "اعتبارسنجی فنی خروجی",
        "why": issue.get("message", "نقص فنی شناسایی شد."),
        "upgrade": "اصلاح همان بخش، اجرای مجدد اعتبارسنجی و آزمون پذیرش؛ تا آن زمان خروجی تأیید نشود.",
        "code": issue.get("code", "builder_audit"),
        "severity": issue.get("severity", "blocker"),
    } for issue in issues]
