# Shared decisions

Settings every lane depends on. Changing one is a team decision, logged here with a date.

| Decision | Value | Why |
|---|---|---|
| LLM access | `openai` SDK; `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` from `.env`; only `src/llm.py` talks to the model | One config switch between OpenAI, OpenRouter, and local servers; JSON parsing and timeouts solved once |
| Data | `yfinance` only; every tool response cached as JSON under `data/cache/` and committed | Offline, reproducible reruns; identical data for every teammate; rate limits are a one-time problem |
| Symbols | AAPL (run twice), NVDA (run once) | Minimum that demonstrates memory across runs |
| Iteration caps | Evaluator-optimizer max 2 refinements; plan max 8 steps; every call has a timeout | Bounded cost and guaranteed termination |
| Memory | `memory/memory.json` with two keys, `symbols` and `lessons`, read by the planner prompt | Smallest thing that visibly changes the next run |
| Framework | None; plain Python as in the Module 7 lab | Rubric grades the patterns, not a framework |
| Code placement | Graded logic as notebook cells; only plumbing in `src/` | The grader reads a PDF |
| Python | 3.12, uv, `pyproject.toml` + `uv.lock` committed; `ruff` for PEP 8 | Reproducible env; PEP 8 is required |

## Change log

| Date | Change | Who |
|---|---|---|
| 2026-09-19 | Initial decisions from the team proposal. | Ian |
