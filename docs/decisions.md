# Shared decisions

Settings every lane depends on. Changing one is a team decision, logged here with a date.

| Decision | Value | Why |
|---|---|---|
| LLM access | `openai` SDK; `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` from `.env`; only `src/llm.py` talks to the model | One config switch between OpenAI, OpenRouter, and local servers; JSON parsing and timeouts solved once |
| Model | `deepseek/deepseek-v4.1-flash` through Nous Portal (`https://inference-api.nousresearch.com/v1`, an OpenRouter-catalog mirror), one shared key; `deepseek-v4-flash-0731` is the fallback | Fast, flat JSON 36/36 in tests, reasoning can be switched off. GLM-5.3 Flash tested and rejected: mandatory reasoning on this gateway, wraps JSON in an extra key |
| Data | `yfinance` only; every tool response cached as JSON under `data/cache/` and committed | Offline, reproducible reruns; identical data for every teammate; rate limits are a one-time problem |
| Symbols | AAPL (run twice), NVDA (run once) | Minimum that demonstrates memory across runs |
| Iteration caps | Evaluator-optimizer max 2 refinements; plan max 8 steps; every call has a timeout | Bounded cost and guaranteed termination |
| Memory | `memory/memory.json` with two keys, `symbols` and `lessons`, read by the planner prompt | Smallest thing that visibly changes the next run |
| Framework | None; plain Python as in the Module 7 lab | Rubric grades the patterns, not a framework |
| Code placement | Graded logic as notebook cells; only plumbing in `src/` | The grader reads a PDF |
| Python | 3.12, uv, `pyproject.toml` + `uv.lock` committed; `ruff` for PEP 8 | Reproducible env; PEP 8 is required |
| Fundamentals units | `get_fundamentals` returns money in billions (`market_cap_b`, `revenue_b`), ratios as percentages (`*_pct`), plus a `currency` field; units are in the key names | Raw Yahoo integers (302970011648) were misread by the model as $3.03T in one of three simulated runs; scaling once in the tool means no prompt ever formats numbers |
| NLP library | spaCy 3.8 with `en_core_web_sm` 3.8.0 declared as a dependency (installed by `uv sync`, no download step) | Lane 1's preprocess and extract steps; a pinned wheel means every machine has the same model |
| Evaluator feedback shape | `evaluate()` returns `feedback` as a list of strings, each naming the criterion it failed; `refine()` takes that list | Easier to print, count, and feed back than one paragraph |
| Reflection and memory shape | `reflect(symbol, run_result) -> {"score", "note", "lesson"}`; `remember(symbol, note, lesson=None)` | A useful note needs the plan and tool log, not only the report; a general lesson needs somewhere to go |

## Change log

| Date | Change | Who |
|---|---|---|
| 2026-09-19 | Initial decisions from the team proposal. | Ian |
| 2026-09-19 | Kickoff: model fixed to DeepSeek V4.1 Flash via Nous Portal; lanes assigned (see contributions.md). | Team |
| 2026-09-20 | GLM-5.3 Flash evaluated as default and rejected (mandatory reasoning, wrapped JSON, stray fences); DeepSeek V4.1 Flash stays. | Ian |
| 2026-09-22 | Contract shapes settled for evaluator feedback, `reflect`, and `remember`. Calendar: early deliverables Oct 4, assembly Oct 12 to 14, submission Sun Oct 18. | Ian |
