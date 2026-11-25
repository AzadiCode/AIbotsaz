import ast
import pathlib
import unittest

import caps


ROOT = pathlib.Path(__file__).resolve().parents[1]


def assigned_tuple(path, variable):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable for target in node.targets
        ):
            return set(ast.literal_eval(node.value))
    raise AssertionError(f"{variable} assignment not found in {path}")


def function_node(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)


class EngineRegistryContractTests(unittest.TestCase):
    def test_caps_actions_match_ai_validator_allowlist(self):
        registry = {item["k"] for item in caps.CAPS_DO}
        self.assertEqual(registry, assigned_tuple("ai.py", "ACT_OPS"))

    def test_caps_conditions_match_ai_validator_allowlist(self):
        registry = {item["k"] for item in caps.CAPS_IF}
        self.assertEqual(registry, assigned_tuple("ai.py", "OPS"))

    def test_every_registered_action_has_an_engine_dispatch(self):
        run_actions = function_node("engine.py", "run_actions")
        explicit = set()
        db_prefix = False
        for node in ast.walk(run_actions):
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "op":
                for value in node.comparators:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        explicit.add(value.value)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "op" and node.func.attr == "startswith":
                    if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "db_":
                        db_prefix = True
        missing = []
        for item in caps.CAPS_DO:
            action = item["k"]
            if action.startswith("db_") and db_prefix:
                continue
            if action not in explicit:
                missing.append(action)
        self.assertEqual(missing, [])

    def test_engine_condition_evaluator_covers_registry(self):
        check = function_node("engine.py", "check")
        constants = {node.value for node in ast.walk(check) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        missing = {item["k"] for item in caps.CAPS_IF} - constants
        self.assertEqual(missing, [])

    def test_required_action_arguments_are_a_subset_of_supported_arguments(self):
        for item in caps.CAPS_DO:
            self.assertTrue(set(item.get("required", [])) <= set(item.get("args", [])), item["k"])


if __name__ == "__main__":
    unittest.main()
