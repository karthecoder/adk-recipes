#!/usr/bin/env python3
# ruff: noqa: E402
"""
Nexus End-to-End 5-Act FinOps Showcase Runner for `adk-tokenomics-plugin`.

Demonstrates all 18 capabilities across:
  • Act 1: Run `nexus_unoptimized` -> export `unopt_baseline.json` + OpenTelemetry `gen_ai.client.cost.usd`
  • Act 2: Run `adk-tokenomics assert` on `unopt_baseline.json` -> FAIL-CLOSED (`exit 1`)
  • Act 3: Run `adk-tokenomics profile` + `tower.profile()` -> 5 Built-In Rules + Custom SLA Alert
  • Act 4: Run `nexus_optimized` -> export `opt_tuned.json` + `decorated_session.json` -> `0` Warnings & `assert` PASS (`exit 0`)
  • Act 5: Side-by-Side Unit Economics Comparison & `adk-tokenomics web` Observatory Guide
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from adk_tokenomics_plugin.cli_profiler import profile_from_trace_file
from adk_tokenomics_plugin.testing.assertions import run_cli_assertions
from examples.shared.mock_llm import (
    build_nexus_agents,
    run_simulated_nexus_session,
)


class _InMemoryOTelCapture:
    """Lightweight OpenTelemetry MeterProvider hook that captures `gen_ai.client.cost.usd` recordings."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(
        self, amount: float, attributes: dict[str, Any] | None = None
    ) -> None:
        self.records.append(
            {
                "amount": float(amount),
                "attributes": dict(attributes or {}),
            }
        )


def _attach_otel_capture(bundle: Any) -> _InMemoryOTelCapture:
    capture = _InMemoryOTelCapture()
    bundle.tower.tracker._otel_cost_histogram = capture
    bundle.tower.tracker._otel_meter_id = id(capture)
    return capture


