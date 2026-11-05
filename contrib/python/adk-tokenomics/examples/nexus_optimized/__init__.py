"""
Nexus Optimized ADK Agent Package (`nexus_optimized`).
Exposes `agent`, `root_agent`, `app`, and `MODEL_NAME` for `adk web examples/` discovery.
"""

from . import agent
from .agent import MODEL_NAME, app, root_agent

__all__ = ["MODEL_NAME", "agent", "app", "root_agent"]
