# ruff: noqa: E402
"""
Nexus FinOps-Optimized ADK Agent (`nexus_optimized`).
Applies all 5 ADK FinOps optimizations recommended by `adk-tokenomics profile`:
  1. Sub-agent model tiering (`gemini-3.8-flash` + `custom/nexus-policy-guard-v1`; `gemini-4-argon` only on `report_drafter`).
  2. Prefix Context Caching (`ContextCacheConfig(min_tokens=1024, ttl_seconds=300)`).
  3. Multi-Turn Event Compaction (`EventsCompactionConfig(compaction_interval=4, overlap_size=1)`).
  4. Progressive Skill Disclosure (`SkillToolset` loading `SKILL.md` modules via `load_skill`).
  5. Right-sized `BuiltInPlanner` reasoning tiers (`MINIMAL` / `LOW` / `MEDIUM`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from examples.shared.config_adapter import MODEL_NAME as _DEFAULT_MODEL_NAME
from examples.shared.mock_llm import build_nexus_agents

MODEL_NAME: str = _DEFAULT_MODEL_NAME
_DEFAULT_EXPORT = os.environ.get(
    "TOKENOMICS_AUTO_EXPORT_PATH",
    str(
        _REPO_ROOT
        / "examples"
        / "artifacts"
        / "traces"
        / "live_opt_session.json"
    ),
)

bundle = build_nexus_agents(
    optimized=True,
    app_name="nexus_optimized",
    auto_export_path=_DEFAULT_EXPORT,
)

root_agent = bundle.root_agent
app = bundle.app
tower = bundle.tower
tokenomics_plugin = bundle.plugin
