# The Investment Research Agent: a walkthrough

This document explains the agent in section 4 of `notebook.ipynb` (developed in `dev/agent.ipynb`): what it does, why it is built the way it is, what testing changed, and what the final run (October 12) shows. It follows the rubric's three headings and is the source for Lane 4's part of the Supplemental Report. A longer version, with every test narrated in full, is in PR #12's history (commit `dc1c011`).

## 1. Agent Design and Workflows

### What the agent does

Given a stock symbol, the agent decides which research steps to take, takes them, writes a short research note, grades and revises it, and stores a lesson that changes how it writes the next time. It never recommends buying, selling, or holding. In the terms of Anthropic's *Building Effective Agents*, sections 1 to 3 of the notebook are workflows (our code fixes the sequence of LLM calls) and section 4 is an agent (the LLM chooses the sequence), which uses the three workflows as tools.

### One research cycle

```
 1 PLAN      Coordinator picks steps -> [{"tool", "args", "why"}]
                 |
 2 EXECUTE   for each step, by name:
               get_prices / get_fundamentals                (src/tools.py, cached)
               run_chain          -> News Analyst            (section 1)
               route_and_analyze  -> Router + Specialists    (section 2)
             every step logged; a failed step is recorded, not fatal
                 |
            memory: ["lesson", ...]  <------------------------------------------------+
                 |                                                                    |
 3 WRITE     Writer drafts from the data and memory; Critic   (section 3, <= 2 rounds)|
             grades each criterion; Writer revises                                    |
                 |                                                                    |
 4 REFLECT   Reflector reads the run, above all the first draft's feedback            |
               -> {"score", "lesson"}                                                 |
                 |                                                                    |
 5 REMEMBER  a new lesson is added  -------------------------------------------------+
```

Planning is step 1, dynamic tool use step 2, self-reflection steps 3 and 4, and learning across runs step 5 feeding the next run's step 3. Memory reaches the Writer only (see 2.4).

### The agents

One agent loop staffed by named roles. Every LLM call names its role (`chat(..., agent="Name")`, logged in `llm.CALL_LOG`), and every pass of work prints one `handoff(sender, receiver, content)` line, so the output reads as a transcript of who handed what to whom.

| Agent | Owner | Job |
|---|---|---|
| Coordinator | Lane 4 | Plans the research and dispatches each step |
| News Analyst | Lane 1 | Runs the prompt chain over recent news |
| Router | Lane 2 | Labels each item earnings, news, or market |
| Earnings, News, Market Specialist | Lane 2 | Analyze the items routed to them, each with its own data |
| Writer | Lane 4 (drafts), Lane 3 (revises) | Writes and revises the research note |
| Critic | Lane 3 | Scores a note against explicit criteria and lists what failed |
| Reflector | Lane 4 | Turns a finished run into a lesson for memory |

### Plumbing

`src/llm.py` holds `chat()`, the only path to the model (DeepSeek V4.1 Flash through the Nous Portal gateway). It returns text, or parsed JSON with one correction round, and raises on a truncated or empty reply instead of passing a broken answer downstream. The one exception is a reply that spent its whole token budget and holds no text: it is sent once more (seen twice in about 280 calls; one crashed a final run on October 12). `src/tools.py` holds the three Yahoo Finance tools, each caching its response under `data/cache/`. The cache is committed, so every teammate and every rerun sees identical market data. `get_news` raises on an empty result: on October 11 Yahoo's news endpoint returned 404, and the cache would have replayed the empty list on every later run.

### How it was built

