import unittest

from builder_agent import audit_config, capability_manifest, requires_approval_replan, unapproved_limits


class BuilderAgentAuditTests(unittest.TestCase):
    def base(self):
        return {
            "name": "Test",
            "start": "start",
            "fallback": "start",
            "commands": {},
            "vars": {"score": "0"},
            "globals": {},
            "nodes": {
                "start": {
                    "text": "Score: {score}",
                    "buttons": [],
                    "do": [{"op": "add", "var": "score", "value": "1"}],
                }
            },
        }

    def test_declared_variable_and_supported_action_pass(self):
        self.assertEqual(audit_config(self.base()), [])

    def test_undefined_variable_is_blocking(self):
        cfg = self.base()
        cfg["vars"] = {}
        issues = audit_config(cfg)
        self.assertIn("undeclared_variable", {x["code"] for x in issues})

    def test_missing_action_argument_is_blocking(self):
        cfg = self.base()
        cfg["nodes"]["start"]["do"] = [{"op": "add", "var": "score"}]
        issues = audit_config(cfg)
        self.assertIn("action_missing_args", {x["code"] for x in issues})


    def test_condition_operators_are_not_misclassified_as_actions(self):
        cfg = self.base()
        cfg["nodes"]["start"]["when"] = {"op": "==", "var": "score", "value": "0"}
        self.assertEqual(audit_config(cfg), [])

    def test_unknown_action_is_blocking(self):
        cfg = self.base()
        cfg["nodes"]["start"]["do"] = [{"op": "teleport"}]
        issues = audit_config(cfg)
        self.assertIn("unknown_action", {x["code"] for x in issues})

    def test_chat_scoped_action_is_registered(self):
        cfg = self.base()
        cfg["nodes"]["start"]["do"] = [{"op": "cset", "var": "room_score", "value": "1"}]
        self.assertNotIn("unknown_action", {x["code"] for x in audit_config(cfg)})

    def test_condition_variable_must_be_declared(self):
        cfg = self.base()
        cfg["nodes"]["start"]["when"] = {"op": "==", "var": "missing_score", "value": "0"}
        issues = audit_config(cfg)
        self.assertIn("undeclared_variable", {x["code"] for x in issues})

    def test_optional_registry_action_is_not_misclassified(self):
        cfg = self.base()
        cfg["nodes"]["start"]["do"] = [{"op": "sub_add"}]
        self.assertNotIn("unknown_action", {x["code"] for x in audit_config(cfg)})

    def test_user_data_key_named_op_is_not_treated_as_an_action(self):
        cfg = self.base()
        cfg["nodes"]["start"]["do"] = [{"op": "db_add", "table": "records",
                                         "data": {"op": "teleport", "score": "{score}"}}]
        self.assertNotIn("unknown_action", {x["code"] for x in audit_config(cfg)})

    def test_approved_preflight_invalidates_stale_empty_checkpoint(self):
        state = {"phase": "planned", "completed": [], "plan": [{"id": "foundation"}]}
        self.assertTrue(requires_approval_replan(state, [{"want": "feature X"}]))
        state["completed"] = ["foundation"]
        self.assertFalse(requires_approval_replan(state, [{"want": "feature X"}]))
        self.assertFalse(requires_approval_replan({"phase": "planned", "completed": []}, []))

    def test_new_limit_requires_fresh_approval(self):
        approved = [{"want": "feature A"}]
        discovered = [{"want": "feature A"}, {"want": "feature B"}]
        self.assertEqual([x["want"] for x in unapproved_limits(discovered, approved)], ["feature B"])

    def test_manifest_matches_registry(self):
        manifest = capability_manifest()
        self.assertTrue(manifest["available"])
        self.assertIn("dice", manifest["actions"])
        self.assertIn("quiz", manifest["games"])


if __name__ == "__main__":
    unittest.main()
