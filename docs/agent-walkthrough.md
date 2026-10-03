# The Investment Research Agent: a walkthrough

This document guides a reader who has not opened the notebook through the agent in section 4 of `notebook.ipynb` (developed in `dev/agent.ipynb`): what it does, how data moves through it, and why it is built the way it is. It is organized under the three headings the project rubric asks the code comments to cover, so it can grow into the optional Supplemental Report. It is updated at each build step; the status table below says which parts exist in code and which are still design.

| Part | Status |
|---|---|
| Memory store (`__init__`) | Built, step 1 |
| Step registry, planner menu, development stand-ins | Built, step 2 |
| `plan()` | Built, step 3; lean-plan tuning waits for step 6 |
| `run()` with `brief()`, `write_report()`, `report_criteria()` | Built, step 4 |
| `reflect()`, `remember()` | Built, step 5 |
| Demonstration and figures | Built, step 6; run order under review |
| Real lane functions in place of stand-ins | After Oct 4, step 7 |

## 1. Agent Design and Workflows

### What the agent does

Given a stock symbol, the Investment Research Agent decides which research steps to take, takes them, writes a short research note from what it found, grades its own note, and stores a lesson that changes how it plans the next time. It never recommends buying, selling, or holding; the project's name is a design constraint.

The project distinguishes workflows from an agent in the sense of Anthropic's *Building Effective Agents*: in a workflow, our code fixes the sequence of LLM calls; in an agent, the LLM chooses the sequence. Sections 1 to 3 of the notebook are workflows. Section 4 is the agent, and it uses the three workflows as tools it can choose to call.

### One research cycle

```
            memory: {"symbols": {"AAPL": [notes]}, "lessons": [...]}  <------------------+
                 |                                                                    |
 1 PLAN      Coordinator reads memory, picks steps -> [{"tool", "args", "why"}]       |
                 |                                                                    |
 2 EXECUTE   for each step, by name:                                                  |
               get_prices / get_fundamentals / get_news     (src/tools.py, cached)    |
               run_chain          -> News Analyst            (section 1)              |
               route_and_analyze  -> Router + Specialists    (section 2)              |
             every step logged; a failed step is recorded, not fatal                  |
                 |                                                                    |
 3 WRITE     Writer drafts, Critic scores, Writer revises    (section 3, <= 2 rounds) |
                 |                                                                    |
 4 REFLECT   Critic rescores the final note; Reflector reviews the whole run          |
               -> {"score", "note" for this symbol, "lesson" for any symbol}          |
                 |                                                                    |
 5 REMEMBER  note and lesson appended to memory  ---------------------------------------+
```

The four agent functions the rubric requires map onto this cycle one to one: planning is step 1, dynamic tool use is step 2, self-reflection is step 4, and learning across runs is step 5 feeding the next step 1.

### The agents

The system is one agent loop staffed by named roles. Every LLM call carries its role through `chat(..., agent="Name")`, which records it in `llm.CALL_LOG`, and every pass of work from one role to another prints one line through `handoff(sender, receiver, content)`. The notebook output therefore reads as a transcript of who handed what to whom, the way the Module 7 lab's multi-agent team does, without a framework.

| Agent | Owner | Job |
|---|---|---|
| Coordinator | Lane 4 | Plans the research and dispatches each step |
| News Analyst | Lane 1 | Runs the prompt chain over recent news |
| Router | Lane 2 | Labels each item earnings, news, or market |
| Earnings, News, Market Specialist | Lane 2 | Analyze the items routed to them, each with its own data |
| Writer | Lane 4 (drafts), Lane 3 (revises) | Writes and revises the research note |
| Critic | Lane 3 | Scores a note against explicit criteria and lists what failed |
| Reflector | Lane 4 | Turns a finished run into a note and a lesson for memory |

### Plumbing

Two small modules sit under every lane. `src/llm.py` holds `chat()`, the only path to the model (DeepSeek V4.1 Flash through the Nous Portal gateway); it returns text, or a parsed JSON object with one correction round, and it raises on a truncated or empty reply instead of passing a broken answer downstream. `src/tools.py` holds the three Yahoo Finance tools. Each caches its response as JSON under `data/cache/`, and the cache is committed, so every teammate and every rerun of the notebook sees identical data and the notebook runs offline.

### Building before the lanes exist

