# Contribution log

One line per piece of work, added by the person who did it, the week it happened. This is the source for the Module 7 peer evaluation and the 4.2 status form.

| Date | Who | Lane | What |
|---|---|---|---|
| 2026-09-19 | Team | all | Kickoff: lanes assigned. L1 Jackson Kenyon (prompt chaining), L2 Ali Abdul-Hameed (routing), L3 Nina Zhao (evaluator-optimizer), L4 Ian Schmitt (plumbing, agent, integration) |
| 2026-09-19 | Ian Schmitt | L4 | Repo, README, license, uv project, `src/llm.py`, `src/tools.py`, cache for AAPL and NVDA, `.env.example`, docs skeleton |
| 2026-10-03 | Nina Zhao | L3 | Evaluator-optimizer MVP in `dev/evaluate.ipynb` and its `dev/evaluate.py` export: per-criterion Critic with reply checking and one retry, Writer revision from the feedback, loop capped at two revisions and ending on a grade of the final text; demo on AAPL and NVDA with a score table, score-per-round plot, before/after, and calls by agent |
