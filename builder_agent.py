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
        "action_contracts": [{"k": x.get("k"), "args": x.get("args", []), "required": x.get("required", x.get("args", []))}
                             for x in getattr(_caps, "CAPS_DO", [])],
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


def _variable_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        db_line = "table" in value and "line" in value
        for key, child in value.items():
            if db_line and key == "line":
                continue
            yield from _variable_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _variable_strings(child)


def _logic_items(cfg: dict):
    """Yield only actual action/condition objects, never arbitrary user data dictionaries."""
    found = []

    def actions(value):
        if isinstance(value, list):
            found.extend(x for x in value if isinstance(x, dict) and x.get("op"))

    def condition(value):
        if not isinstance(value, dict):
            return
        if value.get("op") or "var" in value:
            found.append(value)
        for key in ("all", "any"):
            for child in value.get(key) or []:
                condition(child)
        if isinstance(value.get("not"), dict):
            condition(value["not"])

    for node in (cfg.get("nodes") or {}).values():
        if not isinstance(node, dict):
            continue
        actions(node.get("do"))
        condition(node.get("when"))
        for row in node.get("buttons") or []:
            for button in row if isinstance(row, list) else []:
                if isinstance(button, dict):
                    actions(button.get("do"))
                    condition(button.get("when"))
        for route in node.get("route") or []:
            if isinstance(route, dict):
                actions(route.get("do"))
                condition(route.get("when"))
    actions(cfg.get("on_ref"))
    return found


def audit_config(cfg: dict) -> list[dict]:
    """Find deterministic configuration defects; never infer feature coverage from labels."""
    issues: list[dict] = []
    if not isinstance(cfg, dict) or not isinstance(cfg.get("nodes"), dict):
        return [{"code": "invalid_config", "severity": "blocker",
                 "message": "ساختار کانفیگ یا مجموعه نودها معتبر نیست."}]

    nodes = cfg.get("nodes") or {}
    vars_declared = set((cfg.get("vars") or {}).keys()) | set((cfg.get("globals") or {}).keys())
    if not isinstance(cfg.get("start"), str) or cfg.get("start") not in nodes:
        issues.append({"code": "invalid_start_node", "severity": "blocker", "message": "گره شروع تعریف نشده یا به نودی ناموجود اشاره می‌کند."})
    if cfg.get("fallback") and cfg.get("fallback") not in nodes:
        issues.append({"code": "invalid_fallback_node", "severity": "blocker", "message": f"گره جایگزین «{cfg.get('fallback')}» وجود ندارد."})
    for command, target in (cfg.get("commands") or {}).items():
        if target not in nodes:
            issues.append({"code": "invalid_command_target", "severity": "blocker", "message": f"دستور «{command}» به نود ناموجود «{target}» متصل است."})
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            issues.append({"code": "invalid_node", "severity": "blocker", "message": f"ساختار نود «{node_id}» معتبر نیست."})
            continue
        if node.get("next") and node["next"] not in nodes:
            issues.append({"code": "invalid_navigation_target", "severity": "blocker", "message": f"نود «{node_id}» به مقصد ناموجود «{node['next']}» اشاره می‌کند."})
        pay = node.get("pay")
        if isinstance(pay, dict) and pay.get("goto") and pay["goto"] not in nodes:
            issues.append({"code": "invalid_payment_target", "severity": "blocker", "message": f"مسیر پس از پرداخت در نود «{node_id}» به مقصد ناموجود «{pay['goto']}» اشاره می‌کند."})
        for route in node.get("route") or []:
            if isinstance(route, dict) and route.get("goto") and route["goto"] not in nodes:
                issues.append({"code": "invalid_navigation_target", "severity": "blocker", "message": f"مسیر نود «{node_id}» به مقصد ناموجود «{route['goto']}» اشاره می‌کند."})
        for row in node.get("buttons") or []:
            for button in row if isinstance(row, list) else []:
                if isinstance(button, dict) and button.get("goto") and button["goto"] not in nodes:
                    issues.append({"code": "invalid_button_target", "severity": "blocker", "message": f"دکمه در نود «{node_id}» به مقصد ناموجود «{button['goto']}» اشاره می‌کند."})
    reads: set[str] = set()
    writes: set[str] = set()
    used_ops: set[str] = set()
    for value in _variable_strings(nodes):
        reads.update(VAR_RE.findall(value))
    for value in _variable_strings(cfg.get("on_ref") or []):
        reads.update(VAR_RE.findall(value))
    for item in _logic_items(cfg):
        op = str(item.get("op") or ("==" if "var" in item else ""))
        if op:
            used_ops.add(op)
            if op == "remind" and item.get("goto") and item["goto"] not in nodes:
                issues.append({"code": "invalid_reminder_target", "severity": "blocker",
                               "message": f"مقصد یادآور «{item['goto']}» وجود ندارد."})
            required = next((x.get("required", []) for x in getattr(_caps, "CAPS_DO", []) if x.get("k") == op), ACTION_ARGS.get(op, ()))
            if required:
                missing = [key for key in required if key not in item or item.get(key) in (None, "")]
                if missing:
                    issues.append({
                        "code": "action_missing_args", "severity": "blocker",
                        "message": f"اکشن «{op}» آرگومان‌های لازم را ندارد: {', '.join(missing)}.",
                        "node": "", "action": op,
                    })
            elif op not in CONDITION_OPS and op not in {x.get("k") for x in getattr(_caps, "CAPS_DO", [])}:
                issues.append({"code": "unknown_action", "severity": "blocker",
                               "message": f"اکشن «{op}» در قرارداد شناخته‌شده موتور ثبت نشده است.", "action": op})
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
                       "message": f"اکشن «{op}» در رجیستری قابلیت‌های موتور وجود ندارد.", "action": op})

    # Deduplicate without losing stable order.
    result, seen = [], set()
    for issue in issues:
        key = (issue.get("code"), issue.get("message"))
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def requires_approval_replan(state, approved_limits):
    """A preflight-only checkpoint is stale after the user approves a substitution."""
    return bool(isinstance(state, dict) and approved_limits
                and state.get("phase") == "planned" and not (state.get("completed") or []))


def unapproved_limits(discovered, approved):
    """Return newly discovered limitations that have not received explicit user approval."""
    approved_wants = {str(x.get("want") or "").strip().casefold()
                      for x in (approved or []) if isinstance(x, dict)}
    return [x for x in (discovered or []) if isinstance(x, dict)
            and str(x.get("want") or "").strip().casefold() not in approved_wants]


def gaps_from_issues(issues: list[dict]) -> list[dict]:
    """Convert deterministic findings to the existing user/admin gap-report contract."""
    return [{
        "want": (f"تعریف متغیر {issue['variable']}" if issue.get("variable")
                 else f"اصلاح اکشن {issue['action']}" if issue.get("action")
                 else f"رفع خطای {issue.get('code', 'builder_audit')}"),
        "why": issue.get("message", "نقص فنی شناسایی شد."),
        "upgrade": "اصلاح همان بخش، اجرای مجدد اعتبارسنجی و آزمون پذیرش؛ تا آن زمان خروجی تأیید نشود.",
        "code": issue.get("code", "builder_audit"),
        "severity": issue.get("severity", "blocker"),
    } for issue in issues]
