import unittest

from builder_agent import audit_config, capability_manifest


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
                    "actions": [{"op": "add", "var": "score", "value": "1"}],
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
        cfg["nodes"]["start"]["actions"] = [{"op": "add", "var": "score"}]
        issues = audit_config(cfg)
        self.assertIn("action_missing_args", {x["code"] for x in issues})

    def test_manifest_matches_registry(self):
        manifest = capability_manifest()
        self.assertTrue(manifest["available"])
        self.assertIn("dice", manifest["actions"])
        self.assertIn("quiz", manifest["games"])


if __name__ == "__main__":
    unittest.main()
