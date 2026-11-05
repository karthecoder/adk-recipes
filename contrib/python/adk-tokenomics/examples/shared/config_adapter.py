"""
Nexus Showcase — Cross-Model Capability Adapter, ADK Class Bridge & TokenControlTower Factory.
Works with both installed `google-adk >= 2.9.2` / `google-genai >= 2.25.0` and zero-dependency stdlib test environments.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from adk_tokenomics_plugin import (
    ADKTokenomicsPlugin,
    OptimizationRulesConfig,
    TokenControlTower,
)

MODEL_NAME: str = os.environ.get(
    "TOKENOMICS_DEFAULT_MODEL",
    "publishers/google/models/gemini-3.8-flash",
)
FRONTIER_MODEL_NAME: str = os.environ.get(
    "NEXUS_FRONTIER_MODEL",
    "publishers/google/models/gemini-4-argon",
)
CUSTOM_POLICY_MODEL_ID: str = "custom/nexus-policy-guard-v1"

AGENT_REASONING_TIERS: dict[str, str] = {
    "nexus_router": "minimal",
    "sandbox_analyst": "low",
    "market_intel_analyst": "low",
    "metrics_sql_analyst": "low",
    "risk_policy_analyst": "low",
    "report_drafter": "medium",
    "adversarial_critic": "low",
    "packager_agent": "minimal",
}

try:
    from google.adk.agents import (
        Agent,
        LlmAgent,
        LoopAgent,
        ParallelAgent,
        SequentialAgent,
    )
    from google.adk.apps import App
    from google.adk.apps.app import ContextCacheConfig, EventsCompactionConfig
    from google.adk.planners import BuiltInPlanner
    from google.adk.runners import InMemoryRunner, RunConfig
    from google.adk.skills import Frontmatter, Skill, load_skill_from_dir
    from google.adk.tools import FunctionTool, ToolContext, exit_loop
    from google.adk.tools.agent_tool import AgentTool
    from google.adk.tools.skill_toolset import SkillToolset
    from google.genai import types as genai_types

    HAS_GOOGLE_ADK = True
except Exception:
    HAS_GOOGLE_ADK = False

    class _ThinkingLevelEnum(StrEnum):
        THINKING_LEVEL_UNSPECIFIED = "THINKING_LEVEL_UNSPECIFIED"
        MINIMAL = "MINIMAL"
        LOW = "LOW"
        MEDIUM = "MEDIUM"
        HIGH = "HIGH"

    @dataclass
    class _ThinkingConfig:
        include_thoughts: bool | None = None
        thinking_budget: int | None = None
        thinking_level: Any | None = None

    @dataclass
    class _HttpRetryOptions:
        attempts: int = 3
        initial_delay: float = 1.0
        max_delay: float = 8.0
        exp_base: float = 2.0

    @dataclass
    class _GenerateContentConfig:
        temperature: float | None = None
        thinking_config: _ThinkingConfig | None = None
        http_options: Any | None = None
        max_output_tokens: int | None = None

    class genai_types:  # type: ignore[no-redef]
        ThinkingLevel = _ThinkingLevelEnum
        ThinkingConfig = _ThinkingConfig
        GenerateContentConfig = _GenerateContentConfig
        HttpRetryOptions = _HttpRetryOptions

    class BuiltInPlanner:  # type: ignore[no-redef]
        def __init__(self, *, thinking_config: Any):
            self.thinking_config = thinking_config

    @dataclass
    class ContextCacheConfig:  # type: ignore[no-redef]
        min_tokens: int = 1024
        ttl_seconds: int = 300
        cache_intervals: int = 10

    @dataclass
    class EventsCompactionConfig:  # type: ignore[no-redef]
        compaction_interval: int = 4
        overlap_size: int = 1

    @dataclass
    class Frontmatter:  # type: ignore[no-redef]
        name: str
        description: str

    @dataclass
    class Skill:  # type: ignore[no-redef]
        frontmatter: Frontmatter
        instructions: str
        resources: dict[str, Any] = field(default_factory=dict)

    def load_skill_from_dir(skill_dir: str | Path) -> Skill:  # type: ignore[no-redef]
        p = Path(skill_dir)
        skill_md = p / "SKILL.md"
        text = (
            skill_md.read_text(encoding="utf-8") if skill_md.is_file() else ""
        )
        name = p.name
        desc = f"Domain skill module {name}"
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
                text = parts[2].strip()
        return Skill(
            frontmatter=Frontmatter(name=name, description=desc),
            instructions=text,
        )

    class SkillToolset:  # type: ignore[no-redef]
        def __init__(self, skills: list[Skill] | None = None, **kwargs: Any):
            self.skills = list(skills or [])
            self.kwargs = kwargs

    class FunctionTool:  # type: ignore[no-redef]
        def __init__(
            self,
            func: Callable[..., Any],
            *,
            require_confirmation: bool = False,
        ):
            self.func = func
            self.name = getattr(func, "__name__", "tool")
            self.require_confirmation = require_confirmation

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self.func(*args, **kwargs)

    class ToolContext:  # type: ignore[no-redef]
        def __init__(
            self,
            state: dict[str, Any] | None = None,
            session_id: str = "default_session",
            invocation_id: str | None = None,
            agent_name: str | None = None,
            agent: Any | None = None,
        ):
            self.state: dict[str, Any] = state if state is not None else {}
            self.session_id = session_id
            self.invocation_id = invocation_id
            self.agent_name = agent_name
            self.agent = agent
            self.actions = type("EventActions", (), {"escalate": False})()

    def exit_loop(tool_context: ToolContext) -> None:  # type: ignore[no-redef]
        if (
            hasattr(tool_context, "actions")
            and tool_context.actions is not None
        ):
            tool_context.actions.escalate = True
        if hasattr(tool_context, "state") and isinstance(
            tool_context.state, dict
        ):
            tool_context.state["_loop_exited"] = True

    class AgentTool:  # type: ignore[no-redef]
        def __init__(
            self,
            agent: Any,
            skip_summarization: bool = False,
            *,
            include_plugins: bool = True,
            propagate_grounding_metadata: bool = False,
        ):
            self.agent = agent
            self.name = getattr(agent, "name", "agent_tool")
            self.skip_summarization = skip_summarization
            self.include_plugins = include_plugins
            self.propagate_grounding_metadata = propagate_grounding_metadata

    class _BaseShimAgent:
        def __init__(
            self,
            *,
            name: str,
            description: str = "",
            sub_agents: list[Any] | None = None,
            before_agent_callback: Any | None = None,
            after_agent_callback: Any | None = None,
            **kwargs: Any,
        ):
            self.name = name
            self.description = description
            self.parent_agent: Any | None = None
            self.sub_agents: list[Any] = list(sub_agents or [])
            for child in self.sub_agents:
                if hasattr(child, "parent_agent"):
                    child.parent_agent = self
            self.before_agent_callback = before_agent_callback
            self.after_agent_callback = after_agent_callback
            for k, v in kwargs.items():
                setattr(self, k, v)

    class LlmAgent(_BaseShimAgent):  # type: ignore[no-redef]
        def __init__(
            self,
            *,
            name: str,
            model: Any = MODEL_NAME,
            description: str = "",
            instruction: str = "",
            tools: list[Any] | None = None,
            sub_agents: list[Any] | None = None,
            output_key: str | None = None,
            planner: Any | None = None,
            generate_content_config: Any | None = None,
            before_model_callback: Any | None = None,
            after_model_callback: Any | None = None,
            before_tool_callback: Any | None = None,
            after_tool_callback: Any | None = None,
            **kwargs: Any,
        ):
            super().__init__(
                name=name,
                description=description,
                sub_agents=sub_agents,
                **kwargs,
            )
            self.model = model
            self.instruction = instruction
            self.tools: list[Any] = list(tools or [])
            self.output_key = output_key
            self.planner = planner
            self.generate_content_config = generate_content_config
            self.before_model_callback = before_model_callback
            self.after_model_callback = after_model_callback
            self.before_tool_callback = before_tool_callback
            self.after_tool_callback = after_tool_callback

    Agent = LlmAgent  # type: ignore[no-redef,misc]

    class SequentialAgent(_BaseShimAgent):  # type: ignore[no-redef]
        pass

    class ParallelAgent(_BaseShimAgent):  # type: ignore[no-redef]
        pass

    class LoopAgent(_BaseShimAgent):  # type: ignore[no-redef]
        def __init__(
            self,
            *,
            name: str,
            sub_agents: list[Any] | None = None,
            max_iterations: int = 2,
            **kwargs: Any,
        ):
            super().__init__(name=name, sub_agents=sub_agents, **kwargs)
            self.max_iterations = max_iterations

    class App:  # type: ignore[no-redef]
        def __init__(
            self,
            *,
            name: str,
            root_agent: Any,
            plugins: list[Any] | None = None,
            context_cache_config: ContextCacheConfig | None = None,
            events_compaction_config: EventsCompactionConfig | None = None,
            **kwargs: Any,
        ):
            self.name = name
            self.root_agent = root_agent
            self.plugins = list(plugins or [])
            self.context_cache_config = context_cache_config
            self.events_compaction_config = events_compaction_config
            for p in self.plugins:
                if hasattr(p, "attach_to_agent"):
                    p.attach_to_agent(self.root_agent)

    @dataclass
    class RunConfig:  # type: ignore[no-redef]
        max_llm_calls: int = 25

    class InMemoryRunner:  # type: ignore[no-redef]
        def __init__(
            self,
            agent: Any | None = None,
            *,
            app_name: str | None = None,
            plugins: list[Any] | None = None,
            app: App | None = None,
            **kwargs: Any,
        ):
            self.app = app
            self.agent = app.root_agent if app is not None else agent
            self.app_name = (
                app.name if app is not None else (app_name or "nexus_app")
            )
            self.plugins = list(
                app.plugins if app is not None else (plugins or [])
            )
            for p in self.plugins:
                if hasattr(p, "attach_to_agent") and self.agent is not None:
                    p.attach_to_agent(self.agent)


GEMINI3_LEVELS: dict[str, Any] = {
    "minimal": genai_types.ThinkingLevel.MINIMAL,
    "low": genai_types.ThinkingLevel.LOW,
    "medium": genai_types.ThinkingLevel.MEDIUM,
    "high": genai_types.ThinkingLevel.HIGH,
}

GEMINI4_LEVELS: dict[str, Any] = {
    "minimal": genai_types.ThinkingLevel.LOW,  # gemini-4-argon supports low/medium/high
    "low": genai_types.ThinkingLevel.LOW,
    "medium": genai_types.ThinkingLevel.MEDIUM,
    "high": genai_types.ThinkingLevel.HIGH,
}

LEGACY_25_BUDGETS: dict[str, int] = {
    "minimal": 0,
    "low": 256,
    "medium": 1024,
    "high": 4096,
}


def resolve_planner_and_config(
    model_name: str,
    tier: str,
    *,
    optimized: bool = True,
) -> tuple[BuiltInPlanner | None, genai_types.GenerateContentConfig | None]:
    """
    Resolves (BuiltInPlanner, GenerateContentConfig) for any ADK sub-agent.
    Assigns `thinking_config` exclusively via `BuiltInPlanner` so it never conflicts with
    `GenerateContentConfig`, and clamps `minimal` -> `ThinkingLevel.LOW` on `gemini-4*` models.
    """
    effective_tier = tier.strip().lower() if optimized else "high"
    if effective_tier not in GEMINI3_LEVELS:
        raise ValueError(
            f"Unknown reasoning tier {tier!r}. Expected one of {sorted(GEMINI3_LEVELS)}."
        )

    clean_model = str(model_name or "").split("/")[-1].strip().lower()
    if clean_model.startswith("gemini-3"):
        t_cfg = genai_types.ThinkingConfig(
            include_thoughts=effective_tier != "minimal",
            thinking_level=GEMINI3_LEVELS[effective_tier],
        )
        return BuiltInPlanner(
            thinking_config=t_cfg
        ), genai_types.GenerateContentConfig(temperature=1.0)

    if clean_model.startswith("gemini-4"):
        t_cfg = genai_types.ThinkingConfig(
            include_thoughts=True,
            thinking_level=GEMINI4_LEVELS[effective_tier],
        )
        return BuiltInPlanner(
            thinking_config=t_cfg
        ), genai_types.GenerateContentConfig(temperature=1.0)

    if clean_model.startswith("gemini-2.5"):
        budget = LEGACY_25_BUDGETS[effective_tier]
        t_cfg = genai_types.ThinkingConfig(
            include_thoughts=budget > 0,
            thinking_budget=budget,
        )
        temp = (
            0.2
            if effective_tier == "minimal"
            else (0.7 if effective_tier == "low" else 0.9)
        )
        return BuiltInPlanner(
            thinking_config=t_cfg
        ), genai_types.GenerateContentConfig(temperature=temp)

    return None, None


def flag_high_cost_session(ctx: dict[str, Any]) -> str | None:
    """Custom FinOps SLA rule callback triggered when accumulated session cost exceeds $0.05."""
    total_cost = float(ctx.get("total_cost", 0.0))
    if total_cost > 0.05:
        return (
            f"🚨 [Enterprise FinOps SLA Breach]: Session spend (${total_cost:.5f}) "
            f"exceeded the $0.05000 per-session budget ceiling."
        )
    return None


def create_nexus_tower(
    *,
    app_name: str,
    auto_export_path: str | None = None,
    mode: str = "dev",
    sink: str = "memory",
    project_id: str | None = None,
    dataset_id: str | None = None,
    prompts_config_path: str | None = None,
) -> tuple[TokenControlTower, ADKTokenomicsPlugin]:
    """
    Creates a pre-configured TokenControlTower and ADKTokenomicsPlugin with:
      1. Custom model registration (`custom/nexus-policy-guard-v1` under `provider='custom'`).
      2. Custom FinOps SLA callback (`flag_high_cost_session`).
      3. Optional `--prompts-file` (`finops_policy.json`) loading.
    """
    default_policy = Path(__file__).resolve().parent / "finops_policy.json"
    resolved_prompts_cfg = prompts_config_path or (
        str(default_policy) if default_policy.is_file() else None
    )

    tower = TokenControlTower(
        mode=mode,
        sink=sink,
        project_id=project_id,
        dataset_id=dataset_id,
        default_model=MODEL_NAME,
        prompts_config_path=resolved_prompts_cfg,
        optimization_rules=OptimizationRulesConfig(),
    )
    tower.register_model(
        model_id=CUSTOM_POLICY_MODEL_ID,
        input_per_million=0.20,
        cached_per_million=0.05,
        output_per_million=0.80,
        provider="custom",
        name="Nexus Fine-Tuned Policy Guard v1",
    )
    tower.add_recommendation_rule(flag_high_cost_session)

    plugin = tower.create_adk_plugin(
        app_name=app_name,
        auto_export_path=auto_export_path,
    )
    return tower, plugin
