# The Investment Research Agent: a walkthrough

This document guides a reader who has not opened the notebook through the agent in section 4 of `notebook.ipynb` (developed in `dev/agent.ipynb`): what it does, how data moves through it, and why it is built the way it is. It is organized under the three headings the project rubric asks the code comments to cover, so it can grow into the optional Supplemental Report. It is updated at each build step; the status table below says which parts exist in code and which are still design.

| Part | Status |
|---|---|
| Memory store (`__init__`) | Built, step 1 |
| Step registry, planner menu, development stand-ins | Built, step 2 |
| `plan()` | Planned, step 3 |
| `run()` with `brief()`, `write_report()`, `report_criteria()` | Planned, step 4 |
| `reflect()`, `remember()` | Planned, step 5 |
| Demonstration and figures | Planned, step 6 |
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

### 2.1 Plans (`plan`, planned)

The Coordinator makes one JSON-mode call. Its prompt holds a menu of available steps (what each returns, when it is worth running, and its allowed arguments) and the agent's memory for this symbol: the notes from earlier runs on it, then every general lesson, or "none yet". It returns an ordered list of at most eight steps, each `{"tool", "args", "why"}`.

Design choices:

- **Temperature 0 for the planner only.** With sampling noise removed, memory is the only input that differs between a first and a second run on the same symbol, so a changed plan can be attributed to what the agent learned.
- **A lean plan.** The prompt asks for only the steps the note needs. If the first plan already called every tool, memory would have nothing to add and the learning demonstration would be empty.
- **`why` cites memory.** When a step exists because of a stored note, its `why` says so. That makes memory's influence visible even when two plans use the same tools.
- **Unknown tools are kept, not filtered.** A step naming a tool that does not exist reaches the executor, which logs and skips it. The mistake stays visible and becomes something the Reflector can learn from.

### 2.2 Uses tools dynamically (`run`, planned)

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

### 2.3 Self-reflects (`reflect`, planned)

Reflection has two parts. The Critic scores the final note against the run's criteria using section 3's `evaluate`. The Reflector then reads the whole run (the plan, the tool log, the score history, and the Critic's feedback) and returns a note specific to this symbol, such as "add get_fundamentals; the fundamentals criterion failed without it", plus a general lesson when one applies to any symbol.

Design choices:

- **The Critic grades the text; the Reflector grades the process.** A low score says the note was weak. Only the plan and the tool log can say why, which is what the next plan needs to change.
- **Criteria carry the facts.** `evaluate(text, criteria)` sees only the note and the criteria string. The criteria therefore include the reference figures from `brief()`; without them the Critic could check that a revenue figure is present but not that it is correct.

### 2.4 Learns across runs (`remember`, memory built)

Memory is a dictionary on the agent, created empty in `__init__`:

```python
self.memory = {"symbols": {}, "lessons": []}
```

`symbols` maps a symbol to the list of notes about it, oldest first. `lessons` holds notes that apply to any symbol. `remember(symbol, note, lesson)` appends the note under its symbol and adds the lesson if it is new. The planner reads both on the next run.

Design choices:

- **Two kinds of memory.** A note such as "AAPL's earnings criterion failed without fundamentals" should change AAPL's next plan. A lesson such as "run the news chain before routing" should change every plan. Keeping them apart lets the demonstration show each one separately.
- **In memory, not on disk.** An earlier design wrote memory to `memory/memory.json`. Only the agent reads or writes memory, so nothing else depends on the file, and a file would carry notes from the last session into the next run of the notebook. The run exported to PDF would then begin with memory already full, and the first run would no longer be a cold start. A dictionary on the agent starts empty every time the notebook runs, so the demonstration is reproducible: the learning shown is learning that happened inside that execution.

## 3. Evaluation and Iteration

*(Planned, step 6. Results are filled in once the demonstration runs on the real lane functions.)*

The demonstration runs one agent three times, in this order: AAPL, AAPL, NVDA. Each run is `run`, then `reflect`, then `remember`, and a copy of memory is kept after each.

- **AAPL run 2 against run 1** shows a symbol note at work. Same symbol, same data, planner at temperature 0; the only new input is the note from run 1.
- **NVDA** has no notes of its own, so any change from the first AAPL plan comes from the general lessons, showing that learning transfers across symbols.

The figures:

1. AAPL plan 1 beside plan 2, with the memory between them printed.
2. The Critic's score per round for each run, and the reflection score per run.
3. Team status: LLM calls and tokens per agent, read from `CALL_LOG`.

Known variation: only the planner runs at temperature 0. The Writer, Critic, and Reflector sample at 1.0, so scores and wording differ between exports of the notebook. A rough estimate is 40 LLM calls per run, most of them in routing (one route and one analysis per article).

### Iteration log

Problems found while building, and what changed because of them.

| Date | Observed | Change |
|---|---|---|
| 2026-10-01 | Asked to revise a flawed note, the Writer returned commentary about the note's problems instead of a revised note. The prompt said what to fix but not what to return. | Revision prompts end with "Reply with the revised report only, no commentary on what changed." |
| 2026-10-01 | When the criteria named a data field (`revenue_b`), the revised note quoted the field name in its prose. | Criteria and the Writer prompt describe figures in plain language ("annual revenue in billions of USD"); field names stay in the data. |

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
