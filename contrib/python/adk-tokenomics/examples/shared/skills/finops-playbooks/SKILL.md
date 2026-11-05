---
name: finops-playbooks
description: Enterprise AI unit economics, context caching, model tiering, and thinking-budget guardrails for ADK multi-agent systems.
---

# Enterprise AI FinOps Playbook (`finops-playbooks`)

## 1. Unit Economics Guardrails
- **Target Cost per Turn:** Keep average turn spend `<= $0.0040` across multi-agent sessions.
- **Prefix Context Caching:** Enable `ContextCacheConfig(min_tokens=1024, ttl_seconds=300)` on every multi-agent `App` so repeated system instructions and tool declarations receive the 75%-95% cached prefix discount.
- **Multi-Turn Compaction:** Enable `EventsCompactionConfig(compaction_interval=4, overlap_size=1)` to bound conversation history growth across multi-turn sessions.

## 2. Sub-Agent Model Tiering Matrix
- **Tier Minimal (`gemini-3.8-flash`, `ThinkingLevel.MINIMAL`):** Root intake routers and final Markdown/JSON packagers.
- **Tier Low (`gemini-3.8-flash`, `ThinkingLevel.LOW`):** Parallel retrieval analysts, quantitative tool runners, and rubric gatekeepers (`adversarial_critic`).
- **Tier Medium (`gemini-4-argon`, `ThinkingLevel.MEDIUM`):** Complex multi-source executive synthesis (`report_drafter`).
