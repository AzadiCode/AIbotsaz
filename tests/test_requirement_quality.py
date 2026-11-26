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
        self.assertEqual(defect.get("suggested_capability"), "group_manager")

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


    def test_operation_intent_is_authoritative_not_model_supplied(self):
        payload = {
            "version": "v1", "intent": "create", "name": "مدیر گروه", "features": [],
            "requirements": [{"id": "r1", "want": "مدیریت گروه", "part": "گروه",
                              "status": "covered", "features": ["group_manager"]}],
        }
        validated = spec.validate_spec(payload, require_requirements=True, expected_intent="edit")
        self.assertEqual(validated["intent"], "edit")
        self.assertIn("group_manager", [f["type"] for f in validated["features"]])

    def test_actual_group_request_variants_match_existing_module(self):
        variants = (
            "اجرای دستورات مدیریتی و نظارتی در محیط گروه",
            "فعالیت و مدیریت ربات در داخل گروه",
            "مدیریت و نظارت ربات در گروه",
        )
        for want in variants:
            with self.subTest(want=want):
                self.assertIn("group_manager", [x["id"] for x in cov.catalog_candidates(want)])

    def test_actual_private_group_settings_variants_match_existing_module(self):
        variants = (
            "دسترسی به پنل تنظیمات و پیکربندی ربات در محیط پی‌وی",
            "انجام تنظیمات ربات از طریق پیام خصوصی (PV)",
            "دسترسی به پنل تنظیمات ربات در چت خصوصی پیوی",
        )
        for want in variants:
            with self.subTest(want=want):
                self.assertIn("group_manager", [x["id"] for x in cov.catalog_candidates(want)])

    def test_original_combined_request_matches_group_module(self):
        want = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        self.assertIn("group_manager", [x["id"] for x in cov.catalog_candidates(want)])

    def test_personal_private_account_settings_do_not_match_group_manager(self):
        want = "تنظیمات حساب شخصی از طریق پیام خصوصی"
        self.assertNotIn("group_manager", [x["id"] for x in cov.catalog_candidates(want)])

    def test_spec_recovers_missing_top_level_features_before_coverage_validation(self):
        payload = {
            "intent": "create", "name": "مدیر گروه", "features": [],
            "requirements": [
                {"id": "r1", "want": "اجرای دستورات مدیریتی و نظارتی در محیط گروه", "part": "گروه",
                 "status": "covered", "features": []},
                {"id": "r2", "want": "دسترسی به پنل تنظیمات و پیکربندی ربات در محیط پی‌وی", "part": "پیوی",
                 "status": "covered", "features": []},
            ],
        }
        validated = spec.validate_spec(payload, require_requirements=True, expected_intent="edit")
        self.assertEqual(validated["intent"], "edit")
        self.assertEqual([f["type"] for f in validated["features"]], ["group_manager"])
        self.assertEqual([r["status"] for r in validated["requirements"]], ["covered", "covered"])
        self.assertEqual([r["features"] for r in validated["requirements"]],
                         [["group_manager"], ["group_manager"]])
        self.assertEqual(cov.unmet_items(validated), [])

    def test_spec_recovers_feature_named_on_requirement_but_omitted_from_feature_array(self):
        payload = {
            "intent": "create", "name": "مدیر گروه", "features": [],
            "requirements": [{"id": "r1", "want": "فعالیت و مدیریت ربات در داخل گروه", "part": "گروه",
                              "status": "covered", "features": ["group_manager"]}],
        }
        validated = spec.validate_spec(payload, require_requirements=True, expected_intent="edit")
        self.assertEqual([f["type"] for f in validated["features"]], ["group_manager"])
        self.assertEqual(validated["requirements"][0]["status"], "covered")

    def test_unlinked_covered_requirement_becomes_reviewable_gap_not_spec_crash(self):
        payload = {
            "intent": "create", "name": "x", "features": [],
            "requirements": [{"id": "r1", "want": "قابلیت خیالی برای کنترل ذهن کاربران", "part": "گروه",
                              "status": "covered", "features": []}],
        }
        validated = spec.validate_spec(payload, require_requirements=True, expected_intent="create")
        self.assertEqual(validated["requirements"][0]["status"], "catalog_missing")
        gaps = cov.unmet_items(validated)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["kind"], "CATALOG_MISSING")


    def test_realistic_production_spec_variants_are_recovered_before_retry_failure(self):
        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {
            "version": "BUILD 3.6.2", "intent": "create", "name": "ربات من", "features": [],
            "requirements": [
                {"id": "r1", "want": "اجرای دستورات مدیریتی و نظارتی در محیط گروه",
                 "part": "محیط گروه", "status": "covered", "features": []},
                {"id": "r2", "want": "دسترسی به پنل تنظیمات و پیکربندی ربات در محیط پی‌وی",
                 "part": "پیوی", "status": "covered", "features": []},
            ],
        }
        validated = spec.validate_spec(payload, require_requirements=True,
                                        expected_intent="edit", request_context=context)
        self.assertEqual(validated["intent"], "edit")
        self.assertEqual([f["type"] for f in validated["features"]], ["group_manager"])
        self.assertEqual([r["status"] for r in validated["requirements"]], ["covered", "covered"])
        self.assertEqual(cov.unmet_items(validated, context), [])
        report = cov.coverage_report(validated)
        self.assertEqual(report["covered"], 2)
        self.assertTrue(all("مدیر گروه" in r["evidence"] for r in report["requirements"]))

    def test_private_settings_clause_uses_only_relevant_original_group_context(self):
        request = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {"features": [], "requirements": [
            {"id": "r1", "want": "فعالیت و مدیریت ربات در داخل گروه", "part": "گروه",
             "status": "covered", "features": []},
            {"id": "r2", "want": "تنظیمات ربات در گفتگوی خصوصی", "part": "پیوی",
             "status": "covered", "features": []},
        ]}
        with_context = spec.validate_spec(payload, require_requirements=True,
                                          expected_intent="create", request_context=request)
        self.assertEqual([r["status"] for r in with_context["requirements"]], ["covered", "covered"])
        without_context = spec.validate_spec(payload, require_requirements=True,
                                             expected_intent="create", request_context="تنظیمات حساب شخصی در پیوی")
        self.assertEqual(without_context["requirements"][1]["status"], "catalog_missing")


    def test_model_catalog_missing_status_cannot_override_existing_selected_module(self):
        # Models are inconsistent about status fields. If the actual module is
        # registered and semantically matches, deterministic reconciliation wins.
        phrases = (
            "اجرای دستورات مدیریتی و نظارتی در محیط گروه",
            "دسترسی به پنل تنظیمات و پیکربندی ربات در محیط پی‌وی",
            "تنظیمات ربات در چت خصوصی (پی‌وی)",
        )
        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        for status in ("catalog_missing", "engine_limit"):
            for want in phrases:
                with self.subTest(status=status, want=want):
                    payload = {
                        "intent": "create", "name": "ربات من",
                        "features": [{"type": "group_manager", "params": {}, "req": ["r1"]}],
                        "requirements": [{"id": "r1", "want": want, "part": "گروه/پیوی",
                                          "status": status, "features": ["group_manager"]}],
                    }
                    validated = spec.validate_spec(payload, require_requirements=True,
                                                   expected_intent="edit", request_context=context)
                    self.assertEqual(validated["intent"], "edit")
                    self.assertEqual(validated["requirements"][0]["status"], "covered")
                    self.assertEqual(validated["requirements"][0]["features"], ["group_manager"])
                    self.assertEqual(cov.unmet_items(validated, context), [])

    def test_exact_report_payloads_parse_and_reconcile_deterministically(self):
        import json
        import sys
        import types
        from unittest.mock import patch

        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        responses = [
            {
                "intent": "create", "name": "ربات من", "features": [],
                "requirements": [
                    {"id": "r1", "want": "اجرای دستورات مدیریتی و نظارتی در محیط گروه",
                     "source_quote": "مدیریت گروه", "part": "محیط گروه", "status": "covered", "features": []},
                    {"id": "r2", "want": "دسترسی به پنل تنظیمات و پیکربندی ربات در محیط پی‌وی",
                     "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "part": "پیوی", "status": "covered", "features": []},
                ],
            },
            {
                "intent": "edit", "name": "ربات من", "features": [],
                "requirements": [
                    {"id": "r1", "want": "فعالیت و مدیریت ربات در داخل گروه",
                     "source_quote": "در گروه کار کنه", "part": "گروه", "status": "catalog_missing", "features": []},
                    {"id": "r2", "want": "تنظیمات ربات در چت خصوصی (پی‌وی)",
                     "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "part": "پیوی", "status": "catalog_missing", "features": []},
                ],
            },
            {
                "intent": "create", "name": "ربات من",
                "features": [{"type": "group_manager", "params": {}, "req": ["r1", "r2"]}],
                "requirements": [
                    {"id": "r1", "want": "اجرای دستورات مدیریتی و نظارتی در محیط گروه",
                     "source_quote": "مدیریت گروه", "part": "گروه", "status": "engine_limit", "features": ["group_manager"]},
                    {"id": "r2", "want": "دسترسی به پنل تنظیمات ربات از طریق پیام خصوصی",
                     "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "part": "پیوی", "status": "catalog_missing", "features": ["group_manager"]},
                ],
            },
        ]
        ai_stub = types.ModuleType("ai")
        ai_stub._extract_json_object = lambda value: value
        with patch.dict(sys.modules, {"ai": ai_stub}):
            for raw_obj in responses:
                with self.subTest(response=raw_obj):
                    raw = json.dumps(raw_obj, ensure_ascii=False)
                    parsed = spec.parse_llm_spec(raw, require_requirements=True,
                                                  expected_intent="edit", request_context=context)
                    self.assertEqual(parsed["intent"], "edit")
                    self.assertIn("group_manager", [f["type"] for f in parsed["features"]])
                    self.assertTrue(all(r["status"] == "covered" for r in parsed["requirements"]))
                    self.assertEqual(cov.unmet_items(parsed, context), [])

    def test_validation_does_not_mutate_reused_model_payload(self):
        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {"features": [], "requirements": [
            {"id": "r1", "want": "فعالیت و مدیریت ربات در داخل گروه", "part": "گروه",
             "status": "covered", "features": []},
            {"id": "r2", "want": "تنظیمات ربات در گفتگوی خصوصی", "part": "پیوی",
             "status": "covered", "features": []},
        ]}
        original = __import__("copy").deepcopy(payload)
        with_context = spec.validate_spec(payload, require_requirements=True,
                                          expected_intent="create", request_context=context)
        without_context = spec.validate_spec(payload, require_requirements=True,
                                             expected_intent="create", request_context="تنظیمات حساب شخصی در پیوی")
        self.assertEqual(payload, original)
        self.assertEqual([r["status"] for r in with_context["requirements"]], ["covered", "covered"])
        self.assertEqual(without_context["requirements"][1]["status"], "catalog_missing")


    def test_combined_group_and_private_settings_requirement_is_recovered_when_one_module_covers_both(self):
        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {
            "intent": "create", "name": "ربات من", "features": [],
            "requirements": [{
                "id": "r1",
                "want": "اجرای دستورات مدیریتی و نظارتی در محیط گروه و امکان تغییر تنظیمات ربات از طریق پیام خصوصی (PV)",
                "part": "گروه و پیوی", "status": "catalog_missing", "features": [],
            }],
        }
        validated = spec.validate_spec(payload, require_requirements=True,
                                       expected_intent="edit", request_context=context)
        self.assertEqual([f["type"] for f in validated["features"]], ["group_manager"])
        self.assertEqual(validated["requirements"][0]["status"], "covered")
        self.assertEqual(validated["requirements"][0]["features"], ["group_manager"])
        self.assertEqual(cov.unmet_items(validated, context), [])

    def test_exact_private_settings_report_phrase_is_not_catalog_missing_in_group_context(self):
        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {
            "intent": "create", "name": "ربات من", "features": [],
            "requirements": [{"id": "r1", "want": "امکان تغییر تنظیمات ربات از طریق پیام خصوصی (PV)",
                              "part": "پیوی", "status": "catalog_missing", "features": []}],
        }
        validated = spec.validate_spec(payload, require_requirements=True,
                                       expected_intent="edit", request_context=context)
        self.assertEqual(validated["requirements"][0]["status"], "covered")
        self.assertEqual(validated["requirements"][0]["features"], ["group_manager"])



    def test_llm_requirements_must_be_grounded_in_exact_user_text(self):
        from unittest.mock import patch
        import json, sys, types
        request = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {"intent": "create", "name": "مدیر گروه", "features": [],
                   "requirements": [{"id": "r1", "want": "شناسه واقعی کاتالوگ",
                                     "source_quote": "شناسه واقعی کاتالوگ", "status": "catalog_missing", "features": []}]}
        ai_stub = types.ModuleType("ai")
        ai_stub._extract_json_object = lambda value: value
        with patch.dict(sys.modules, {"ai": ai_stub}):
            with self.assertRaises(spec.SpecError) as caught:
                spec.parse_llm_spec(json.dumps(payload, ensure_ascii=False), require_requirements=True,
                                    expected_intent="create", request_context=request)
        self.assertTrue(any("source_quote" in err for err in caught.exception.errors))

    def test_unknown_feature_note_does_not_become_a_fabricated_requirement(self):
        payload = {"version": 1, "intent": "create", "name": "مدیر گروه",
                   "features": [{"type": "group_manager", "params": {}, "req": ["r1"]},
                                {"type": "pv_group_db_custom", "params": {}, "req": [],
                                 "note": "نیاز به توسعه اختصاصی برای اتصال تنظیمات PV به دیتابیس گروه"}],
                   "requirements": [{"id": "r1", "want": "مدیریت گروه",
                                     "source_quote": "مدیریت گروه", "status": "covered",
                                     "features": ["group_manager"]}]}
        validated = spec.validate_spec(payload, require_requirements=True, expected_intent="create")
        self.assertEqual(len(validated["requirements"]), 1)
        self.assertEqual(validated["requirements"][0]["want"], "مدیریت گروه")

    def test_group_private_settings_report_phrase_is_recovered_from_user_quote(self):
        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {"version": 1, "intent": "create", "name": "مدیر گروه", "features": [],
                   "requirements": [
                       {"id": "r1", "want": "اجرای دستورات مدیریتی و نظارتی در گروه",
                        "source_quote": "مدیریت گروه", "status": "covered", "features": []},
                       {"id": "r2", "want": "تنظیمات ربات از طریق پیام خصوصی (PV) قابل تغییر باشد",
                        "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "status": "covered", "features": []},
                   ]}
        validated = spec.validate_spec(payload, require_requirements=True, expected_intent="create",
                                       request_context=context, require_grounded_quotes=True)
        self.assertEqual([r["status"] for r in validated["requirements"]], ["covered", "covered"])
        self.assertEqual([f["type"] for f in validated["features"]], ["group_manager"])


    def test_engineering_note_is_dropped_without_poisoning_valid_user_requirements(self):
        import json, sys, types
        from unittest.mock import patch
        request = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {"intent": "create", "name": "مدیر گروه", "features": [{"type": "group_manager", "req": ["r1", "r2"]}],
                   "requirements": [
                       {"id": "r1", "want": "اجرای دستورات مدیریتی در گروه", "source_quote": "در گروه کار کنه", "status": "covered", "features": ["group_manager"]},
                       {"id": "r2", "want": "نیاز به توسعه اختصاصی برای اتصال تنظیمات PV به دیتابیس گروه", "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "status": "covered", "features": ["group_manager"]},
                   ]}
        ai_stub = types.ModuleType("ai")
        ai_stub._extract_json_object = lambda value: value
        with patch.dict(sys.modules, {"ai": ai_stub}):
            parsed = spec.parse_llm_spec(json.dumps(payload, ensure_ascii=False), require_requirements=True,
                                         expected_intent="create", request_context=request)
        self.assertEqual([r["id"] for r in parsed["requirements"]], ["r1"])
        self.assertEqual([f["type"] for f in parsed["features"]], ["group_manager"])
        self.assertEqual(cov.unmet_items(parsed, request), [])

    def test_duplicate_source_quotes_cannot_split_one_user_clause_into_fake_requirements(self):
        import json, sys, types
        from unittest.mock import patch
        request = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {"intent": "create", "name": "مدیر گروه", "features": [],
                   "requirements": [
                       {"id": "r1", "want": "مدیریت گروه", "source_quote": "مدیریت گروه", "status": "covered", "features": []},
                       {"id": "r2", "want": "تنظیمات خصوصی گروه", "source_quote": "مدیریت گروه", "status": "covered", "features": []},
                   ]}
        ai_stub = types.ModuleType("ai")
        ai_stub._extract_json_object = lambda value: value
        with patch.dict(sys.modules, {"ai": ai_stub}):
            with self.assertRaises(spec.SpecError) as caught:
                spec.parse_llm_spec(json.dumps(payload, ensure_ascii=False), require_requirements=True,
                                    expected_intent="create", request_context=request)
        self.assertTrue(any("source_quote تکراری" in err for err in caught.exception.errors))

    def test_model_note_does_not_reconcile_an_unrequested_database_requirement(self):
        context = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        req = {"id": "r2", "want": "نیاز به توسعه اختصاصی برای اتصال تنظیمات PV به دیتابیس گروه",
               "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "part": "پیوی",
               "status": "covered", "features": ["group_manager"],
               "source": "catalog_reconciliation_context"}
        self.assertFalse(cov._served_by(req, {"group_manager"}, context))
        defect = cov.classify_uncovered(req, context, {"group_manager"})
        self.assertEqual(defect["kind"], "BUILD_DEFECT")
        self.assertIn("database", defect["evidence"] or defect["why"])

    def test_exact_real_request_parses_to_two_user_requirements_and_one_existing_module(self):
        import json, sys, types
        from unittest.mock import patch
        request = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {"intent": "create", "name": "مدیر گروه", "features": [],
                   "requirements": [
                       {"id": "r1", "want": "مدیریت و نظارت ربات در گروه", "source_quote": "مدیریت گروه", "part": "گروه", "status": "covered", "features": []},
                       {"id": "r2", "want": "تنظیمات ربات از طریق پیام خصوصی قابل تغییر باشد", "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "part": "پیوی", "status": "covered", "features": []},
                   ]}
        ai_stub = types.ModuleType("ai")
        ai_stub._extract_json_object = lambda value: value
        with patch.dict(sys.modules, {"ai": ai_stub}):
            parsed = spec.parse_llm_spec(json.dumps(payload, ensure_ascii=False), require_requirements=True,
                                         expected_intent="create", request_context=request)
        self.assertEqual(len(parsed["requirements"]), 2)
        self.assertEqual([f["type"] for f in parsed["features"]], ["group_manager"])
        self.assertEqual(cov.unmet_items(parsed, request), [])



    def test_exact_latest_report_is_recovered_and_fabricated_pv_database_row_is_dropped(self):
        import json, sys, types
        from unittest.mock import patch
        request = "یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد"
        payload = {
            "intent": "create", "name": "ربات من",
            "features": [{"type": "group_manager", "req": ["r1", "r2", "r3"]}],
            "requirements": [
                {"id": "r1", "want": "تنظیمات ربات از طریق پیام خصوصی (PV) قابل تغییر باشد",
                 "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "part": "پیوی",
                 "status": "covered", "features": ["group_manager"]},
                {"id": "r2", "want": "نیاز به توسعه اختصاصی برای اتصال تنظیمات PV به دیتابیس گروه",
                 "source_quote": "در پیویش هم تنظیماتشو بشه تنجام داد", "part": "پیوی",
                 "status": "covered", "features": ["group_manager"]},
                {"id": "r3", "want": "اجرای دستورات مدیریتی و نظارتی در گروه",
                 "source_quote": "در گروه کار کنه", "part": "گروه",
                 "status": "covered", "features": ["group_manager"]},
            ],
        }
        ai_stub = types.ModuleType("ai")
        ai_stub._extract_json_object = lambda value: value
        with patch.dict(sys.modules, {"ai": ai_stub}):
            parsed = spec.parse_llm_spec(json.dumps(payload, ensure_ascii=False), require_requirements=True,
                                         expected_intent="create", request_context=request)
        self.assertEqual({r["id"] for r in parsed["requirements"]}, {"r1", "r3"})
        self.assertEqual([f["type"] for f in parsed["features"]], ["group_manager"])
        self.assertEqual(cov.unmet_items(parsed, request), [])


    def test_model_cannot_forge_requirement_provenance(self):
        rows, errors = cov.norm_requirements([{
            "id": "r1", "want": "مدیریت گروه", "source": "salvage"
        }])
        self.assertFalse(errors)
        self.assertEqual(rows[0]["source"], "model")

    def test_spec_prompt_exposes_private_group_settings_alias(self):
        system = spec.spec_prompt("یه ربات مدیریت گروه بساز که در گروه کار کنه و در پیویش هم تنظیماتشو بشه تنجام داد")[0]["content"]
        self.assertIn("تنظیمات ربات از طریق پیام خصوصی", system)
        self.assertIn("تنظیمات گروه در پیوی", system)

    def test_edit_context_is_not_truncated_into_invalid_json(self):
        import json
        summary = json.dumps({"name": "ربات", "start": "start", "node_count": 5,
                              "node_index": [[f"node_{i}", "عنوان"] for i in range(100)],
                              "node_index_truncated": 0, "relevant_nodes": [],
                              "vars": [f"v{i}" for i in range(40)], "globals": [], "commands": [],
                              "configured_sections": ["group"]}, ensure_ascii=False)
        system = spec.spec_prompt("یک قابلیت به ربات فعلی اضافه کن", summary)[0]["content"]
        marker = "خلاصهٔ ساختاری فعلی به‌صورت JSON معتبر (فقط زمینه، نه نیازمندی جدید):\n"
        packed = system.split(marker, 1)[1]
        parsed = json.loads(packed)
        self.assertEqual(parsed["name"], "ربات")
        self.assertLessEqual(len(packed), 2300)

    def test_spec_prompt_has_no_copyable_catalog_placeholder(self):
        system = spec.spec_prompt("یه ربات مدیریت گروه بساز")[0]["content"]
        self.assertNotIn("شناسه واقعی کاتالوگ", system)
        self.assertNotIn("شناسه واقعی قابلیت", system)
        self.assertIn("source_quote", system)
        self.assertIn("source_quote تنها مدرک مجاز", system)


if __name__ == "__main__":
    unittest.main(verbosity=2)