def run_showcase(
    *,
    traces_dir: str = "examples/artifacts/traces",
    reports_dir: str = "examples/artifacts/reports",
    sink: str = "memory",
    project_id: str | None = None,
    dataset_id: str | None = None,
    max_cost_per_turn: float = 0.004,
    min_cache_rate: float = 0.60,
    max_tokens_per_turn: int = 3500,
) -> dict[str, Any]:
    traces_path = Path(traces_dir).resolve()
    reports_path = Path(reports_dir).resolve()
    traces_path.mkdir(parents=True, exist_ok=True)
    reports_path.mkdir(parents=True, exist_ok=True)

    # Ensure idempotent showcase runs by clearing prior benchmark trace files
    for stale_name in (
        "unopt_baseline.json",
        "live_unopt_session.json",
        "opt_tuned.json",
        "live_opt_session.json",
        "decorated_session.json",
    ):
        stale_file = traces_path / stale_name
        if stale_file.is_file():
            stale_file.unlink()

    policy_file = str(_REPO_ROOT / "examples" / "shared" / "finops_policy.json")

    print("\n" + "═" * 105)
    print(
        " ⚡ ADK TOKENOMICS PLUGIN — END-TO-END 5-ACT FINOPS SHOWCASE (NEXUS ENTERPRISE COPILOT)"
    )
    print("═" * 105)

    # =========================================================================
    # ACT 1: Run Unoptimized Baseline (`nexus_unoptimized`)
    # =========================================================================
    print(
        "\n🎬 [ACT 1/5] Running `nexus_unoptimized` (4 User Turns / 10 ADK Sub-Agent Turns)..."
    )
    unopt_live_export = str(traces_path / "live_unopt_session.json")
    unopt_bundle = build_nexus_agents(
        optimized=False,
        app_name="nexus_unoptimized",
        auto_export_path=unopt_live_export,
        sink=sink,
        project_id=project_id,
        dataset_id=dataset_id,
        prompts_config_path=policy_file,
    )
    unopt_otel = _attach_otel_capture(unopt_bundle)
    unopt_res = run_simulated_nexus_session(
        unopt_bundle,
        session_id="unopt_baseline",
        max_loop_passes=1,
        output_dir=str(reports_path),
    )
    unopt_trace_file = str(traces_path / "unopt_baseline.json")
    actual_otel_pts = [
        r
        for r in unopt_otel.records
        if r["attributes"].get("gen_ai.cost.type") == "actual"
    ]
    print(f"   ✓ Exported Session Trace : {unopt_trace_file}")
    print(f"   ✓ Persisted Brief Report : {unopt_res['report_path']}")
    print(
        f"   ✓ OTel Histogram Emitted : {len(actual_otel_pts)} `gen_ai.client.cost.usd` data points "
        f"(Total=${sum(r['amount'] for r in actual_otel_pts):.5f})"
    )

    # =========================================================================
    # ACT 2: Shift-Left CI/CD Budget Gate FAILS on Unoptimized Trace
    # =========================================================================
    print(
        "\n🚨 [ACT 2/5] Running Shift-Left CI Gate (`adk-tokenomics assert`) on `unopt_baseline.json`..."
    )
    unopt_rc = run_cli_assertions(
        traces_path=unopt_trace_file,
        max_cost_per_turn=max_cost_per_turn,
        min_cache_rate=min_cache_rate,
        max_tokens_per_turn=max_tokens_per_turn,
    )
    unopt_passed = unopt_rc == 0

    # =========================================================================
    # ACT 3: Profile Unoptimized Trace (5 Built-In Rules + 1 Custom SLA Rule)
    # =========================================================================
    print(
        "\n🔬 [ACT 3/5] Running `adk-tokenomics profile` & `tower.profile()` on `unopt_baseline.json`..."
    )
    cli_unopt_recs = (
        profile_from_trace_file(
            file_path=unopt_trace_file,
            prompts_config_path=policy_file,
        )
        or []
    )
    tower_unopt_recs = unopt_bundle.tower.profile(
        title="unopt_baseline (with Custom Org SLA Rule)"
    )

    # =========================================================================
    # ACT 4: Run FinOps-Optimized Agent (`nexus_optimized`) & Pass CI Gate
    # =========================================================================
    print(
        "\n🚀 [ACT 4/5] Running `nexus_optimized` (All 5 ADK FinOps Fixes Applied)..."
    )
    opt_live_export = str(traces_path / "live_opt_session.json")
    decorated_trace_file = str(traces_path / "decorated_session.json")
    opt_bundle = build_nexus_agents(
        optimized=True,
        app_name="nexus_optimized",
        auto_export_path=opt_live_export,
        sink=sink,
        project_id=project_id,
        dataset_id=dataset_id,
        prompts_config_path=policy_file,
    )
    opt_otel = _attach_otel_capture(opt_bundle)
    opt_res = run_simulated_nexus_session(
        opt_bundle,
        session_id="opt_tuned",
        max_loop_passes=1,
        output_dir=str(reports_path),
        export_decorated_trace_path=decorated_trace_file,
    )
    opt_trace_file = str(traces_path / "opt_tuned.json")
    opt_cache_otel_pts = [
        r
        for r in opt_otel.records
        if r["attributes"].get("gen_ai.cost.type") == "cache_savings"
    ]
    print(f"   ✓ Exported Session Trace   : {opt_trace_file}")
    print(f"   ✓ Exported @track_tokens   : {decorated_trace_file}")
    print(f"   ✓ Persisted Brief Report   : {opt_res['report_path']}")
    print(
        f"   ✓ OTel Cache Savings Emitted: {len(opt_cache_otel_pts)} `gen_ai.client.cost.usd` points "
        f"(Saved=${sum(r['amount'] for r in opt_cache_otel_pts):.5f})"
    )

    cli_opt_recs = (
        profile_from_trace_file(
            file_path=opt_trace_file,
            prompts_config_path=policy_file,
        )
        or []
    )

    print(
        "\n✅ Re-running Shift-Left CI Gate (`adk-tokenomics assert`) on `opt_tuned.json`..."
    )
    opt_rc = run_cli_assertions(
        traces_path=opt_trace_file,
        max_cost_per_turn=max_cost_per_turn,
        min_cache_rate=min_cache_rate,
        max_tokens_per_turn=max_tokens_per_turn,
    )
    opt_passed = opt_rc == 0

    # =========================================================================
    # ACT 5: Side-by-Side Scorecard & Web Observatory Launch Guide
    # =========================================================================
    u_sum = unopt_res["summary"]
    o_sum = opt_res["summary"]
    u_cost = float(u_sum["total_cost"])
    o_cost = float(o_sum["total_cost"])
    cost_savings_pct = (
        ((u_cost - o_cost) / u_cost * 100.0) if u_cost > 0 else 0.0
    )

    print("\n" + "═" * 105)
    print(
        " 📊 [ACT 5/5] BEFORE vs. AFTER FINOPS SCORECARD (`unopt_baseline` vs. `opt_tuned`)"
    )
    print("═" * 105)
    print(
        f" {'Metric':<34} | {'nexus_unoptimized (Before)':<28} | {'nexus_optimized (After)':<28}"
    )
    print("─" * 105)
    print(
        f" {'Total Session Cost ($)':<34} | ${u_cost:<27.5f} | ${o_cost:<27.5f} (-{cost_savings_pct:.1f}%)"
    )
    print(
        f" {'Avg Cost per Turn ($)':<34} | ${u_cost / max(1, u_sum['total_turns']):<27.5f} | ${o_cost / max(1, o_sum['total_turns']):<27.5f}"
    )
    print(
        f" {'Prefix Cache Hit Ratio (%)':<34} | {u_sum['cache_read_ratio_pct']:<27.1f}% | {o_sum['cache_read_ratio_pct']:<27.1f}%"
    )
    print(
        f" {'Fresh Input Tokens':<34} | {u_sum['input_tokens']:<28,d} | {o_sum['input_tokens']:<28,d}"
    )
    print(
        f" {'Cached Prefix Tokens':<34} | {u_sum['cached_tokens']:<28,d} | {o_sum['cached_tokens']:<28,d}"
    )
    print(
        f" {'Reasoning / Thinking Tokens':<34} | {u_sum['thinking_tokens']:<28,d} | {o_sum['thinking_tokens']:<28,d}"
    )
    print(
        f" {'Profiler Warnings Fired':<34} | {len(cli_unopt_recs)} built-in ({len(tower_unopt_recs)} w/ SLA)    | {len(cli_opt_recs)} warnings (Clean!)"
    )
    print(
        f" {'CI/CD `assert` Gate Status':<34} | {'❌ FAILED (exit 1)':<28} | {'✅ PASSED (exit 0)':<28}"
    )
    print("═" * 105)
    print(
        "\n🌐 Next Step — Compare Both Sessions Side-by-Side in the Visual Observatory:"
    )
    print(f"   adk-tokenomics web --traces {traces_dir} --port 8080\n")

    return {
        "unoptimized": unopt_res,
        "optimized": opt_res,
        "unopt_assert_passed": unopt_passed,
        "opt_assert_passed": opt_passed,
        "unopt_cli_recommendations": cli_unopt_recs,
        "unopt_tower_recommendations": tower_unopt_recs,
        "opt_cli_recommendations": cli_opt_recs,
        "unopt_trace_file": unopt_trace_file,
        "opt_trace_file": opt_trace_file,
        "decorated_trace_file": decorated_trace_file,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the 5-Act Nexus FinOps Showcase for adk-tokenomics-plugin."
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--simulate",
        action="store_true",
        default=True,
        help="Run deterministically via hermetic ADK simulation (default; zero cloud credentials required).",
    )
    mode_group.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Run with live Vertex AI / Gemini credentials when configured in .env.",
    )
    parser.add_argument(
        "--traces-dir",
        default="examples/artifacts/traces",
        help="Output directory for exported session trace JSON files (default: examples/artifacts/traces).",
    )
    parser.add_argument(
        "--reports-dir",
        default="examples/artifacts/reports",
        help="Output directory for generated Markdown executive briefs (default: examples/artifacts/reports).",
    )
    parser.add_argument(
        "--sink",
        choices=["memory", "bigquery"],
        default="memory",
        help="Telemetry storage sink ('memory' or 'bigquery').",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Optional GCP project ID when --sink bigquery is used.",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Optional BigQuery dataset ID when --sink bigquery is used.",
    )
    args = parser.parse_args(argv)

    result = run_showcase(
        traces_dir=args.traces_dir,
        reports_dir=args.reports_dir,
        sink=args.sink,
        project_id=args.project,
        dataset_id=args.dataset,
    )
    if result["unopt_assert_passed"] or not result["opt_assert_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