The agent depends on all three workflow sections, which are built in parallel by other team members. To build it before they deliver, `dev/agent.ipynb` carries a development-only cell of stand-ins with the same names, arguments, and return shapes as the real functions: `run_chain` labels the cached news as neutral, `route_and_analyze` sends every item to the news route, and `evaluate` and `evaluator_optimizer` make real Critic and Writer calls so reflection has a real score to work with. When the lanes deliver, that cell is replaced by three imports and nothing else in the agent changes. The contracts in the appendix are what make the swap safe.

### Why no agent framework

The rubric grades the patterns, not a library. Plain Python keeps every decision visible in the exported PDF: the plan is a list the reader can print, the dispatch is a dictionary lookup, and memory is a dictionary. A framework such as LangGraph would add a dependency and hide the control flow that the grader needs to see.

## 2. Agent Functions and Capabilities

### 2.1 Plans (`plan`)

The Coordinator makes one JSON-mode call. Its prompt holds a menu of available steps (what each returns, when it is worth running, and its allowed arguments) and the agent's memory for this symbol: the notes from earlier runs on it, then every general lesson, or "none yet". It returns an ordered list of at most eight steps, each `{"tool", "args", "why"}`.

Design choices:

- **Temperature 0 for the planner only.** Memory is then the only input that differs between a first and a second run on the same symbol. In testing, temperature 0 on this gateway did not make the planner repeatable. Within one test session, identical requests gave the same sequence of tools in different words; across sessions, the same empty-memory request produced all five steps in one session and three in another. Temperature 0 alone therefore cannot attribute a changed plan to memory (see Evaluation and Iteration).
- **The planner does not see the Critic's criteria.** It is told the goal (a short factual note, no recommendation) and nothing about how the note will be graded. What a good note needs is something the agent learns from the Critic's feedback, run by run; a planner shown the criteria would plan perfectly on the first run and leave memory nothing to teach.
- **A lean plan.** The prompt asks for only the steps the note needs and the menu states each step's cost in LLM calls. If the first plan already calls every tool, memory has nothing to add. In testing it did call every tool; see the iteration log.
- **`why` cites memory.** When a step exists because of a stored note, its `why` says so. That makes memory's influence visible even when two plans use the same tools.
- **Unknown tools are kept, not filtered.** A step naming a tool that does not exist reaches the executor, which logs and skips it. The mistake stays visible and becomes something the Reflector can learn from.

### 2.2 Uses tools dynamically (`run`)

The executor walks the plan and calls each step by name from one dispatch table: the three data tools from `src/tools.py` plus `run_chain` (section 1) and `route_and_analyze` (section 2). Which tools run, and in what order, is the planner's choice, not ours; no line of our code fixes the sequence, which is what makes the tool use dynamic.

The dispatch table is one line:

```python
STEPS = {**tools.TOOLS, "run_chain": run_chain, "route_and_analyze": route_and_analyze}
```

Next to it, `MENU` is the text the Coordinator reads when it plans: one entry per step giving its arguments, what it returns, and what it costs in LLM calls (none for the data tools, one per article for the chain, two per article for routing). Stating the cost is what gives a lean plan a reason to exist. The arguments shown are the ones whose responses are in the committed cache (`period="6mo"`, `limit=10`); any other value still works but fetches live from Yahoo.

Design choices:

- **One special case for data flow.** `route_and_analyze` needs a batch of items. The executor passes it the articles from `run_chain` when the plan ran the chain, and the raw cached news when it did not. Every other step is called as `tool(symbol, **args)`.
- **A failed step is recorded, not raised.** Each step runs inside a `try`; a failure is written to the run log with its error and the run continues. A research run that loses one source should still produce a note, and the failure becomes evidence for reflection.
- **One compact view of the results.** Price history arrives as 125 daily closes, which would bloat every prompt. A `brief()` function reduces the results to the figures a note would cite, and the Writer, the Critic's criteria, and the Reflector all read that same view, so the numbers the Writer quotes are the numbers the Critic checks.
- **The note goes through the section 3 loop.** The Writer's draft is passed to `evaluator_optimizer` as its generator, so every report the agent produces has been scored and, if needed, revised.
- **The Writer quotes and never computes.** Its prompt says to quote figures exactly as given and derive none. A difference the Writer computes correctly (an 89.94-point gain from two closes) is still a figure the Critic cannot find in the reference data, and in testing it was graded as a mismatch.
- **Fixed criteria, whatever the plan gathered.** The Critic grades every note against the same six criteria (price change, a fundamental with its unit, news sentiment as counts, a named risk, no recommendation, figures that match the data). A plan that skipped a needed step yields a note that fails one, and that failure is what reflection turns into a note for the next plan. Only `run_chain` supplies sentiment counts, so a plan without it fails criterion 3.

