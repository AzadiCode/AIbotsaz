import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def source_of_function(filename, function_name):
    path = ROOT / filename
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return source.splitlines()[node.lineno - 1:node.end_lineno]
    raise AssertionError(f"{function_name} not found in {filename}")


def function_text(filename, function_name):
    return "\n".join(source_of_function(filename, function_name))


class BuildPipelineContractTests(unittest.TestCase):
    def test_review_gates_happen_before_any_save_or_charge(self):
        body = function_text("mother.py", "gen_job")
        review_existing = body.index("if gaps and bot_id")
        review_new = body.index("if gaps and not bot_id")
        save_transition = body.index('"status": "saving"')
        persist_bot = body.index("new_bot_doc(uid, cfg, thinking)")
        charge = body.index("charge_up_to(uid, cost")
        mark_done = body.index('"status": "done"')
        self.assertLess(review_existing, save_transition)
        self.assertLess(review_new, save_transition)
        self.assertLess(save_transition, persist_bot)
        self.assertLess(persist_bot, charge)
        self.assertLess(charge, mark_done)

    def test_failure_path_refunds_and_rolls_back_created_or_existing_bot(self):
        body = function_text("mother.py", "gen_job")
        self.assertIn("core.refund(uid, charged_amount", body)
        self.assertIn("db.bots.delete_one", body)
        self.assertIn("old_bot_snapshot", body)
        self.assertIn("sync_commands(restored", body)

    def test_preflight_approval_is_persisted_and_stale_plan_is_rebuilt(self):
        callback = function_text("mother.py", "mother_callback")
        self.assertIn('"preflight_ok": True', callback)
        self.assertIn('"approved_limits": list(job.get("approved_limits") or []) + list(job.get("gaps") or [])', callback)
        ai_source = (ROOT / "ai.py").read_text(encoding="utf-8")
        self.assertIn("builder_agent.requires_approval_replan", ai_source)
        self.assertIn("builder_agent.unapproved_limits", ai_source)
        self.assertIn("approved_limit_substitutions", ai_source)

    def test_fast_module_path_requires_both_deterministic_and_requirement_qa(self):
        body = function_text("ai.py", "ask_llm")
        self.assertIn("_module_build", body)
        self.assertIn("builder_agent.audit_config", body)
        self.assertIn("audit_requirements", body)
        self.assertIn("_fast_qa", body)

    def test_deterministic_validator_failure_gets_one_bounded_repair_attempt(self):
        body = function_text("ai.py", "ask_llm")
        self.assertIn("deterministic_task", body)
        self.assertIn("repair_deterministic_audit", body)
        self.assertIn("_task_patch_call", body)
        self.assertIn("deterministic_repair_failed", body)
        self.assertIn("builder_agent.audit_config(cfg)", body)


if __name__ == "__main__":
    unittest.main()
