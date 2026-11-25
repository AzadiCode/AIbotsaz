import unittest

import planner
from builder_agent import audit_config


def build_module_plan(module_id):
    selected = set(module_id) if isinstance(module_id, (list, tuple, set)) else {module_id}
    changed = True
    while changed:
        changed = False
        for mid in list(selected):
            for dependency in planner.MODULES[mid].requires:
                if dependency not in selected:
                    selected.add(dependency)
                    changed = True
    result = planner.PlanResult()
    result.name = "Deterministic module audit"
    result.items = [
        (mid, planner.clean_params(planner.MODULES[mid], None))
        for mid in sorted(selected, key=lambda x: planner.MODULES[x].prio)
    ]
    return result


class CompiledModuleAuditTests(unittest.TestCase):
    def test_every_registered_module_default_compiles_and_passes_audit(self):
        self.assertGreater(len(planner.MODULES), 0)
        for module_id in sorted(planner.MODULES):
            with self.subTest(module=module_id):
                plan = build_module_plan(module_id)
                _, cfg, _ = planner.compile_plan(plan)
                issues = audit_config(cfg)
                self.assertEqual(issues, [], msg=f"modules={plan.ids}; issues={issues}")

    def test_common_multi_module_combinations_pass_audit(self):
        combinations = [
            ["wallet", "daily", "referral", "miner", "wheel", "puzzle", "sponsor", "forced_join", "member_orders", "coin_shop", "owner_panel"],
            ["ads", "shop", "support", "faq", "about", "links"],
            ["group_manager", "quiz", "ai_assistant", "links", "faq"],
        ]
        for combination in combinations:
            with self.subTest(modules=combination):
                plan = build_module_plan(combination)
                _, cfg, _ = planner.compile_plan(plan)
                issues = audit_config(cfg)
                self.assertEqual(issues, [], msg=f"modules={plan.ids}; issues={issues}")


if __name__ == "__main__":
    unittest.main()