### 2.3 Self-reflects (`reflect`)

Reflection has two parts. The Critic scores the final note against the run's criteria using section 3's `evaluate`. The Reflector then reads the whole run (the plan, the tool log, the score history, and the Critic's feedback) and returns a note specific to this symbol, such as "add get_fundamentals; the fundamentals criterion failed without it", plus a general lesson when one applies to any symbol.

Design choices:

- **The Critic grades the text; the Reflector grades the process.** A low score says the note was weak. Only the plan and the tool log can say why, which is what the next plan needs to change.
- **Temperature 0 for the Reflector.** Its reply becomes the memory the next plan reads, so sampling noise in reflection would surface as an unexplained change in the next plan.
- **The Reflector sees the lessons already stored** and is told not to restate one; `remember()` also skips a lesson that matches a stored one exactly.
- **Criteria carry the facts.** `evaluate(text, criteria)` sees only the note and the criteria string. The criteria therefore include the reference figures from `brief()`; without them the Critic could check that a revenue figure is present but not that it is correct.

### 2.4 Learns across runs (`remember`)

Memory is a dictionary on the agent, created empty in `__init__`:

```python
self.memory = {"symbols": {}, "lessons": []}
```

`symbols` maps a symbol to the list of notes about it, oldest first. `lessons` holds notes that apply to any symbol. `remember(symbol, note, lesson)` appends the note under its symbol and adds the lesson if it is new. `recall(symbol)` renders this symbol's notes and every lesson as one block of text, and two agents read that same block on the next run: the Coordinator when it plans, and the Writer when it drafts.

Design choices:

- **Two readers of memory.** A note can only fix what its reader controls. The first design gave memory to the planner alone, and the first real failure was in the writing (the note mischaracterized the sentiment counts). With no way to change the writing, the planner invented a verification step that did not exist. Memory now reaches the Writer too, and the Reflector, which sees the menu, says whether a failure came from the plan (name a step to add, drop, or change) or from the writing (say what the Writer must do differently). The planner is told that writing notes need no step.
- **Two kinds of memory.** A note such as "AAPL's earnings criterion failed without fundamentals" should change AAPL's next plan. A lesson such as "run the news chain before routing" should change every plan. Keeping them apart lets the demonstration show each one separately.
- **In memory, not on disk.** An earlier design wrote memory to `memory/memory.json`. Only the agent reads or writes memory, so nothing else depends on the file, and a file would carry notes from the last session into the next run of the notebook. The run exported to PDF would then begin with memory already full, and the first run would no longer be a cold start. A dictionary on the agent starts empty every time the notebook runs, so the demonstration is reproducible: the learning shown is learning that happened inside that execution.

## 3. Evaluation and Iteration

*(Built, step 6. Results are filled in once the demonstration runs on the real lane functions.)*

The demonstration runs one agent four times, interleaved: AAPL, NVDA, AAPL, NVDA. Each run is `run`, then `reflect`, then `remember`, and a copy of memory is kept after each.

- **Each symbol's second run** reads the note its first run wrote. Same symbol, same data, planner at temperature 0; the new input is memory.
- **NVDA's first run** has no notes of its own but reads AAPL's lessons, so a change there shows a lesson transferring across symbols.
- **A fresh-agent control.** Temperature 0 does not make the planner repeatable on this gateway, so a difference between two runs could be drift between calls made minutes apart, the way a batch effect separates samples run on different days. Before every run after the first, a new agent with empty memory plans the same symbol. Its plan and the run's were requested moments apart and differ only in memory. If the control matches the earlier plan and the run's plan differs, memory changed the plan; if the control matches the run's plan, memory did not; if it matches neither, the noise is too large for one sample and the control is repeated.
- **Why interleaved.** Learning can only appear when a run that failed is followed by a run that reads its memory, and which run fails is chance. The first order tried (AAPL, AAPL, NVDA) put NVDA's only run last; in the first end-to-end test that was the run that failed, and nothing read its note. Interleaving gives each symbol a second run. It does not guarantee an improvement: a second run can regress, as one did in testing, and only a third would show the correction.

The outputs:

1. For every run after the first: the memory it planned from, its plan beside the earlier plan and its own control, and a verdict line computed from the three (memory changed the plan; the plan matches the control; or the control matches neither). Where memory changed the plan, each step's `why`.
2. Everything in memory after the last run, and the final note from the last run.
3. The Critic's score at each round of the writing loop for each run, and the score reflection recorded per run.
4. Team status: LLM calls and tokens per agent across the demonstration, read from `CALL_LOG`.

Known variation: the planner, the Reflector, and the development Critic run at temperature 0, but this gateway does not make temperature 0 repeatable, and the Writer samples at 1.0. Plans, scores, and wording differ between exports of the notebook; the controls are what make any one export readable. A rough estimate is 40 LLM calls per run with the real lanes, most of them in routing (one route and one analysis per article).

### Iteration log

Problems found while building, and what changed because of them.

| Date | Observed | Change |
|---|---|---|
| 2026-10-01 | Asked to revise a flawed note, the Writer returned commentary about the note's problems instead of a revised note. The prompt said what to fix but not what to return. | Revision prompts end with "Reply with the revised report only, no commentary on what changed." |
| 2026-10-01 | When the criteria named a data field (`revenue_b`), the revised note quoted the field name in its prose. | Criteria and the Writer prompt describe figures in plain language ("annual revenue in billions of USD"); field names stay in the data. |
| 2026-10-01 | With empty memory the planner chose all five steps, including `get_news` before `run_chain`, "so later steps have source material". The menu had not said that `run_chain` fetches the news itself. | The menu now says so. The planner still chose all five steps. |
| 2026-10-01 | The Critic, sampling at temperature 1.0, gave a correct 89.94-point difference a failing mark and wrote partly incoherent feedback; the revision then scored lower than the draft (3, then 0). | The Writer now quotes figures and computes none. The development Critic runs at temperature 0, after which its feedback named real, specific problems. Recommended to Lane 3: grade at temperature 0, and return the best-scoring draft, not the last. |
| 2026-10-01 | With a plan that skipped `run_chain`, the Writer invented sentiment counts (14 positive, 9 negative, 22 neutral, against 10 headlines). The temperature-0 Critic caught it under criteria 3 and 6. | None needed: this is the failure the learning loop is meant to catch and correct on the next run. |
| 2026-10-01 | The Critic failed a P/E rounded to 38.6 against 38.591274. | Criterion 6 now allows rounding. |
| 2026-10-01 | One Writer call took 49.6 seconds against a 60-second timeout. A timeout inside the writing loop is not caught per step, so it would end the run. | Watching; not changed. |
| 2026-10-01 | Compared four model variants on the gateway: the empty-memory AAPL plan 10 times each in two interleaved batches, and one fixed note graded 5 times each by the Critic at temperature 0. Same tool sequence: v4.1 Flash 9 of 10, v4.1 Flash pinned to US servers 10 of 10, V4 Flash 6 of 10, V4 Flash 0731 5 of 10. Grading a note that lacked sentiment counts and a named risk, v4.1 Flash failed it every time (score 3 to 4, naming both gaps, plus one false claim that the 52-week range was missing from the data); V4 Flash and V4 Flash 0731 passed it with 8 to 10, and V4 Flash returned the criteria list as its feedback. The 0731 snapshot reported different backend fingerprints across calls, evidence that one model name is served by more than one backend. | Stay on v4.1 Flash. The older models plan less repeatably and grade leniently. The fresh-agent control is added to the demonstration. |
| 2026-10-02 | First two full cycles on AAPL. Every article in the stand-in chain is labeled neutral, and `Counter` omits labels with no articles, so the data read `{"neutral": 10}`. The Writer correctly stated 0 positive and 0 negative; the Critic could not find those zeros in the data and failed the note, and the Reflector turned the false failure into a wrong lesson ("report only the values present rather than inferring the missing ones as zero"). | `brief()` now always lists all three sentiment labels, zeros included. A representation quirk in the data became a false grade and then a false memory; the reference data a Critic checks against has to be complete. |
| 2026-10-02 | Following that note, the run-2 planner added a step that does not exist (`verify_sentiment_counts`). The executor logged it as unknown and continued; the Reflector read the log and wrote "Drop the verify_sentiment_counts step: it is not in the tool menu". | Reflection corrected the agent's own planning mistake on the next cycle. The cause is that the run-1 failure was a writing problem, which no change to the plan can fix; see 2.4. |
| 2026-10-02 | With memory reaching the Writer and the Reflector shown the menu, four AAPL cycles on the stand-ins gave Critic scores of 10, 6, 9, 10. The cycle-2 failure was diagnosed as a writing failure ("must report the news sentiment exactly as the labeled counts show"), with a matching lesson; cycle 4's first draft scored 10 with no revision. No step was invented. | One sequence, so suggestive only: the cycle-2 drop after a perfect cycle 1 shows how much a single score moves with the Writer at temperature 1.0. |
| 2026-10-02 | One Critic reply hit the 800-token cap inside `reflect()` and `chat()` raised, ending the run. The next 11 Critic replies used 17 to 192 tokens. Cause unknown: a greedy-decoding repetition loop at temperature 0 is the leading guess, and raising the cap would not cure that. | Watching. `chat()` raises without the text, so the next occurrence cannot be diagnosed either; including the end of a truncated reply in the error is proposed for `src/llm.py`. |
| 2026-10-02 | First end-to-end run of the demonstration on the stand-ins: 21 calls, about 24,600 tokens, 2 minutes 18 seconds. AAPL run 1 scored 10, so its note said to keep the plan; run 2 matched both run 1 and the control, and the verdict line reported that memory did not change the plan. NVDA was the run that failed (the Writer invented sentiment counts) and produced a specific note and lesson, but no later run read them. | The order assumes the first run fails, which is chance. Proposed: interleave AAPL, NVDA, AAPL, NVDA, so each symbol's second run reads its own note and whichever run fails is followed by one that can show the correction. |
| 2026-10-02 | Second end-to-end run. AAPL run 1's note said to ground risks in figures rather than in a headline's claim; AAPL run 2 dropped `run_chain` and `route_and_analyze`, citing that lesson, while the empty-memory control kept all five steps, so the verdict line credited memory with the change. With no labeled news, the Writer invented sentiment counts (2 positive, 0 negative, 1 neutral from 10 headlines) and scored 4. Reflection caught it: the new AAPL note says to run `run_chain` before stating counts, and a new lesson generalizes it. No later run read either. | The control attributes a change correctly in both directions: memory can make a plan worse, and the demonstration has to be able to show the correction. Feeds the run-order decision. |
| 2026-10-01 | Adding a research budget in LLM calls to the planner prompt made the first plan leaner in some runs, but results swung with small wording changes and the planner exceeded the budget it was given. With a stored note from a failed run, every variant changed the plan (dropped `get_news`, added `run_chain`). | No budget for now. Tuning the planner against invented notes fits noise; it waits for step 6, when real Critic feedback produces real notes. |

## 4. Areas to build on

- **Route the Critic's feedback back to a specialist.** Today a failed criterion leads the Writer to revise its prose. A stronger loop would send "no earnings figure" to the Earnings Specialist for a new analysis before the rewrite.
- **Replan after a failure.** The executor runs the plan once. A Coordinator that revises the remaining steps when a tool fails would turn a logged failure into a recovered one within the same run.
- **Persistent memory with pruning.** Saving memory between sessions is a small change (write the dictionary to JSON after `remember`), but notes accumulate. A real deployment would summarize or expire old notes so the planner prompt does not grow without bound.
- **More data sources as tools.** SEC EDGAR filings and FRED macroeconomic series fit the same pattern: one cached function per source, one line in the dispatch table, one entry in the planner menu.
- **Evaluate the evaluator.** The Critic is an LLM grading an LLM. Scoring a handful of notes by hand and measuring agreement with the Critic would say how far its scores can be trusted.
- **More symbols.** Two symbols show the mechanism. Evidence that memory improves notes in general would need many symbols and repeated runs, compared against an agent with memory switched off.

## Appendix: data shapes

| Function | Lane | Returns |
|---|---|---|
| `run_chain(symbol)` | 1 | `{"articles": [{"title", "summary", "sentiment", "topic", "entities"}], "summary": str}` |
| `route_and_analyze(symbol, items)` | 2 | `[{"item", "route", "analysis"}]` |
| `evaluate(text, criteria)` | 3 | `{"score": 1-10, "pass": bool, "feedback": list[str]}` |
| `evaluator_optimizer(generate, criteria, max_rounds=2)` | 3 | `{"final": str, "history": [{"round", "score", "pass", "feedback"}]}` |
| `ResearchAgent.plan(symbol)` | 4 | `[{"tool", "args", "why"}]`, at most 8 |
| `ResearchAgent.run(symbol)` | 4 | `{"symbol", "plan", "log", "results", "criteria", "report", "history", "calls"}` |
| `ResearchAgent.reflect(symbol, run_result)` | 4 | `{"score", "note", "lesson"}` |
| `ResearchAgent.remember(symbol, note, lesson=None)` | 4 | nothing; updates `self.memory` |
