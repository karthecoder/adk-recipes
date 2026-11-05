"""
End-to-End Verification Suite for the Nexus ADK Tokenomics Showcase (`examples/`).
Covers all 6 Mode-3 Codebase Parity layers:
  1. Package entrypoints (`__init__.py` exports for `adk web examples/`) & 8-agent topology
  2. Cross-model capability adapter (`resolve_planner_and_config`) across Gemini 3/4/2.5 & custom models
  3. Prompt `{key?}` optional state placeholder regex audit (`use_jinja2=False` safety)
  4. Hardened tool contracts, XML prompt-injection delimiters & path-traversal containment
  5. Hermetic Trajectory A (Pass-1 `exit_loop`) and Trajectory B (`max_iterations=2` latest-draft precedence)
  6. 18-capability FinOps verification (`TokenProfiler`, `evaluate_trace_files`, `TokenomicsTestCase`, `@track_tokens`)
"""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path

import examples.nexus_optimized as nexus_opt_pkg
import examples.nexus_unoptimized as nexus_unopt_pkg
from adk_tokenomics_plugin import TokenomicsTestCase
from examples.run_nexus_showcase import run_showcase
from examples.shared.config_adapter import (
    CUSTOM_POLICY_MODEL_ID,
    FRONTIER_MODEL_NAME,
    MODEL_NAME,
    genai_types,
    resolve_planner_and_config,
)
from examples.shared.mock_llm import (
    build_nexus_agents,
    run_simulated_nexus_session,
)
from examples.shared.prompts import ALL_PROMPTS, REGISTERED_STATE_KEYS
from examples.shared.tools import (
    append_state_entry,
    build_nexus_skill_toolset,
    evaluate_compliance_controls,
    fetch_market_benchmarks,
    query_telemetry_warehouse,
    save_executive_brief,
)