Until the three workflows delivered, `dev/agent.ipynb` used stand-ins with the same names, arguments, and return shapes (the stand-in Critic's per-criterion grading was then adopted by Lane 3). When they delivered, the stand-ins became three imports and nothing else in the agent changed: the written contracts (appendix) made the swap safe. No agent framework: plain Python keeps every decision visible in the export (the plan is a list, the dispatch a dictionary lookup, memory a list), where LangGraph would add a dependency and hide the control flow.

## 2. Agent Functions and Capabilities

### 2.1 Plans (`plan`)

The Coordinator makes one JSON-mode call with the goal and a menu of steps (what each returns, its arguments, and its cost in LLM calls) and returns at most eight `{"tool", "args", "why"}` steps. It sees neither the criteria nor memory.

- **The plan rarely changes, by design.** Every criterion needs data from one of four steps: the price change from `get_prices`, a fundamental from `get_fundamentals`, sentiment and topic counts from `run_chain`, and the specialist analyses the Writer draws risks from in `route_and_analyze`. With one goal, the complete plan is the only good plan, and the planner finds it: 7 of 7 plans in the final run, 14 of 14 on October 10, 20 of 20 in an earlier check. We did not invent goals or steps to make it vary for show. The choice still matters: with a plan that skipped `run_chain`, 0 of 24 first drafts met every criterion (October 3). A planner with a real choice would need goals that need different data, such as a valuation-only note graded on its own criteria.
- **Temperature 1.0 for every call.** Considered: temperature 0 for the planner, the Critic, and the Reflector, so that memory would be the only input differing between two runs. Testing undid it (October 2). Temperature 0 was not repeatable on this gateway (one empty-memory request planned five steps in one session and three in another), and at 0 the Critic sometimes reasoned aloud inside its JSON until the token cap, which ended two demonstration runs: 1 truncation in 60 calls, against 0 in 120 at 1.0, the model card's recommendation, where it graded as accurately. The cost is variance (the Critic's score spread rose from a standard deviation of 0.9 to 1.5), which the twins and trials handle.
- **Unknown tools are logged, not filtered,** so a planning mistake stays visible to the Reflector (see the invented `verify_sentiment_counts` step, October 2).
- **No research budget.** A budget in LLM calls made some plans leaner, but results swung with small wording changes and the planner exceeded the budget it was given.

### 2.2 Uses tools dynamically (`run`)

The executor walks the plan and calls each step by name from one dispatch table:

```python
STEPS = {
    "get_prices": tools.get_prices,
    "get_fundamentals": tools.get_fundamentals,
    "run_chain": run_chain,
    "route_and_analyze": route_and_analyze,
}
```

No line of our code fixes which tools run or in what order. `MENU`, which the Coordinator reads, gives each step's arguments, return, and cost in calls, so a lean plan has a reason to exist.

- **One data-flow special case.** `route_and_analyze` gets `run_chain`'s result when the plan ran the chain, and the raw news when it did not.
- **A failed step is recorded, not raised,** so a run that loses one source still produces a note and the failure becomes evidence for reflection.
- **No news tool in the menu.** `run_chain` fetches the same articles itself, so plans with both read the news twice.
- **Routing takes every article the chain kept.** A five-article cap (each article costs two calls) cut AAPL's articles in feed order and left out the one about a price-target cut, and a 300-character cut on specialist analyses could drop the sentence naming a risk. Both were removed on October 10.
- **One compact view of the results.** `brief()` reduces them to the figures a note would cite, and the Writer, the Critic's reference data, and the Reflector all read it, so the numbers the Writer quotes are the numbers the Critic checks. It drops the 127 daily closes, rounds fundamentals (Yahoo's P/E arrives as 28.099874, and the Writer quotes exactly), and lists every sentiment label, zeros included (see October 2 in the log).
- **The Writer quotes and never computes.** A correctly computed 89.94-point gain was still a figure the Critic could not find in the data, and was graded a mismatch.
- **Risks come from the specialists,** each tied to its headline or figure, so routing shows in the notes.
- **Fixed criteria, whatever the plan gathered:** price change, a fundamental with its unit, sentiment as three counts, a supported risk, no recommendation, figures that match the data, and the most common topic with its count. A plan that skips a step fails one. These seven differ from section 3's nine because the note draws on the chain's labels, which section 3's data lacks.
- **A criterion chosen so learning can show (disclosed).** Criterion 7 was added on October 3, when a demonstration stored no memory because its first drafts were clean (11 of 12 AAPL and 5 of 12 NVDA first drafts met every criterion with the full plan); with it, 6 of 6 memories carried a lesson, against 1 of 6. The Writer's drafting prompt never shows the criteria (only the reviser sees them), so a first draft meets criterion 7 only through memory: an analyst learning an editor's house standard from feedback. A second candidate (where the close sits in its 52-week range) was missed 35% of the time with or without memory, so it was not learnable and was dropped. The claim this supports is that memory teaches standards the Writer is never told when drafting, not that memory improves notes in general.

### 2.3 Self-reflects (`reflect`)

Within a run, section 3's Critic grades each draft and the Writer revises, at most twice. After it, the Reflector reads the whole record (final note, criteria with reference data, plan, tool log, score history, and the first draft's feedback) and returns one lesson for what the first draft missed, or null if it missed nothing.

