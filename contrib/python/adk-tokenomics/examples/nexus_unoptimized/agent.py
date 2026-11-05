# ruff: noqa: E402
"""
Nexus Unoptimized Baseline ADK Agent (`nexus_unoptimized`).
Intentionally demonstrates the 5 classic LLM FinOps anti-patterns:
  1. Frontier model (`publishers/google/models/gemini-4-argon`) on all 8 sub-agents (`model_tiering`).
  2. No `ContextCacheConfig` on `App` (`context_caching`).
  3. No `EventsCompactionConfig` on `App` across multi-turn sessions (`history_compaction`).
  4. ~6,200-token monolithic inline reference manual in `nexus_router` (`modular_skills`).
  5. Unbounded `ThinkingLevel.HIGH` reasoning across sub-agents (`thinking_budget`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from examples.shared.config_adapter import FRONTIER_MODEL_NAME
from examples.shared.mock_llm import build_nexus_agents

MODEL_NAME: str = FRONTIER_MODEL_NAME
_DEFAULT_EXPORT = os.environ.get(
    "TOKENOMICS_AUTO_EXPORT_PATH",
    str(
        _REPO_ROOT
        / "examples"
        / "artifacts"
        / "traces"
        / "live_unopt_session.json"
    ),
)

bundle = build_nexus_agents(
    optimized=False,
    app_name="nexus_unoptimized",
    auto_export_path=_DEFAULT_EXPORT,
)

root_agent = bundle.root_agent
app = bundle.app
tower = bundle.tower
tokenomics_plugin = bundle.plugin
