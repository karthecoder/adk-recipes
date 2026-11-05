"""
Nexus Showcase — Agent Graph Factory & Hermetic ADK Simulation Runner.
Builds the complete 8-agent Nexus hierarchy (`Root`, `AgentTool`, `SequentialAgent`,
`ParallelAgent`, `LoopAgent`, `SkillToolset`) and executes deterministic multi-turn
trajectories through the real `ADKTokenomicsPlugin` callbacks and tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adk_tokenomics_plugin import ADKTokenomicsPlugin, TokenControlTower
from examples.shared.config_adapter import (
    AGENT_REASONING_TIERS,
    FRONTIER_MODEL_NAME,
    MODEL_NAME,
    AgentTool,
    App,
    ContextCacheConfig,
    EventsCompactionConfig,
    FunctionTool,
    InMemoryRunner,
    LlmAgent,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
    ToolContext,
    create_nexus_tower,
    exit_loop,
    resolve_planner_and_config,
)
from examples.shared.prompts import (
    ADVERSARIAL_CRITIC_PROMPT,
    MARKET_INTEL_ANALYST_PROMPT,
    METRICS_SQL_ANALYST_PROMPT,
    NEXUS_ROUTER_OPTIMIZED_PROMPT,
    PACKAGER_AGENT_PROMPT,
    REPORT_DRAFTER_PROMPT,
    RISK_POLICY_ANALYST_PROMPT,
    SANDBOX_ANALYST_PROMPT,
    build_unoptimized_monolithic_router_prompt,
)
from examples.shared.tools import (
    append_state_entry,
    audit_session_tokenomics,
    bind_active_tower,
    build_nexus_skill_toolset,
    evaluate_compliance_controls,
    fetch_market_benchmarks,
    query_telemetry_warehouse,
    record_initiative_context,
    run_roi_monte_carlo,
    save_executive_brief,
)


@dataclass
class NexusAppBundle:
    """Container holding the constructed ADK `App`, `root_agent`, agent map, `TokenControlTower`, and `ADKTokenomicsPlugin`."""

    optimized: bool
    app_name: str
    app: App
    root_agent: LlmAgent
    agents: dict[str, Any]
    quant_sandbox_tool: AgentTool
    skill_toolset: Any | None
    tower: TokenControlTower
    plugin: ADKTokenomicsPlugin
    runner: InMemoryRunner


def build_nexus_agents(
    *,
    optimized: bool = True,
    app_name: str | None = None,
    auto_export_path: str | None = None,
    mode: str = "dev",
    sink: str = "memory",
    project_id: str | None = None,
    dataset_id: str | None = None,
    prompts_config_path: str | None = None,
) -> NexusAppBundle:
    """
    Constructs an isolated instance of the 8-agent Nexus hierarchy (`nexus_optimized` or `nexus_unoptimized`).
    """
    resolved_app_name = app_name or (
        "nexus_optimized" if optimized else "nexus_unoptimized"
    )
    tower, plugin = create_nexus_tower(
        app_name=resolved_app_name,
        auto_export_path=auto_export_path,
        mode=mode,
        sink=sink,
        project_id=project_id,
        dataset_id=dataset_id,
        prompts_config_path=prompts_config_path,
    )
    bind_active_tower(tower)

    def _model_for(agent_name: str) -> str:
        if not optimized:
            return FRONTIER_MODEL_NAME
        if agent_name == "report_drafter":
            return FRONTIER_MODEL_NAME
        return MODEL_NAME

    def _make_llm_agent(
        *,
        name: str,
        description: str,
        instruction: str,
        tools: list[Any] | None = None,
        sub_agents: list[Any] | None = None,
        output_key: str | None = None,
    ) -> LlmAgent:
        m_id = _model_for(name)
        tier = AGENT_REASONING_TIERS[name]
        planner, gen_cfg = resolve_planner_and_config(
            m_id, tier, optimized=optimized
        )
        kwargs: dict[str, Any] = {
            "name": name,
            "model": m_id,
            "description": description,
            "instruction": instruction,
            "tools": list(tools or []),
            "sub_agents": list(sub_agents or []),
        }
        if output_key is not None:
            kwargs["output_key"] = output_key
        if planner is not None:
            kwargs["planner"] = planner
        if gen_cfg is not None:
            kwargs["generate_content_config"] = gen_cfg
        return LlmAgent(**kwargs)

    # 1. AgentTool child specialist (`sandbox_analyst`)
    sandbox_analyst = _make_llm_agent(
        name="sandbox_analyst",
        description="Isolated quantitative ROI & Monte Carlo sensitivity specialist.",
        instruction=SANDBOX_ANALYST_PROMPT,
        tools=[FunctionTool(run_roi_monte_carlo)],
    )
    quant_sandbox_tool = AgentTool(agent=sandbox_analyst, include_plugins=True)

    # 2. Parallel fan-out specialists (`signal_gatherers`)
    market_intel_analyst = _make_llm_agent(
        name="market_intel_analyst",
        description="Parallel market benchmark analyst.",
        instruction=MARKET_INTEL_ANALYST_PROMPT,
        tools=[FunctionTool(fetch_market_benchmarks)],
        output_key="parallel_market_intel",
    )
    metrics_sql_analyst = _make_llm_agent(
        name="metrics_sql_analyst",
        description="Parallel BigQuery telemetry warehouse analyst.",
        instruction=METRICS_SQL_ANALYST_PROMPT,
        tools=[FunctionTool(query_telemetry_warehouse)],
        output_key="parallel_metrics_sql",
    )
    risk_policy_analyst = _make_llm_agent(
        name="risk_policy_analyst",
        description="Parallel security & compliance control specialist.",
        instruction=RISK_POLICY_ANALYST_PROMPT,
        tools=[FunctionTool(evaluate_compliance_controls)],
        output_key="parallel_risk_policy",
    )
    signal_gatherers = ParallelAgent(
        name="signal_gatherers",
        description="Concurrent fan-out gathering market, SQL telemetry, and compliance signals.",
        sub_agents=[
            market_intel_analyst,
            metrics_sql_analyst,
            risk_policy_analyst,
        ],
    )

    # 3. Iterative synthesis & gatekeeper loop (`deliverable_refiner`)
    report_drafter = _make_llm_agent(
        name="report_drafter",
        description="Executive brief synthesis author.",
        instruction=REPORT_DRAFTER_PROMPT,
        tools=[FunctionTool(append_state_entry)],
    )
    adversarial_critic = _make_llm_agent(
        name="adversarial_critic",
        description="4-point rubric gatekeeper with BuiltInPlanner.",
        instruction=ADVERSARIAL_CRITIC_PROMPT,
        tools=[FunctionTool(append_state_entry), FunctionTool(exit_loop)],
    )
    deliverable_refiner = LoopAgent(
        name="deliverable_refiner",
        description="Bounded 2-pass synthesis and adversarial verification loop.",
        sub_agents=[report_drafter, adversarial_critic],
        max_iterations=2,
    )

    # 4. Final artifact packager (`packager_agent`)
    packager_agent = _make_llm_agent(
        name="packager_agent",
        description="Schema-compliant 5-section Markdown report packager.",
        instruction=PACKAGER_AGENT_PROMPT,
        tools=[FunctionTool(save_executive_brief)],
        output_key="final_report_path",
    )

    # 5. Composite Sequential pipeline (`deep_research_pipeline`)
    deep_research_pipeline = SequentialAgent(
        name="deep_research_pipeline",
        description="Sequential pipeline orchestrating parallel signal gathering, loop refinement, and packaging.",
        sub_agents=[signal_gatherers, deliverable_refiner, packager_agent],
    )

    # 6. Root coordinator (`nexus_router`)
    skill_toolset = build_nexus_skill_toolset() if optimized else None
    router_tools: list[Any] = [
        FunctionTool(record_initiative_context),
        quant_sandbox_tool,
        FunctionTool(audit_session_tokenomics),
    ]
    if skill_toolset is not None:
        router_tools.append(skill_toolset)

    router_instruction = (
        NEXUS_ROUTER_OPTIMIZED_PROMPT
        if optimized
        else build_unoptimized_monolithic_router_prompt()
    )
    nexus_router = _make_llm_agent(
        name="nexus_router",
        description="Root Coordinator for the Nexus Enterprise Copilot.",
        instruction=router_instruction,
        tools=router_tools,
        sub_agents=[deep_research_pipeline],
    )

    # Ensure parent pointers are linked across the entire tree for orchestration flow extraction
    for sub in signal_gatherers.sub_agents:
        sub.parent_agent = signal_gatherers
    for sub in deliverable_refiner.sub_agents:
        sub.parent_agent = deliverable_refiner
    for sub in deep_research_pipeline.sub_agents:
        sub.parent_agent = deep_research_pipeline
    deep_research_pipeline.parent_agent = nexus_router

    app = App(
        name=resolved_app_name,
        root_agent=nexus_router,
        plugins=[plugin],
        context_cache_config=ContextCacheConfig(
            min_tokens=1024, ttl_seconds=300
        )
        if optimized
        else None,
        events_compaction_config=EventsCompactionConfig(
            compaction_interval=4, overlap_size=1
        )
        if optimized
        else None,
    )
    plugin.attach_to_agent(nexus_router)
    runner = InMemoryRunner(app=app)

    agents_map = {
        "nexus_router": nexus_router,
        "sandbox_analyst": sandbox_analyst,
        "signal_gatherers": signal_gatherers,
        "market_intel_analyst": market_intel_analyst,
        "metrics_sql_analyst": metrics_sql_analyst,
        "risk_policy_analyst": risk_policy_analyst,
        "deliverable_refiner": deliverable_refiner,
        "report_drafter": report_drafter,
        "adversarial_critic": adversarial_critic,
        "packager_agent": packager_agent,
        "deep_research_pipeline": deep_research_pipeline,
    }
    return NexusAppBundle(
        optimized=optimized,
        app_name=resolved_app_name,
        app=app,
        root_agent=nexus_router,
        agents=agents_map,
        quant_sandbox_tool=quant_sandbox_tool,
        skill_toolset=skill_toolset,
        tower=tower,
        plugin=plugin,
        runner=runner,
    )


@dataclass
class _SimFunctionCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class _SimPart:
    text: str | None = None
    function_call: _SimFunctionCall | None = None


@dataclass
class _SimContent:
    role: str = "model"
    parts: list[_SimPart] = field(default_factory=list)


@dataclass
class _SimCandidate:
    content: _SimContent


@dataclass
class _SimUsageMetadata:
    prompt_token_count: int
    cached_content_token_count: int
    candidates_token_count: int
    thoughts_token_count: int = 0
    tool_use_prompt_token_count: int = 0


@dataclass
class _SimLlmRequest:
    model: str
    contents: list[dict[str, Any]]


@dataclass
class _SimLlmResponse:
    model_version: str
    usage_metadata: _SimUsageMetadata
    candidates: list[_SimCandidate]
    partial: bool = False


@dataclass
class _SimSession:
    id: str
    state: dict[str, Any]


@dataclass
class _SimCallbackContext:
    session: _SimSession
    session_id: str
    invocation_id: str
    agent_name: str
    agent: Any
    user_content: dict[str, Any]


@dataclass
class _SimToolObj:
    name: str
    agent: Any | None = None


class _SimEventActions:
    def __init__(self) -> None:
        self.escalate: bool = False


class _SimToolContext:
    """Lightweight ToolContext for hermetic simulation runs (compatible with both ADK exit_loop and custom tools)."""

    def __init__(
        self,
        *,
        state: dict[str, Any],
        session_id: str,
        invocation_id: str,
        agent_name: str,
        agent: Any,
        function_call_id: str,
    ) -> None:
        self.state = state
        self.session = _SimSession(id=session_id, state=state)
        self.session_id = session_id
        self.invocation_id = invocation_id
        self.agent_name = agent_name
        self.agent = agent
        self.function_call_id = function_call_id
        self.actions = _SimEventActions()


def _compose_five_section_brief(
    state: dict[str, Any], pass_num: int = 1, complete: bool = True
) -> str:
    initiative = (
        state.get("target_initiative")
        or "Enterprise AI FinOps Copilot (Tier-1 Cloud Enterprise)"
    )
    market = (
        state.get("parallel_market_intel")
        or "75%-86% median unit-cost reduction via Prefix Caching and Flash routing."
    )
    warehouse = (
        state.get("parallel_metrics_sql")
        or "Unoptimized p50=$0.16220 vs. Optimized=$0.02272 (81.2% cache hit)."
    )
    quant = (
        state.get("sandbox_quant_model")
        or "Volume=10,000 sessions/day | Projected Annual Savings=$509,102.00/yr."
    )
    controls = (
        state.get("parallel_risk_policy")
        or "Mandatory Controls: [C-01], [C-02], [C-03], [C-04]."
    )

    sections = [
        f"# SECTION 1: EXECUTIVE DECISION BRIEF\n"
        f"- **Initiative:** {initiative} (Draft Pass #{pass_num})\n"
        f"- **Go / No-Go Recommendation:** GO — Architecture achieves 86.0% unit-cost reduction while meeting all latency and governance gates.\n",
        f"# SECTION 2: MARKET & TELEMETRY BENCHMARKS\n"
        f"- **Market Intelligence Summary:** {market}\n"
        f"- **Warehouse Telemetry Baseline:** {warehouse}\n",
        f"# SECTION 3: QUANTITATIVE ROI & UNIT ECONOMICS MODEL\n"
        f"- **Monte Carlo Sensitivity:** {quant}\n",
        f"# SECTION 4: RISK, SECURITY & COMPLIANCE CONTROLS\n"
        f"- **Mandatory Controls:** {controls}\n",
    ]
    if complete:
        sections.append(
            "# SECTION 5: SESSION TOKENOMICS & FINOPS SCORECARD\n"
            "- **Target Production Guardrails:** Max Cost/Turn <= $0.0040 | Min Prefix Cache Hit >= 60.0% | Thinking Budget <= 256 tokens\n"
        )
    return "\n".join(sections)


def run_simulated_nexus_session(
    bundle: NexusAppBundle,
    *,
    session_id: str | None = None,
    max_loop_passes: int = 1,
    output_dir: str = "artifacts/reports",
    export_decorated_trace_path: str | None = None,
) -> dict[str, Any]:
    """
    Executes the canonical multi-turn Nexus trajectory through the real ADK agent objects,
    domain tools, and `ADKTokenomicsPlugin` lifecycle callbacks (`before_model_callback`,
    `after_model_callback`, `before_tool_callback`, `after_tool_callback`, `finalize_session`).

    Args:
        bundle: Constructed `NexusAppBundle` (`nexus_unoptimized` or `nexus_optimized`).
        session_id: Explicit session ID (`unopt_baseline` or `opt_tuned` by default).
        max_loop_passes: `1` for Pass-1 `exit_loop` convergence (Trajectory A), or `2` to test
                         Pass-1 critic rejection -> Pass-2 revision at `max_iterations=2` (Trajectory B).
        output_dir: Directory where `packager_agent` writes the 5-section Markdown executive brief.
        export_decorated_trace_path: Optional file path to export the standalone `@track_tokens`
                                     trace (`session_id='decorated_session'`).
    """
    bind_active_tower(bundle.tower)
    plugin = bundle.plugin
    agents = bundle.agents
    opt = bundle.optimized
    sid = session_id or ("opt_tuned" if opt else "unopt_baseline")
    session_state: dict[str, Any] = {}
    _SimSession(id=sid, state=session_state)
    call_seq = 0

    def _next_fc_id() -> str:
        nonlocal call_seq
        call_seq += 1
        return f"fc_{sid}_{call_seq:03d}"

    def _run_llm_turn(
        *,
        agent_obj: Any,
        invocation_id: str,
        user_query: str,
        fresh_tokens: int,
        cached_tokens: int,
        output_tokens: int,
        thinking_tokens: int,
        response_text: str,
        tool_calls: list[tuple[Any, dict[str, Any], Any]] | None = None,
        override_session_id: str | None = None,
    ) -> None:
        eff_raw_sid = override_session_id or sid
        ctx_session = _SimSession(id=eff_raw_sid, state=session_state)
        user_content = {"role": "user", "parts": [{"text": user_query}]}
        cb_ctx = _SimCallbackContext(
            session=ctx_session,
            session_id=eff_raw_sid,
            invocation_id=invocation_id,
            agent_name=agent_obj.name,
            agent=agent_obj,
            user_content=user_content,
        )
        req = _SimLlmRequest(
            model=str(agent_obj.model), contents=[user_content]
        )
        plugin.before_model_callback(callback_context=cb_ctx, llm_request=req)

        parts: list[_SimPart] = []
        if tool_calls:
            for t_obj, t_args, _ in tool_calls:
                t_name = getattr(t_obj, "name", None) or getattr(
                    t_obj, "__name__", str(t_obj)
                )
                parts.append(
                    _SimPart(
                        function_call=_SimFunctionCall(
                            name=str(t_name), args=dict(t_args)
                        )
                    )
                )
        if response_text:
            parts.append(_SimPart(text=response_text))

        prompt_total = fresh_tokens + cached_tokens
        resp = _SimLlmResponse(
            model_version=str(agent_obj.model),
            usage_metadata=_SimUsageMetadata(
                prompt_token_count=prompt_total,
                cached_content_token_count=cached_tokens,
                candidates_token_count=output_tokens,
                thoughts_token_count=thinking_tokens,
            ),
            candidates=[
                _SimCandidate(content=_SimContent(role="model", parts=parts))
            ],
        )
        plugin.after_model_callback(callback_context=cb_ctx, llm_response=resp)

        if tool_calls:
            for t_obj, t_args, fn_exec in tool_calls:
                t_ctx = _SimToolContext(
                    state=session_state,
                    session_id=eff_raw_sid,
                    invocation_id=invocation_id,
                    agent_name=agent_obj.name,
                    agent=agent_obj,
                    function_call_id=_next_fc_id(),
                )
                plugin.before_tool_callback(
                    tool=t_obj, tool_args=t_args, tool_context=t_ctx
                )
                res = fn_exec(t_ctx) if callable(fn_exec) else None
                plugin.after_tool_callback(
                    tool=t_obj, tool_args=t_args, tool_context=t_ctx, result=res
                )

        if getattr(agent_obj, "output_key", None) and response_text:
            session_state[str(agent_obj.output_key)] = response_text

    # =========================================================================
    # INVOCATION 1: Initiative Intake + (Skill Load in Optimized) + AgentTool ROI
    # =========================================================================
    inv1_id = "inv_o1" if opt else "inv_u1"
    q1 = "Evaluate launching the Enterprise AI FinOps Copilot for Tier-1 Cloud Enterprise customers and model ROI for 10,000 daily sessions."

    router_turn1_tools: list[tuple[Any, dict[str, Any], Any]] = [
        (
            _SimToolObj(name="record_initiative_context"),
            {
                "initiative_name": "Enterprise AI FinOps Copilot",
                "target_segment": "Tier-1 Cloud Enterprise",
            },
            lambda tctx: record_initiative_context(
                "Enterprise AI FinOps Copilot",
                "Tier-1 Cloud Enterprise",
                tool_context=tctx,
            ),
        ),
    ]
    if opt:
        router_turn1_tools.append(
            (
                _SimToolObj(name="load_skill"),
                {"skill_name": "finops-playbooks"},
                lambda _tctx: {
                    "status": "loaded",
                    "skill_name": "finops-playbooks",
                },
            )
        )

    def _invoke_child_sandbox_agent(parent_tctx: ToolContext) -> str:
        # Ephemeral child session ID automatically stitched back to `sid` by ADKTokenomicsPlugin!
        child_sid = f"child_sandbox_{sid}"
        _run_llm_turn(
            agent_obj=agents["sandbox_analyst"],
            invocation_id=f"{inv1_id}_sandbox",
            user_query=q1,
            fresh_tokens=380 if opt else 2200,
            cached_tokens=1200 if opt else 0,
            output_tokens=220 if opt else 240,
            thinking_tokens=0 if opt else 950,
            response_text="Completed Monte Carlo ROI simulation for 10,000 daily sessions.",
            tool_calls=[
                (
                    _SimToolObj(name="run_roi_monte_carlo"),
                    {
                        "daily_sessions": 10000,
                        "baseline_cost_usd": 0.16220,
                        "target_cost_usd": 0.02272,
                    },
                    lambda child_tctx: run_roi_monte_carlo(
                        10000, 0.16220, 0.02272, tool_context=child_tctx
                    ),
                )
            ],
            override_session_id=child_sid,
        )
        return session_state.get("sandbox_quant_model", "")

    router_turn1_tools.append(
        (
            bundle.quant_sandbox_tool,
            {"request": "Model ROI sensitivity for 10,000 daily sessions"},
            _invoke_child_sandbox_agent,
        )
    )

    _run_llm_turn(
        agent_obj=agents["nexus_router"],
        invocation_id=inv1_id,
        user_query=q1,
        fresh_tokens=420 if opt else 6400,
        cached_tokens=1400 if opt else 0,
        output_tokens=160 if opt else 180,
        thinking_tokens=0,
        response_text="Recorded initiative context and executed quantitative ROI simulation.",
        tool_calls=router_turn1_tools,
    )

    # =========================================================================
    # INVOCATION 2: Full Sequential Pipeline (Parallel -> Loop -> Packager)
    # =========================================================================
    inv2_id = "inv_o2" if opt else "inv_u2"
    q2 = "Run the full deep research pipeline and generate the 5-section executive decision brief."

    # Stage 1: ParallelAgent (`signal_gatherers`)
    _run_llm_turn(
        agent_obj=agents["market_intel_analyst"],
        invocation_id=inv2_id,
        user_query=q2,
        fresh_tokens=320 if opt else 1600,
        cached_tokens=1200 if opt else 0,
        output_tokens=280 if opt else 300,
        thinking_tokens=0,
        response_text="78% of untiered multi-agent deployments fail margin gates; Prefix Caching + Flash routing cuts cost by 75%-86%.",
        tool_calls=[
            (
                _SimToolObj(name="fetch_market_benchmarks"),
                {"domain": "enterprise_ai_finops"},
                lambda _tctx: fetch_market_benchmarks("enterprise_ai_finops"),
            )
        ],
    )
    _run_llm_turn(
        agent_obj=agents["metrics_sql_analyst"],
        invocation_id=inv2_id,
        user_query=q2,
        fresh_tokens=320 if opt else 1600,
        cached_tokens=1200 if opt else 0,
        output_tokens=280 if opt else 300,
        thinking_tokens=0,
        response_text="BigQuery v_llm_response baseline: Unoptimized=$0.16220 (0% cache) vs. Optimized=$0.02272 (81.2% cache).",
        tool_calls=[
            (
                _SimToolObj(name="query_telemetry_warehouse"),
                {"workload_tier": "tier1_enterprise"},
                lambda _tctx: query_telemetry_warehouse("tier1_enterprise"),
            )
        ],
    )
    _run_llm_turn(
        agent_obj=agents["risk_policy_analyst"],
        invocation_id=inv2_id,
        user_query=q2,
        fresh_tokens=310 if opt else 1600,
        cached_tokens=1200 if opt else 0,
        output_tokens=260 if opt else 300,
        thinking_tokens=0,
        response_text="Verified mandatory controls [C-01] XML delimiters, [C-02] basename path check, [C-03] loop/call caps, [C-04] BQ partitioning.",
        tool_calls=[
            (
                _SimToolObj(name="evaluate_compliance_controls"),
                {"data_classification": "regulated_emea_gdpr"},
                lambda _tctx: evaluate_compliance_controls(
                    "regulated_emea_gdpr"
                ),
            )
        ],
    )

    # Stage 2: LoopAgent (`deliverable_refiner`, max_iterations=2)
    max_iters = int(
        getattr(agents["deliverable_refiner"], "max_iterations", 2) or 2
    )
    target_passes = min(max_iters, max(1, int(max_loop_passes)))
    for pass_idx in range(1, target_passes + 1):
        is_final_pass = pass_idx == target_passes
        draft_md = _compose_five_section_brief(
            session_state,
            pass_num=pass_idx,
            complete=(pass_idx > 1 or target_passes == 1),
        )
        _run_llm_turn(
            agent_obj=agents["report_drafter"],
            invocation_id=inv2_id,
            user_query=q2,
            fresh_tokens=780 if opt else 3600,
            cached_tokens=2800 if opt else 0,
            output_tokens=920 if opt else 950,
            thinking_tokens=180 if opt else 1400,
            response_text=f"Drafted Executive Decision Brief (Pass #{pass_idx}).",
            tool_calls=[
                (
                    _SimToolObj(name="append_state_entry"),
                    {"field": "deliverable_drafts", "content": draft_md},
                    lambda tctx, d=draft_md: append_state_entry(
                        "deliverable_drafts", d, tool_context=tctx
                    ),
                )
            ],
        )

        critic_tools: list[tuple[Any, dict[str, Any], Any]]
        if is_final_pass and target_passes == 1:
            critic_tools = [
                (
                    _SimToolObj(name="exit_loop"),
                    {},
                    exit_loop,
                )
            ]
            critic_resp = "All 4 rubric criteria verified on Pass #1. Exiting refinement loop."
        elif not is_final_pass:
            fb_text = "Pass #1 missing SECTION 5: SESSION TOKENOMICS & FINOPS SCORECARD. Add explicit FinOps thresholds."
            critic_tools = [
                (
                    _SimToolObj(name="append_state_entry"),
                    {"field": "critic_feedback", "content": fb_text},
                    lambda tctx, f=fb_text: append_state_entry(
                        "critic_feedback", f, tool_context=tctx
                    ),
                )
            ]
            critic_resp = fb_text
        else:
            # Trajectory B: Pass 2 at max_iterations=2 hard cap
            critic_tools = []
            critic_resp = "Pass #2 verified at max_iterations=2 ceiling."

        _run_llm_turn(
            agent_obj=agents["adversarial_critic"],
            invocation_id=inv2_id,
            user_query=q2,
            fresh_tokens=450 if opt else 3800,
            cached_tokens=2600 if opt else 0,
            output_tokens=190 if opt else 220,
            thinking_tokens=140 if opt else 1600,
            response_text=critic_resp,
            tool_calls=critic_tools,
        )

    # Stage 3: Packager (`packager_agent` — packages ONLY latest entry `deliverable_drafts[-1]`)
    latest_draft = (session_state.get("deliverable_drafts") or [""])[-1]
    report_filename = f"{sid}_executive_brief.md"
    saved_info: dict[str, str] = {}

    def _exec_save(_tctx: ToolContext) -> dict[str, str]:
        res = save_executive_brief(
            filename=report_filename,
            markdown_content=latest_draft,
            output_dir=output_dir,
        )
        saved_info.update(res)
        return res

    _run_llm_turn(
        agent_obj=agents["packager_agent"],
        invocation_id=inv2_id,
        user_query=q2,
        fresh_tokens=320 if opt else 3900,
        cached_tokens=2600 if opt else 0,
        output_tokens=280 if opt else 320,
        thinking_tokens=0,
        response_text=f"Saved validated 5-section executive brief to {output_dir}/{report_filename}",
        tool_calls=[
            (
                _SimToolObj(name="save_executive_brief"),
                {"filename": report_filename, "output_dir": output_dir},
                _exec_save,
            )
        ],
    )

    # =========================================================================
    # INVOCATION 3 (& 4 in Unoptimized): Multi-Turn Follow-Up + Live FinOps Audit
    # =========================================================================
    if not opt:
        # Unoptimized runs 2 separate uncompacted follow-up turns (+700 and +550 fresh token growth)
        q3 = "Add EMEA GDPR data residency notes to the rollout plan."
        _run_llm_turn(
            agent_obj=agents["nexus_router"],
            invocation_id="inv_u3",
            user_query=q3,
            fresh_tokens=7100,
            cached_tokens=0,
            output_tokens=210,
            thinking_tokens=0,
            response_text="Updated rollout notes with EMEA GDPR residency requirements.",
        )

        q4 = "Audit the token economics of this session and summarize FinOps recommendations."
        _run_llm_turn(
            agent_obj=agents["nexus_router"],
            invocation_id="inv_u4",
            user_query=q4,
            fresh_tokens=7650,
            cached_tokens=0,
            output_tokens=260,
            thinking_tokens=1100,
            response_text="Completed session FinOps audit: $0.16220 across 10 turns (0.0% cache hit).",
            tool_calls=[
                (
                    _SimToolObj(name="audit_session_tokenomics"),
                    {"session_title": "Nexus Unoptimized Baseline"},
                    lambda tctx: audit_session_tokenomics(
                        "Nexus Unoptimized Baseline", tool_context=tctx
                    ),
                )
            ],
        )
    else:
        # Optimized runs a single compacted follow-up + live FinOps self-audit turn (3 user invocations total)
        q3_opt = "Confirm EMEA GDPR compliance controls and run a live FinOps tokenomics audit on this session."
        _run_llm_turn(
            agent_obj=agents["nexus_router"],
            invocation_id="inv_o3",
            user_query=q3_opt,
            fresh_tokens=380,
            cached_tokens=1650,
            output_tokens=240,
            thinking_tokens=0,
            response_text="Verified EMEA controls and completed live FinOps audit: $0.02272 across 9 turns (81.2% cache hit).",
            tool_calls=[
                (
                    _SimToolObj(name="audit_session_tokenomics"),
                    {"session_title": "Nexus Optimized Session"},
                    lambda tctx: audit_session_tokenomics(
                        "Nexus Optimized Session", tool_context=tctx
                    ),
                )
            ],
        )

    archived_trace_path = plugin.finalize_session(session_id=sid)
    if export_decorated_trace_path:
        bundle.tower.tracker.export_traces(
            export_decorated_trace_path, session_id="decorated_session"
        )

    session_turns = [
        t
        for t in bundle.tower.tracker.turns_history
        if t.get("session_id") == sid
    ]
    return {
        "session_id": sid,
        "trace_path": archived_trace_path,
        "report_path": saved_info.get("path"),
        "state": session_state,
        "summary": bundle.tower.tracker._summarize_turns(session_turns),
        "turns": session_turns,
    }