- **The Critic grades the text; the Reflector grades the process,** reading the note beside the data, plan, and tool log, which can say why it was weak.
- **Learn from the first draft.** The loop revises most failing drafts to a pass, so a Reflector that saw only the final grade stored memory after 0 to 2 of 8 runs while first drafts averaged 4.7 to 5.5 (October 3). Given the first draft's feedback, it stored memory after 6 of 8, and the next first draft rose 1.17 points (n=24), 0.75 on the other symbol. Two further additions (example sentences; tagged memory read in order) gave +0.89 and +0.51, no better within noise, and were dropped.
- **Memory has to earn its place.** With the first Reflector prompt, memory made later first drafts worse (by 0.28 points, worse in 10 of 17). The worst cases followed runs that had passed, where the Reflector still wrote advice that contradicted itself: "Run passed all criteria at 10/10 — keep the plan as-is … the only gap is criterion 4". Three rules fixed it: store nothing after a clean first draft; never ask for less than a criterion requires (a lesson once told the Writer never to use labels like "elevated", while criterion 4 requires that kind of judgment); say what to do, not what to avoid, because rules about what to avoid accumulated and narrowed later notes. With them, memory raised later first drafts by 0.63 points (October 2, data held fixed; about 1.4 standard errors, suggestive rather than conclusive).
- **Instructions, not figures.** Memory used to quote the run's values ("'news,' count 7"), and the next AAPL run's chain labeled 6, so a Writer trusting memory over the data would fail criterion 6. Lessons now say what to state and which part of the data holds it. Replaying the Reflector ten times on one run, memory with figures fell from 10 of 10 to 0 of 10.
- **No repeats.** The Reflector sees stored lessons and is told not to restate one; `remember()` skips an exact repeat.
- **One grade per note.** A second Critic call on the same note disagreed with the first (a pass, then a 4), so reflection reuses the loop's last grade.
- **Criteria carry the facts.** The criteria string includes `brief()`'s figures; without them the Critic could check that a revenue figure is present but not that it is correct.

### 2.4 Learns across runs (`remember`)

Memory is a list on the agent, `self.lessons = []`, created empty in `__init__`. `remember(lesson)` adds a new lesson, and `recall()` renders every lesson into the Writer's next draft, for any symbol; with no lessons the Writer gets no memory block.

- **Memory is the Writer's.** The first design gave memory to the planner alone, but the first real failure was in the writing; with no way to change it, the planner invented a verification step. Memory then reached both, and once changed a plan (October 3: after a run that skipped `run_chain` failed criterion 3, the next plan restored the chain while the memoryless twin skipped it again). But plan learning only fired when run 1 happened to skip the chain, and once the news tool was folded into the chain, 20 of 20 plans included it, so it was dropped.
- **One kind of memory.** Memory first held notes per symbol beside general lessons. Misses were nearly always about content every note needs, and no full run after October 4 stored a symbol note, so memory became lessons only (October 10). Runs end with one to three lessons (two in the final run).
- **In memory, not on disk.** A file would carry lessons into the next execution, so the exported run would begin with memory full and no longer start cold. A list on the agent means the learning shown happened inside that execution.

## 3. Evaluation and Iteration

One agent runs four times: AAPL, NVDA, AAPL, NVDA. Each run is `run`, then `reflect`, then `remember`.

- **Interleaved.** Learning only shows when a failed run is followed by one that reads its lesson, and which run fails is chance; the first order tried (AAPL, AAPL, NVDA) put the failing run last. Interleaving gives each symbol a second run, and NVDA's first run, reading only AAPL's lessons, tests transfer.
- **Twin runs.** Every run with memory to read is paired with the same run by a new agent with empty memory, so the twin controls for the whole run. Twins replaced plan-only controls, which at temperature 1.0 printed "planner noise is too large to read from one sample" for two of three runs and could not see memory's effect on the writing. One pair is one sample, so a twin suggests rather than proves.
- **Repeated trials.** For each twinned run, the first draft is written seven more times with that run's memory and seven times without, from the run's stored data, and graded once each; only memory differs. The trials run inside the notebook, replacing an earlier figure (25% to 74% of first drafts meeting every criterion) from a test on the stand-ins whose script was not kept.
- **First drafts, not final notes.** The loop revises nearly every draft to a pass: on October 3, twin comparisons of final scores tied 10 against 10 four times in six.
- **Retry.** A run that raises is retried once (failures ran about 4 in 600 test calls; a demonstration makes over 180), which is safe because only `remember()` changes memory.

