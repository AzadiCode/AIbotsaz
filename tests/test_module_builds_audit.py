import unittest

import planner
from builder_agent import audit_config


class CompiledModuleAuditTests(unittest.TestCase):
    CASES = [
        "ربات فروشگاهی با سبد خرید و ثبت سفارش بساز",
        "ربات ماینر سکه با دعوت دوستان و پاداش روزانه بساز",
        "ربات مدیریت گروه با ضد لینک و کپچا بساز",
        "ربات ثبت آگهی و تبلیغات بساز",
        "ربات بازی با امتیاز و جدول برترین‌ها بساز",
    ]

    def test_compiled_module_outputs_pass_deterministic_audit(self):
        built = 0
        for prompt in self.CASES:
            with self.subTest(prompt=prompt):
                plan = planner.plan_request(prompt)
                if not plan.items:
                    continue
                _, cfg, _ = planner.compile_plan(plan)
                issues = audit_config(cfg)
                self.assertEqual(
                    issues, [],
                    msg=f"modules={plan.ids}; issues={issues}",
                )
                built += 1
        self.assertGreater(built, 0, "No deterministic module case was selected")


if __name__ == "__main__":
    unittest.main()
