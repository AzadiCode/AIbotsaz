# -*- coding: utf-8 -*-
"""Focused regression tests for request understanding and requirement coverage.

Run without Flask/MongoDB: python tests/test_requirement_quality.py
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import modlib  # register the real catalogue
import modules
import planner
import spec
import coverage as cov


class RequirementQualityTests(unittest.TestCase):
    def setUp(self):
        self._old_static = cov._static_limit_for
        cov._static_limit_for = lambda want, prompt="": None

    def tearDown(self):
        cov._static_limit_for = self._old_static

    def test_existing_group_module_is_discoverable(self):
        hits = cov.catalog_candidates("مدیریت گروه در محیط گروه")
        self.assertIn("group_manager", [x["id"] for x in hits])


    def test_exact_production_report_wording_recovers_existing_group_module(self):
        sp = {"features": [], "requirements": [
            {"id": "r1", "want": "اجرای دستورات مدیریتی و نظارتی در گروه", "part": "محیط گروه",
             "status": "catalog_missing", "features": []},
            {"id": "r2", "want": "انجام تنظیمات ربات از طریق پیام خصوصی (PV)", "part": "پیوی",
             "status": "catalog_missing", "features": []},
        ]}
        recovered = cov.reconcile_spec(sp, "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد")
        self.assertEqual(recovered, ["group_manager"])
        self.assertEqual([r["status"] for r in sp["requirements"]], ["covered", "covered"])
        self.assertEqual([r["features"] for r in sp["requirements"]], [["group_manager"], ["group_manager"]])
        self.assertEqual(cov.unmet_items(sp), [])
        self.assertEqual(len([f for f in sp["features"] if f["type"] == "group_manager"]), 1)

    def test_group_aliases_do_not_make_generic_private_settings_a_group_request(self):
        req = {"id": "r1", "want": "تنظیمات حساب شخصی از طریق پیام خصوصی", "part": "پیوی",
               "status": "catalog_missing", "features": []}
        self.assertNotIn("group_manager", [x["id"] for x in cov.catalog_candidates(req["want"])])

    def test_unrelated_module_does_not_cover_group_management(self):
        req = {"id": "r1", "want": "مدیریت گروه در محیط گروه", "features": ["about"]}
        self.assertFalse(cov._served_by(req, {"about"}))
        defect = cov.classify_uncovered({**req, "status": "catalog_missing"})
        self.assertEqual(defect["kind"], "BUILD_DEFECT")
        self.assertNotEqual(defect["kind"], "CATALOG_MISSING")

    def test_catalog_reconciliation_recovers_registered_module(self):
        sp = {"features": [], "requirements": [{
            "id": "r1", "want": "مدیریت گروه در محیط گروه", "part": "گروه",
            "status": "catalog_missing", "features": [],
        }]}
        recovered = cov.reconcile_spec(sp)
        self.assertIn("group_manager", recovered)
        self.assertIn("group_manager", [x["type"] for x in sp["features"]])
        self.assertEqual(sp["requirements"][0]["status"], "covered")

    def test_private_settings_are_not_miscovered_by_group_module(self):
        req = {"id": "r2", "want": "تنظیمات ربات در گفتگوی خصوصی", "status": "catalog_missing", "features": []}
        self.assertFalse(cov.catalog_candidates(req["want"]))
        defect = cov.classify_uncovered(req)
        self.assertEqual(defect["kind"], "CATALOG_MISSING")

    def test_combined_requirement_is_reported_as_decomposition_defect(self):
        req = {"id": "r1", "want": "مدیریت گروه و انجام تنظیمات ربات در گفتگوی خصوصی",
               "status": "catalog_missing", "features": []}
        defect = cov.classify_uncovered(req)
        self.assertEqual(defect["kind"], "BUILD_DEFECT")
        self.assertIn("تفکیک", defect["evidence"])

    def test_static_limit_does_not_leak_between_requirements(self):
        seen = []
        def static_for(want, prompt=""):
            seen.append((want, prompt))
            if "درگاه بانکی" in want:
                return {"kind": "ENGINE_LIMIT", "feature": "pay.bank_gateway", "want": want}
            return None
        cov._static_limit_for = static_for
        defect = cov.classify_uncovered({"id": "r1", "want": "گزارش آمار کاربران", "status": "catalog_missing"},
                                        prompt="درگاه بانکی و گزارش آمار کاربران")
        self.assertEqual(seen[0], ("گزارش آمار کاربران", ""))
        self.assertEqual(defect["kind"], "CATALOG_MISSING")

    def test_generic_about_module_is_not_coverage_evidence(self):
        req = {"id": "r1", "want": "مدیریت گروه و حذف پیام کاربران", "part": "گروه",
               "status": "covered", "features": ["about"]}
        self.assertFalse(cov._served_by(req, {"about"}))

    def test_ranked_game_request_does_not_select_group_manager(self):
        result = planner.plan_request("ربات بازی با گردونه و رتبه بندی و دعوت دوستان و کیف سکه بساز")
        self.assertIn("leaderboard", result.ids)
        self.assertNotIn("group_manager", result.ids)

    def test_simple_start_menu_trigger_is_actionable(self):
        result = planner.plan_request("منوی شروع ربات")
        self.assertIn("start_menu", result.ids)
        self.assertNotIn("shop", result.ids)

    def test_mixed_group_and_private_settings_request_cannot_short_circuit_keyword_router(self):
        result = planner.plan_request("یه ربات مدیر گروه بساز و تنظیماتش در پیوی باشه")
        self.assertIn("group_manager", result.ids)
        self.assertLess(result.rest_ratio, 0.95)

    def test_spec_version_is_normalized_instead_of_rejecting_valid_content(self):
        # The version field is protocol metadata. Variations from different LLMs
        # must not reject an otherwise valid Spec. Semantic fields remain validated.
        versions = [1, 1.0, "1", "1.0", "v1", "spec-v1", "Spec version 1", None, "BUILD 3.6.2"]
        payloads = [{"version": version, "intent": "create", "name": "x",
                     "features": [{"type": "dice", "req": ["r1"]}],
                     "requirements": [{"id": "r1", "want": "بازی تاس",
                                       "status": "covered", "features": ["dice"]}]}
                    for version in versions]
        payloads.append({"intent": "create", "name": "x",
                         "features": [{"type": "dice", "req": ["r1"]}],
                         "requirements": [{"id": "r1", "want": "بازی تاس",
                                           "status": "covered", "features": ["dice"]}]})
        for payload in payloads:
            with self.subTest(version=payload.get("version", "<missing>")):
                validated = spec.validate_spec(payload, require_requirements=True,
                                                expected_intent="create")
                self.assertEqual(validated["version"], spec.SPEC_VERSION)
                self.assertIn("dice", [f["type"] for f in validated["features"]])

    def test_malformed_version_does_not_bypass_semantic_validation(self):
        payload = {"version": "Spec v1", "intent": "create", "name": "x",
                   "features": [{"type": "dice", "params": ["invalid"]}],
                   "requirements": [{"id": "r1", "want": "بازی تاس",
                                     "status": "covered", "features": ["dice"]}]}
        with self.assertRaises(spec.SpecError):
            spec.validate_spec(payload, require_requirements=True, expected_intent="create")

    def test_llm_json_parser_accepts_non_numeric_protocol_version(self):
        import json
        import sys
        import types
        from unittest.mock import patch

        raw = json.dumps({
            "version": "BUILD 3.6.2", "intent": "create", "name": "بازی",
            "features": [{"type": "dice", "req": ["r1"]}],
            "requirements": [{"id": "r1", "want": "بازی تاس",
                              "status": "covered", "features": ["dice"]}],
        }, ensure_ascii=False)
        ai_stub = types.ModuleType("ai")
        ai_stub._extract_json_object = lambda value: value
        with patch.dict(sys.modules, {"ai": ai_stub}):
            validated = spec.parse_llm_spec(raw, require_requirements=True, expected_intent="create")
        self.assertEqual(validated["version"], spec.SPEC_VERSION)
        self.assertEqual(validated["features"][0]["type"], "dice")

    def test_spec_prompt_does_not_ask_model_to_generate_protocol_version(self):
        messages = spec.spec_prompt("یه ربات بازی بساز")
        system_prompt = messages[0]["content"]
        self.assertIn("نسخهٔ Spec را تولید نکن", system_prompt)
        self.assertNotIn('{"version":', system_prompt)

    def test_spec_rejects_missing_requirements_in_ai_mode(self):
        with self.assertRaises(spec.SpecError):
            spec.validate_spec({"version": 1, "intent": "create", "name": "x",
                                "features": [{"type": "about"}]}, require_requirements=True,
                               expected_intent="create")

    def test_unknown_optional_params_are_dropped_without_losing_valid_spec(self):
        validated = spec.validate_spec({"version": 1, "intent": "create", "name": "x",
                                        "features": [{"type": "dice", "params": {"junk": 1, "sides": 12}}]})
        params = next(x["params"] for x in validated["features"] if x["type"] == "dice")
        self.assertNotIn("junk", params)
        self.assertEqual(params["sides"], 12)

    def test_all_unavailable_requirements_survive_spec_validation_for_preflight(self):
        validated = spec.validate_spec({
            "version": 1, "intent": "create", "name": "x", "features": [],
            "requirements": [{"id": "r1", "want": "قابلیت خارج از توان فعلی", "status": "catalog_missing", "features": []}],
        }, require_requirements=True, expected_intent="create")
        self.assertEqual(validated["features"], [])
        self.assertEqual(validated["requirements"][0]["status"], "catalog_missing")

    def test_unknown_model_module_becomes_gap_not_fatal_schema_failure(self):
        validated = spec.validate_spec({
            "version": 1, "intent": "create", "name": "x",
            "features": [{"type": "new_fake_module", "note": "رفتار خیالی"}],
            "requirements": [{"id": "r1", "want": "رفتار خیالی", "status": "covered",
                              "features": ["new_fake_module"]}],
        }, require_requirements=True, expected_intent="create")
        self.assertEqual(validated["features"], [])
        self.assertEqual(validated["requirements"][0]["status"], "catalog_missing")


    def test_placement_part_does_not_replace_requested_behavior(self):
        req = {"id": "r1", "want": "بازی تاس", "part": "منوی شروع ربات",
               "status": "covered", "features": ["dice"]}
        self.assertEqual(cov._req_match_text(req), "بازی تاس")
        self.assertTrue(cov._served_by(req, {"dice", "start_menu"}))
        self.assertFalse(cov._served_by({**req, "features": ["start_menu"]}, {"dice", "start_menu"}))

    def test_reconciliation_uses_behavior_not_placement(self):
        sp = {"features": [], "requirements": [{
            "id": "r1", "want": "بازی تاس", "part": "منوی شروع",
            "status": "catalog_missing", "features": [],
        }]}
        recovered = cov.reconcile_spec(sp)
        self.assertIn("dice", recovered)
        self.assertNotIn("start_menu", recovered)

    def test_action_words_do_not_block_exact_catalog_match(self):
        self.assertIn("dice", [x["id"] for x in cov.catalog_candidates("افزودن بازی تاس")])
        planned = planner.plan_request("افزودن بازی تاس")
        self.assertIn("dice", planned.ids)
        self.assertGreaterEqual(planned.rest_ratio, 0.95)

    def test_long_requirement_is_rejected_not_silently_truncated(self):
        reqs, errors = cov.norm_requirements([{"id": "r1", "want": "الف" * 301}])
        self.assertTrue(errors)
        self.assertFalse(reqs)


    def test_spec_rejects_oversized_requirement_links_without_truncating(self):
        with self.assertRaises(spec.SpecError):
            spec.validate_spec({
                "version": 1, "intent": "create", "name": "x",
                "features": [{"type": "dice", "req": ["r" * 21]}],
                "requirements": [{"id": "r1", "want": "بازی تاس", "status": "covered", "features": ["dice"]}],
            }, require_requirements=True, expected_intent="create")


    def test_generic_shell_cannot_count_as_meaningful_coverage(self):
        sp = {"features": [{"type": "about", "params": {}}],
              "requirements": [{"id": "r1", "want": "مدیریت گروه و حذف پیام", "part": "منوی شروع",
                                "status": "covered", "features": ["about"]}]}
        self.assertFalse(cov.has_meaningful_coverage(sp))

    def test_requested_start_menu_can_count_when_it_is_the_actual_request(self):
        sp = {"features": [{"type": "start_menu", "params": {}}],
              "requirements": [{"id": "r1", "want": "منوی شروع ربات", "part": "منوی شروع",
                                "status": "covered", "features": ["start_menu"]}]}
        self.assertTrue(cov.has_meaningful_coverage(sp))

    def test_coverage_report_does_not_claim_behavior_test_without_scenario(self):
        about = {"features": [{"type": "about", "params": {}}],
                 "requirements": [{"id": "r1", "want": "درباره ما", "status": "covered", "features": ["about"]}]}
        report = cov.coverage_report(about)
        self.assertEqual(report["requirements"][0]["verification"], "structural_only")
        self.assertFalse(report["all_behavior_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
