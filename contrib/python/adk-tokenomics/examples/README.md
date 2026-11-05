# ⚡ Nexus — End-to-End ADK Tokenomics & FinOps Reference Copilot

This directory contains the reference multi-agent showcase for **`adk-tokenomics-plugin`**, designed to exercise **all 18 SDK, CLI, OpenTelemetry, and Web Observatory capabilities** across two side-by-side Google ADK agent packages:

- **`examples/nexus_unoptimized/` (`unopt_baseline`):** Demonstrates the 5 classic multi-agent cost anti-patterns (frontier `gemini-4-argon` on every sub-agent, 6,200-token monolithic static system prompt, no `ContextCacheConfig`, no `EventsCompactionConfig`, and unbounded `ThinkingLevel.HIGH` reasoning).
- **`examples/nexus_optimized/` (`opt_tuned`):** Applies the exact 5 Google ADK optimizations recommended by `adk-tokenomics profile` (`gemini-3.8-flash` + custom `custom/nexus-policy-guard-v1` model tiering, `ContextCacheConfig`, `EventsCompactionConfig`, on-demand `SkillToolset` `SKILL.md` modules, and right-sized `BuiltInPlanner` `ThinkingLevel` tiers)—reducing session spend by **86.0%** (`\$0.16220` → `\$0.02272`) and achieving **81.2% prefix cache efficiency**.

---

## 🏗️ Multi-Agent Topology & Orchestration Coverage

```text
🎯 nexus_router (Root LlmAgent + SkillToolset [finops-playbooks, sql-telemetry, compliance-controls])
 ├── 🧰 quant_sandbox_tool (AgentTool — Ephemeral child session stitched to parent session_id)
 │    └── sandbox_analyst (LlmAgent) -> run_roi_monte_carlo -> @track_tokens forecast_unit_economics()
 ├── ➡️ deep_research_pipeline (SequentialAgent)
 │    ├── 1. ⚡ signal_gatherers (ParallelAgent)
 │    │       ├── market_intel_analyst (LlmAgent | output_key="parallel_market_intel")
 │    │       ├── metrics_sql_analyst (LlmAgent | output_key="parallel_metrics_sql")
 │    │       └── risk_policy_analyst (LlmAgent | Model: custom/nexus-policy-guard-v1 | output_key="parallel_risk_policy")
 │    ├── 2. 🔁 deliverable_refiner (LoopAgent, max_iterations=2)
 │    │       ├── report_drafter (LlmAgent | Tier: Medium)
 │    │       └── adversarial_critic (LlmAgent | Tier: Low + BuiltInPlanner + exit_loop)
 │    └── 3. packager_agent (LlmAgent | Tier: Minimal -> saves 5-section brief to artifacts/reports/)
 └── 🔬 audit_session_tokenomics (FunctionTool -> calls tower.get_finops_advisor_prompt())
```

---

## 🚀 Quickstart: Run the 5-Act End-to-End Showcase

```bash
# Run all 5 acts offline in <2 seconds (zero cloud credentials required)
python3 examples/run_nexus_showcase.py --simulate
```

### Individual CLI Commands (Inspecting the Generated Traces)

```bash
# 1. Verify that the unoptimized baseline FAILS the CI/CD budget gate (exit code 1)
adk-tokenomics assert \
  -t examples/artifacts/traces/unopt_baseline.json \
  --max-cost-per-turn 0.004 \
  --min-cache-rate 0.60 \
  --max-tokens-per-turn 3500

# 2. Profile the unoptimized trace to trigger all 5 FinOps optimization recommendations
adk-tokenomics profile \
  -t examples/artifacts/traces/unopt_baseline.json \
  --prompts-file examples/shared/finops_policy.json

# 3. Profile the optimized trace (0 warnings — "✨ Excellent! Session is well-optimized...")
adk-tokenomics profile \
  -t examples/artifacts/traces/opt_tuned.json \
  --prompts-file examples/shared/finops_policy.json

# 4. Verify that the optimized trace PASSES the CI/CD budget gate (exit code 0)
adk-tokenomics assert \
  -t examples/artifacts/traces/opt_tuned.json \
  --max-cost-per-turn 0.004 \
  --min-cache-rate 0.60 \
  --max-tokens-per-turn 3500

# 5. Launch the visual Token Control Tower Web Observatory to compare both sessions side-by-side
adk-tokenomics web --traces examples/artifacts/traces/ --port 8080

# 6. Or open both agents interactively in Google ADK's Web UI
adk web examples/ --port 8000
```