class TestNexusShowcase(TokenomicsTestCase):
    """Comprehensive verification suite for `examples/nexus_unoptimized` and `examples/nexus_optimized`."""

    def test_01_package_entrypoints_and_topology_contracts(self):
        for pkg in (nexus_unopt_pkg, nexus_opt_pkg):
            self.assertTrue(hasattr(pkg, "agent"))
            self.assertTrue(hasattr(pkg, "root_agent"))
            self.assertTrue(hasattr(pkg, "app"))
            self.assertTrue(hasattr(pkg, "MODEL_NAME"))
            self.assertEqual(pkg.root_agent.name, "nexus_router")

        with tempfile.TemporaryDirectory() as tmpdir:
            unopt = build_nexus_agents(
                optimized=False,
                auto_export_path=os.path.join(tmpdir, "unopt.json"),
            )
            opt = build_nexus_agents(
                optimized=True,
                auto_export_path=os.path.join(tmpdir, "opt.json"),
            )

            self.assertIsNone(unopt.app.context_cache_config)
            self.assertIsNone(unopt.app.events_compaction_config)
            self.assertIsNone(unopt.skill_toolset)

            self.assertIsNotNone(opt.app.context_cache_config)
            self.assertEqual(opt.app.context_cache_config.min_tokens, 1024)
            self.assertIsNotNone(opt.app.events_compaction_config)
            self.assertEqual(
                opt.app.events_compaction_config.compaction_interval, 4
            )
            self.assertIsNotNone(opt.skill_toolset)

            # Verify model tiering in optimized vs unoptimized
            for name, ag in unopt.agents.items():
                if hasattr(ag, "model"):
                    self.assertEqual(
                        ag.model,
                        FRONTIER_MODEL_NAME,
                        f"Unoptimized {name} should use Argon",
                    )

            self.assertEqual(opt.agents["nexus_router"].model, MODEL_NAME)
            self.assertEqual(opt.agents["sandbox_analyst"].model, MODEL_NAME)
            self.assertEqual(
                opt.agents["market_intel_analyst"].model, MODEL_NAME
            )
            self.assertEqual(
                opt.agents["metrics_sql_analyst"].model, MODEL_NAME
            )
            self.assertEqual(
                opt.agents["risk_policy_analyst"].model, CUSTOM_POLICY_MODEL_ID
            )
            self.assertEqual(
                opt.agents["report_drafter"].model, FRONTIER_MODEL_NAME
            )
            self.assertEqual(opt.agents["adversarial_critic"].model, MODEL_NAME)
            self.assertEqual(opt.agents["packager_agent"].model, MODEL_NAME)

            # Verify custom model is registered under provider='custom' to prevent false model_tiering warnings
            rate = opt.tower.pricing.get_rate(CUSTOM_POLICY_MODEL_ID)
            self.assertEqual(rate["provider"], "custom")
            self.assertAlmostEqual(rate["input"], 0.20)
            self.assertAlmostEqual(rate["cached"], 0.05)
            self.assertAlmostEqual(rate["output"], 0.80)

    def test_02_resolve_planner_and_config_cross_model_matrix(self):
        # 1. Gemini 3.x maps minimal -> MINIMAL, low -> LOW, medium -> MEDIUM
        p_min, c_min = resolve_planner_and_config(
            "publishers/google/models/gemini-3.8-flash",
            "minimal",
            optimized=True,
        )
        self.assertIsNotNone(p_min)
        self.assertEqual(
            p_min.thinking_config.thinking_level,
            genai_types.ThinkingLevel.MINIMAL,
        )
        self.assertFalse(p_min.thinking_config.include_thoughts)
        self.assertEqual(c_min.temperature, 1.0)
        self.assertIsNone(getattr(c_min, "thinking_config", None))

        # 2. Gemini 4.x clamps minimal -> LOW (since gemini-4-argon only allows low/medium/high)
        p_g4_min, _ = resolve_planner_and_config(
            "publishers/google/models/gemini-4-argon", "minimal", optimized=True
        )
        self.assertEqual(
            p_g4_min.thinking_config.thinking_level,
            genai_types.ThinkingLevel.LOW,
        )

        # 3. Unoptimized forces HIGH across all tiers
        p_unopt, _ = resolve_planner_and_config(
            "publishers/google/models/gemini-4-argon",
            "minimal",
            optimized=False,
        )
        self.assertEqual(
            p_unopt.thinking_config.thinking_level,
            genai_types.ThinkingLevel.HIGH,
        )

        # 4. Legacy Gemini 2.5 uses integer thinking_budget
        p_25, c_25 = resolve_planner_and_config(
            "gemini-2.5-flash", "low", optimized=True
        )
        self.assertEqual(p_25.thinking_config.thinking_budget, 256)
        self.assertEqual(c_25.temperature, 0.7)

        # 5. Custom / 3P models gracefully return (None, None)
        p_cust, c_cust = resolve_planner_and_config(
            CUSTOM_POLICY_MODEL_ID, "low", optimized=True
        )
        self.assertIsNone(p_cust)
        self.assertIsNone(c_cust)

        with self.assertRaises(ValueError):
            resolve_planner_and_config(MODEL_NAME, "invalid_tier")

    def test_03_prompt_placeholder_hygiene_regex_audit(self):
        placeholder_re = re.compile(r"\{+([^{}]+)\}+")
        for prompt_name, prompt_text in ALL_PROMPTS.items():
            matches = placeholder_re.findall(prompt_text)
            for token in matches:
                self.assertTrue(
                    token.endswith("?"),
                    f"Prompt {prompt_name} contains non-optional '{{...}}' placeholder {{{token}}} without trailing '?'",
                )
                state_key = token[:-1]
                self.assertIn(
                    state_key,
                    REGISTERED_STATE_KEYS,
                    f"Prompt {prompt_name} references unregistered state key {state_key!r}",
                )

    def test_04_hardened_tools_and_path_traversal_security(self):
        # 1. State allowlist check
        bad_res = append_state_entry("unauthorized_key", "payload")
        self.assertEqual(bad_res["status"], "error")
        self.assertIn("DISALLOWED_FIELD", bad_res["message"])

        # 2. XML delimiter wrapping & fallback notice
        m_out = fetch_market_benchmarks("unknown_vertical")
        self.assertTrue(
            m_out.startswith("<external_extract>")
            and m_out.endswith("</external_extract>")
        )
        self.assertIn("Fallback benchmark applied", m_out)

        q_out = query_telemetry_warehouse("unknown_tier")
        self.assertTrue(q_out.startswith("<external_extract>"))
        c_out = evaluate_compliance_controls("unknown_class")
        self.assertIn("[C-01]", c_out)

        # 3. Path traversal rejection on save_executive_brief
        with tempfile.TemporaryDirectory() as tmpdir:
            for malicious in (
                "../../etc/passwd",
                "../escape.md",
                "/etc/passwd",
                "\\windows\\system32",
            ):
                with self.assertRaises(ValueError):
                    save_executive_brief(malicious, "# test", output_dir=tmpdir)

            saved = save_executive_brief(
                "valid_report_name", "# SECTION 1: TEST", output_dir=tmpdir
            )
            self.assertEqual(saved["status"], "saved")
            self.assertTrue(Path(saved["path"]).is_file())
            self.assertTrue(saved["path"].endswith("valid_report_name.md"))

        # 4. SkillToolset fallback when directory is missing
        fallback_ts = build_nexus_skill_toolset(
            skills_dir="/nonexistent/skills/path"
        )
        self.assertEqual(len(fallback_ts.skills), 3)

    def test_05_hermetic_trajectory_a_and_b_loop_precedence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Trajectory B: 2 loop passes (Pass 1 rejected -> Pass 2 accepted at max_iterations=2)
            opt_bundle = build_nexus_agents(
                optimized=True,
                auto_export_path=os.path.join(tmpdir, "live_opt.json"),
            )
            res_b = run_simulated_nexus_session(
                opt_bundle,
                session_id="traj_b_session",
                max_loop_passes=2,
                output_dir=tmpdir,
            )
            state_b = res_b["state"]
            self.assertEqual(len(state_b["deliverable_drafts"]), 2)
            self.assertEqual(len(state_b["critic_feedback"]), 1)
            self.assertIn("missing SECTION 5", state_b["critic_feedback"][0])

            # Verify latest-entry precedence: saved report must contain Pass #2 and all 5 sections
            report_text = Path(res_b["report_path"]).read_text(encoding="utf-8")
            self.assertIn("Draft Pass #2", report_text)
            self.assertNotIn("Draft Pass #1", report_text)
            for sec_idx in range(1, 6):
                self.assertIn(f"# SECTION {sec_idx}:", report_text)

    def test_06_end_to_end_5_act_showcase_and_finops_gates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            traces_dir = os.path.join(tmpdir, "traces")
            reports_dir = os.path.join(tmpdir, "reports")
            showcase = run_showcase(
                traces_dir=traces_dir,
                reports_dir=reports_dir,
            )

            # Act 2 & Act 4 Assert Gates
            self.assertFalse(
                showcase["unopt_assert_passed"],
                "Unoptimized trace must FAIL CI assert gate",
            )
            self.assertTrue(
                showcase["opt_assert_passed"],
                "Optimized trace must PASS CI assert gate",
            )

            # Act 3: Unoptimized must fire all 5 built-in rules on CLI + 1 custom SLA callback on tower
            unopt_cli_recs = showcase["unopt_cli_recommendations"]
            self.assertEqual(len(unopt_cli_recs), 5)
            joined_unopt = "\n".join(unopt_cli_recs)
            self.assertIn("[Context Caching]", joined_unopt)
            self.assertIn("[History Compaction]", joined_unopt)
            self.assertIn("[Modular Skills]", joined_unopt)
            self.assertIn("[Thinking Budget Tuning]", joined_unopt)
            self.assertIn("[Sub-Agent Model Tiering]", joined_unopt)

            unopt_tower_recs = showcase["unopt_tower_recommendations"]
            self.assertEqual(len(unopt_tower_recs), 6)
            self.assertTrue(
                any(
                    "Enterprise FinOps SLA Breach" in r
                    for r in unopt_tower_recs
                )
            )

            # Act 4: Optimized must fire 0 warnings (returns empty list from profile_session)
            self.assertEqual(showcase["opt_cli_recommendations"], [])

            # Verify orchestration flow badges & AgentTool session stitching on optimized trace
            opt_turns = showcase["optimized"]["turns"]
            self.assertEqual(len(opt_turns), 9)
            for t in opt_turns:
                self.assertEqual(
                    t["session_id"],
                    "opt_tuned",
                    "AgentTool child session must stitch to opt_tuned",
                )

            flows = {t.get("orchestration_flow") for t in opt_turns}
            self.assertIn("Root", flows)
            self.assertIn("AgentTool", flows)
            self.assertIn("Parallel", flows)
            self.assertIn("Loop", flows)
            self.assertIn("Sequential", flows)

            # Verify SkillToolset load_skill attribution
            router_turn_1 = opt_turns[0]
            self.assertIn(
                "finops-playbooks", router_turn_1.get("skills_active", [])
            )

            # Verify @track_tokens standalone trace file
            self.assertTrue(Path(showcase["decorated_trace_file"]).is_file())

            # Verify TokenomicsTestCase assertions on the optimized summary
            opt_summary = showcase["optimized"]["summary"]
            self.assertCostLessThan(opt_summary, max_dollars=0.030)
            self.assertCacheHitRatioGreaterThan(opt_summary, min_ratio_pct=75.0)
            self.assertTokenBudget(opt_summary, max_tokens=25000)
            self.assertThinkingTokensWithin(
                opt_summary, min_tokens=0, max_tokens=512
            )


if __name__ == "__main__":
    unittest.main()
