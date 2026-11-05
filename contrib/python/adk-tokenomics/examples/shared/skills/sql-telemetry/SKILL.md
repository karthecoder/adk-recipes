---
name: sql-telemetry
description: BigQuery fleet telemetry schema (adk_agent_events and v_llm_response) and 4-bucket token decomposition formulas.
---

# BigQuery Fleet Telemetry Playbook (`sql-telemetry`)

## 1. Canonical Tables & Views
- **Base Events Table (`adk_agent_events`):** Captures `USER_MESSAGE_RECEIVED`, `LLM_REQUEST`, `TOOL_COMPLETED`, and `LLM_RESPONSE` events partitioned by `DATE(timestamp)` and clustered by `app_name, session_id`.
- **Analytics View (`v_llm_response`):** Extracts `usage_prompt_tokens`, `usage_tool_use_tokens`, `usage_cached_tokens`, `usage_completion_tokens`, and `thoughts_token_count`.

## 2. 4-Bucket Token Decomposition
1. **Fresh Input (`T_fresh`):** `(prompt_token_count + tool_use_prompt_token_count) - cached_content_token_count`
2. **Cached Prefix (`T_cached`):** `cached_content_token_count`
3. **Visible Output (`T_output`):** `candidates_token_count`
4. **Reasoning / Thinking (`T_think`):** `thoughts_token_count` (billed at output token rates)
