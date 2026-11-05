# ruff: noqa: S110
"""
Nexus Showcase — Hardened Domain Tools, SkillToolset Loader, @track_tokens Helper & Live FinOps Auditor.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from adk_tokenomics_plugin import TokenControlTower, track_tokens
from examples.shared.config_adapter import (
    MODEL_NAME,
    Frontmatter,
    Skill,
    SkillToolset,
    ToolContext,
    load_skill_from_dir,
)

ALLOWED_STATE_FIELDS = frozenset({"deliverable_drafts", "critic_feedback"})
_ACTIVE_TOWER: TokenControlTower | None = None


def bind_active_tower(tower: TokenControlTower | None) -> None:
    """Binds the active TokenControlTower so `audit_session_tokenomics` and `@track_tokens` report into it."""
    global _ACTIVE_TOWER
    _ACTIVE_TOWER = tower


def get_active_tower() -> TokenControlTower | None:
    """Returns the currently bound TokenControlTower instance, if any."""
    return _ACTIVE_TOWER


def record_initiative_context(
    initiative_name: str,
    target_segment: str,
    tool_context: ToolContext | None = None,
) -> dict[str, str]:
    """Records the active initiative name and target customer segment into `Session.state['target_initiative']`."""
    clean_name = (
        str(initiative_name or "").strip() or "Enterprise AI Copilot Launch"
    )
    clean_segment = (
        str(target_segment or "").strip() or "Tier-1 Cloud Enterprise"
    )
    combined = f"{clean_name} ({clean_segment})"
    if (
        tool_context is not None
        and hasattr(tool_context, "state")
        and isinstance(tool_context.state, dict)
    ):
        tool_context.state["target_initiative"] = combined
    return {
        "status": "recorded",
        "target_initiative": combined,
    }


def append_state_entry(
    field: str,
    content: str,
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """
    Appends an entry to an allowlisted list key in `Session.state` using top-level assignment
    (`state[field] = existing + [content]`) so ADK records `state_delta` cleanly.
    """
    clean_field = str(field or "").strip()
    if clean_field not in ALLOWED_STATE_FIELDS:
        return {
            "status": "error",
            "message": f"DISALLOWED_FIELD: {clean_field!r}. Allowed fields: {sorted(ALLOWED_STATE_FIELDS)}",
        }
    text = str(content or "").strip()
    if (
        tool_context is not None
        and hasattr(tool_context, "state")
        and isinstance(tool_context.state, dict)
    ):
        existing = list(tool_context.state.get(clean_field) or [])
        updated = [*existing, text]
        tool_context.state[clean_field] = updated
        version = len(updated)
    else:
        version = 1
    return {
        "status": "appended",
        "field": clean_field,
        "version": version,
    }


def _raw_forecast_unit_economics(
    daily_sessions: int,
    baseline_cost_usd: float,
    target_cost_usd: float,
) -> tuple[str, dict[str, int]]:
    safe_sessions = max(1000, int(daily_sessions or 1000))
    base_c = max(0.0, float(baseline_cost_usd))
    targ_c = max(0.0, float(target_cost_usd))
    daily_savings = max(0.0, (base_c - targ_c) * safe_sessions)
    annual_savings = daily_savings * 365.0
    reduction_pct = ((base_c - targ_c) / base_c * 100.0) if base_c > 0 else 0.0
    summary = (
        f"Volume={safe_sessions:,} sessions/day | Unoptimized=${base_c:.5f}/session | "
        f"Optimized=${targ_c:.5f}/session | Reduction={reduction_pct:.1f}% | "
        f"Projected Annual Savings=${annual_savings:,.2f}/yr"
    )
    usage = {
        "prompt_token_count": 600,
        "cached_content_token_count": 450,
        "candidates_token_count": 110,
        "thoughts_token_count": 0,
    }
    return summary, usage


def forecast_unit_economics(
    daily_sessions: int = 10000,
    baseline_cost_usd: float = 0.16220,
    target_cost_usd: float = 0.02272,
) -> tuple[str, dict[str, int]]:
    """
    Standalone helper wrapped dynamically with `@track_tokens` on the active tower's tracker
    (records under `session_id='decorated_session'`).
    """
    active_tracker = (
        _ACTIVE_TOWER.tracker if _ACTIVE_TOWER is not None else None
    )
    decorated = track_tokens(
        app_name="quant_forecaster_fn",
        model_name=MODEL_NAME,
        tracker=active_tracker,
    )(_raw_forecast_unit_economics)
    return decorated(daily_sessions, baseline_cost_usd, target_cost_usd)


def run_roi_monte_carlo(
    daily_sessions: int = 10000,
    baseline_cost_usd: float = 0.16220,
    target_cost_usd: float = 0.02272,
    tool_context: ToolContext | None = None,
) -> str:
    """Runs quantitative ROI sensitivity via `@track_tokens` helper and stores result in `sandbox_quant_model`."""
    summary_text, _ = forecast_unit_economics(
        daily_sessions=daily_sessions,
        baseline_cost_usd=baseline_cost_usd,
        target_cost_usd=target_cost_usd,
    )
    payload = f"<quant_extract>{summary_text}</quant_extract>"
    if (
        tool_context is not None
        and hasattr(tool_context, "state")
        and isinstance(tool_context.state, dict)
    ):
        tool_context.state["sandbox_quant_model"] = summary_text
    return payload


_MARKET_FIXTURES: dict[str, str] = {
    "default": (
        "Enterprise AI Copilot Adoption Benchmark (2026): 78% of multi-agent deployments fail margin gates "
        "due to uncached static prompts (>5,000 tokens/turn) and untiered frontier reasoning models. "
        "Teams enabling Prefix Context Caching and Flash sub-agent routing reduce median unit cost by 75%-86%."
    ),
}

_WAREHOUSE_FIXTURES: dict[str, str] = {
    "default": (
        "BigQuery `v_llm_response` 30-Day Baseline: Unoptimized p50 session cost = $0.16220 across 10 turns "
        "(0.0% cache hit, 5,050 thinking tokens, 39,450 fresh input tokens). Optimized target = $0.02272 across "
        "9 turns (81.2% cache hit, 320 thinking tokens, 3,680 fresh input tokens)."
    ),
}

_COMPLIANCE_FIXTURES: dict[str, str] = {
    "default": (
        "Mandatory Controls: [C-01] Wrap external retrieval data in <external_extract> XML tags; "
        "[C-02] Sanitize report filenames with os.path.basename() and Path.is_relative_to(); "
        "[C-03] Enforce LoopAgent(max_iterations=2) and RunConfig(max_llm_calls=25); "
        "[C-04] Partition BigQuery telemetry by DATE(timestamp) with PII redaction."
    ),
}


def fetch_market_benchmarks(domain: str = "enterprise_ai_finops") -> str:
    """Returns deterministic market benchmark data wrapped in `<external_extract>` tags."""
    key = str(domain or "").strip().lower()
    body = _MARKET_FIXTURES.get(key)
    if body is None:
        body = f"{_MARKET_FIXTURES['default']} (NOTE: Fallback benchmark applied for '{key or 'default'}'.)"
    return f"<external_extract>{body}</external_extract>"


def query_telemetry_warehouse(workload_tier: str = "tier1_enterprise") -> str:
    """Returns deterministic BigQuery telemetry benchmark metrics wrapped in `<external_extract>` tags."""
    key = str(workload_tier or "").strip().lower()
    body = _WAREHOUSE_FIXTURES.get(key)
    if body is None:
        body = f"{_WAREHOUSE_FIXTURES['default']} (NOTE: Fallback benchmark applied for '{key or 'default'}'.)"
    return f"<external_extract>{body}</external_extract>"


def evaluate_compliance_controls(
    data_classification: str = "regulated_emea_gdpr",
) -> str:
    """Returns deterministic security and compliance controls wrapped in `<external_extract>` tags."""
    key = str(data_classification or "").strip().lower()
    body = _COMPLIANCE_FIXTURES.get(key)
    if body is None:
        body = f"{_COMPLIANCE_FIXTURES['default']} (NOTE: Fallback benchmark applied for '{key or 'default'}'.)"
    return f"<external_extract>{body}</external_extract>"


def audit_session_tokenomics(
    session_title: str = "Nexus Live Session",
    tool_context: ToolContext | None = None,
) -> str:
    """
    Calls `tower.get_finops_advisor_prompt()` and `tower.get_summary()` on the active `TokenControlTower`
    so the agent can inspect its own live session token economics in-chat.
    """
    if _ACTIVE_TOWER is None:
        msg = "0 turns recorded yet (no active TokenControlTower bound)."
        if (
            tool_context is not None
            and hasattr(tool_context, "state")
            and isinstance(tool_context.state, dict)
        ):
            tool_context.state["finops_audit_summary"] = msg
        return msg

    summary = _ACTIVE_TOWER.get_summary()
    if int(summary.get("total_turns", 0)) == 0:
        msg = "0 turns recorded yet in active TokenControlTower."
        if (
            tool_context is not None
            and hasattr(tool_context, "state")
            and isinstance(tool_context.state, dict)
        ):
            tool_context.state["finops_audit_summary"] = msg
        return msg

    advisor_payload = _ACTIVE_TOWER.get_finops_advisor_prompt(
        title=session_title
    )
    scorecard = (
        f"Session='{session_title}' | Turns={summary['total_turns']} | "
        f"Total Cost=${summary['total_cost']:.5f} | Cache Hit={summary['cache_read_ratio_pct']:.1f}% | "
        f"Fresh={summary['input_tokens']:,} | Cached={summary['cached_tokens']:,} | "
        f"Out={summary['output_tokens']:,} | Think={summary['thinking_tokens']:,}\n"
        f"{advisor_payload['user_prompt']}"
    )
    if (
        tool_context is not None
        and hasattr(tool_context, "state")
        and isinstance(tool_context.state, dict)
    ):
        tool_context.state["finops_audit_summary"] = scorecard
    return scorecard


def save_executive_brief(
    filename: str,
    markdown_content: str,
    output_dir: str = "artifacts/reports",
) -> dict[str, str]:
    """
    Persists the validated 5-section executive brief to `output_dir` after strict path-traversal
    and character allowlist sanitization. Does not mutate `ToolContext.state`.
    """
    raw_name = str(filename or "").strip()
    if (
        not raw_name
        or ".." in Path(raw_name).parts
        or raw_name.startswith(("/", "\\"))
    ):
        raise ValueError(f"Invalid filename traversal attempt: {filename!r}")

    base_name = os.path.basename(raw_name)
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", base_name).strip("._")[:80]
    if not sanitized:
        raise ValueError(f"Invalid filename after sanitization: {filename!r}")
    if not sanitized.endswith(".md"):
        sanitized = f"{sanitized[:77]}.md"

    base_dir = Path(output_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    target_path = (base_dir / sanitized).resolve()
    if not target_path.is_relative_to(base_dir):
        raise ValueError(
            f"Invalid filename traversal attempt outside {base_dir}: {filename!r}"
        )

    target_path.write_text(str(markdown_content or ""), encoding="utf-8")
    return {
        "status": "saved",
        "path": str(target_path),
    }


def build_nexus_skill_toolset(
    skills_dir: Path | str | None = None,
) -> SkillToolset:
    """Loads the 3 modular `SKILL.md` directories into an ADK `SkillToolset` with in-memory fallback."""
    root = (
        Path(skills_dir)
        if skills_dir is not None
        else (Path(__file__).resolve().parent / "skills")
    )
    loaded_skills = []
    default_specs = (
        (
            "finops-playbooks",
            "Enterprise AI unit economics, context caching, model tiering, and thinking budgets.",
        ),
        (
            "sql-telemetry",
            "BigQuery fleet telemetry schema (adk_agent_events and v_llm_response) and 4-bucket math.",
        ),
        (
            "compliance-controls",
            "Enterprise data governance, XML prompt-injection containment, and path security.",
        ),
    )
    for name, fallback_desc in default_specs:
        cand = root / name
        try:
            if cand.is_dir() and (cand / "SKILL.md").is_file():
                loaded_skills.append(load_skill_from_dir(cand))
                continue
        except Exception:
            pass
        loaded_skills.append(
            Skill(
                frontmatter=Frontmatter(name=name, description=fallback_desc),
                instructions=f"# {name}\n{fallback_desc}",
            )
        )
    return SkillToolset(skills=loaded_skills)