**Final run** (October 12, outputs committed in the notebook): 184 demonstration and 84 trial calls, no errors, no run retried, 17 minutes end to end. AAPL run 1's first draft missed criteria 3 and 7, and the Reflector stored one lesson covering both. NVDA run 1 read only that lesson and met both; its one miss was criterion 4 (a risk backed by a figure that did not support it), and the Reflector stored a second lesson, to tie each risk to the figure or headline that supports it. Both second runs wrote clean first drafts and stored nothing. Memory won every twin comparison: first drafts of 9, 10, and 10 against 6, 9, and 7, and every twin missed criterion 7. The trials:

| First drafts (21 per condition) | With memory | Without memory |
|---|---|---|
| Met every criterion | 100% | 0% |
| Missed criterion 7 (the most common topic, with its count) | 0% | 100% |
| Missed criterion 3 (sentiment as three counts) | 0% | 57% |
| Missed criterion 4 (a supported risk) | 0% | 14% |
| Missed criterion 5 (no recommendation) | 0% | 10% |
| Mean score | 10.0 | 7.57 |

No draft on either side missed criteria 1, 2, or 6. Memory's effect is on criteria 7 and 3, two standards the Writer is never told when drafting. The criterion 4 gap is three drafts, the first gap on it in a full run: on October 10, with no risk lesson stored, 3 of 21 missed it on each side (trials 9.81 against 7.57). The one irregular reply was the Router's: an empty label for one AAPL article, which went to the News Specialist by default.

At temperature 1.0, plans, labels, wording, and scores differ between exports. A run makes about 21 to 34 LLM calls: 11 in the chain, two per routed article, 2 to 5 in the writing loop, plus the planner and the Reflector.

### Iteration log

Problems found while building, and what changed because of them.

| Date | Observed | Change |
|---|---|---|
| 10-01 | Asked to revise a note, the Writer returned commentary on the note's problems instead of a revised note. | Revision prompts end "Reply with the revised report only, no commentary on what changed." |
| 10-01 | A criterion named a data field (`revenue_b`), and the revised note quoted the field name in its prose. | Criteria and prompts describe figures in plain words; field names stay in the data. |
| 10-01 | The Critic failed a correct 89.94-point difference with partly incoherent feedback, and the revision scored lower (3, then 0). It also failed a P/E of 38.6 against 38.591274. | The Writer quotes and never computes; criterion 6 allows rounding; Lane 3's loop keeps the best-scoring draft, not the last. |
| 10-01 | With a plan that skipped `run_chain`, the Writer invented sentiment counts (14 positive, 9 negative, 22 neutral, from 10 headlines). The Critic caught it. | None: this is the failure the learning loop exists to catch. |
| 10-01 | Four model variants on the gateway. Same tool sequence in 9, 10, 6, and 5 of 10 plans (v4.1 Flash, v4.1 Flash pinned to US servers, V4 Flash, V4 Flash 0731). Grading a note that lacked sentiment counts and a risk, v4.1 failed it every time (3 to 4); the older models passed it (8 to 10). 0731 reported several backend fingerprints for one model name. | Stay on v4.1 Flash. |
| 10-02 | The stand-in chain labeled every article neutral, and `Counter` omits zero counts, so the data read `{"neutral": 10}`. The Writer correctly wrote 0 positive and 0 negative; the Critic could not find those zeros and failed the note; the Reflector stored a wrong lesson ("report only the values present rather than inferring the missing ones as zero"). | `brief()` lists all three labels, zeros included. A quirk in the data became a false grade, then a false memory: a Critic's reference data has to be complete. |
| 10-02 | Following that lesson, the next planner added a step that does not exist (`verify_sentiment_counts`). The executor logged it; the Reflector wrote "Drop the verify_sentiment_counts step: it is not in the tool menu". | Reflection corrected the agent's own planning mistake. The root cause, a writing failure sent to the planner, led to Writer memory (2.4). |
| 10-02 | A risk lesson led AAPL run 2 to drop `run_chain` and `route_and_analyze` while its memoryless control kept them; with no labeled news, the Writer invented counts and scored 4, and reflection told the next run to restore the chain. | Memory can make a plan worse, so the demonstration must be able to show the correction: interleaved runs. |
| 10-02 | British spellings ("capitalisation", "defence") in a final note. | Writer prompt ends "Write in American English." |
| 10-02 | Adversarial review by a second model (Codex, GPT-6 Astra). Seven findings, including: the Reflector never saw the note or the data this document said it read; a verdict claimed causation from one control; any exception outside a plan step ended the demonstration. | All seven fixed. |
| 10-03 | A full run on stand-ins: the Critic gave 2/10 to a note whose feedback called criteria 2 and 5 "Satisfied" and penalized a no-recommendation disclaimer, and memory learned the quirk ("included hedging about a recommendation"). Stand-in text leaked into notes ("the accompanying analyses are stand-in text"); all three memory entries repeated one instruction. | Per-criterion Critic scored as the share met, which Lane 3 adopted; criteria 4 and 5 reworded; `brief()` rounds fundamentals. |
| 10-03 | Sampling: top_p 0.95 against 1.0, 150 calls each, gave no failures and the same mean first draft (8.55 and 8.57). Another test lost every call to `APIConnectionError`; the gateway recovered minutes later. | No sampling change; a failed run is retried once; export only when the gateway is healthy. |
| 10-04 | All three real lanes in: 180 calls, no errors. Every twin missed criterion 7 and every run with memory met it. The planner twice spent 800 tokens and returned nothing. | The planner gets 1500 tokens. |
| 10-04 | The 25%-to-74% memory figure in the docs came from a script nobody kept. Memory quoted figures, and "carry forward what still applies" grew AAPL's note into a 100-word restatement of the criteria. The chain and the router, labeling the same articles, agreed on 6 of 10 (AAPL) and 5 of 10 (NVDA): the chain called most articles "news". | In-notebook trials (first: 13 of 14 first drafts met every criterion with memory, 0 of 14 without); lessons by default, without figures; topic definitions sent to Lane 1 (#6). |
| 10-10 | After Lane 1's `other` filter: the routing cap cut AAPL's price-target article. An NVDA note cited a Nasdaq-100 article's 83 percent dot-com loss as an NVDA risk, and the Critic passed it. | Routing cap and 300-character cut removed; memory became lessons only. The dot-com article is Lane 1's classifier's call, not changed here. |
| 10-11 | A rerun on fresh data, to check the results were not specific to the cache, could not run: Yahoo's news endpoint returned 404 and yfinance an empty list. A News Specialist reply came back empty at its 350-token cap. | `get_news` raises on an empty result; the final run uses the committed snapshot; the specialists get 1500 tokens in `notebook.ipynb`. |
| 10-12 | The first final run crashed in section 1: the chain's summary returned no text at its 500-token cap (twice in about 280 calls; 0 of 60 identical retests). | `chat()` resends once on an empty reply at the cap. The rerun is the final run. |

## 4. Areas to build on

- **Route a failed criterion to its specialist:** send "no earnings figure" to the Earnings Specialist before the Writer revises.
- **Replan after a failure,** instead of logging it and moving on.
- **Persistent memory with pruning,** so the Writer's prompt does not grow without bound.
- **More data sources:** SEC EDGAR or FRED, each one cached function, one `STEPS` line, and one `MENU` entry.
- **Evaluate the evaluator and widen the test:** grade a sample of notes by hand to measure the Critic's agreement, and run many symbols to test memory beyond two.

## Appendix: data shapes

| Function | Lane | Returns |
|---|---|---|
| `run_chain(symbol)` | 1 | `{"articles": [{"title", "summary", "sentiment", "topic", "entities"}], "summary": str}` |
| `route_and_analyze(symbol, items)` | 2 | `[{"item", "route", "analysis"}]` |
| `evaluate(text, criteria)` | 3 | `{"score": 1-10, "pass": bool, "feedback": list[str]}` |
| `evaluator_optimizer(generate, criteria, max_rounds=2)` | 3 | `{"final": str, "history": [{"round", "score", "pass", "feedback"}]}` |
| `ResearchAgent.plan(symbol)` | 4 | `[{"tool", "args", "why"}]`, at most 8 |
| `ResearchAgent.run(symbol)` | 4 | `{"symbol", "plan", "log", "results", "criteria", "report", "history"}` |
| `ResearchAgent.reflect(symbol, run_result)` | 4 | `{"score", "lesson"}` |
| `ResearchAgent.remember(lesson)` | 4 | nothing; updates `self.lessons` |
