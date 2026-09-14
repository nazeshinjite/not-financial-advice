# Not Financial Advice: An Autonomous Investment Research Agent

An agentic AI system that researches a stock: given a ticker symbol, it plans its own research steps, pulls prices, fundamentals, and news through tools, writes an analysis, evaluates and refines that analysis, and carries notes forward to improve the next run.

This project is part of the **AAI-520: Natural Language Processing and GenAI** course in the Applied Artificial Intelligence program at the **University of San Diego (USD)**.

**Project status:** Planned (Fall 2026; final deliverable due Oct 19, 2026)

## Objective

Investment research is a reading problem before it is a numbers problem. Analysts read filings, earnings summaries, and a stream of news, then decide what matters and how it fits together. This project builds a small version of that process as an autonomous agent backed by an LLM, and uses it to demonstrate the difference between two ways of structuring LLM systems:

1. **Workflows**, where the sequence of LLM calls is fixed in code. We implement three: prompt chaining (ingest news, preprocess, classify, extract, summarize), routing (send each item to an earnings, news, or market specialist), and evaluator-optimizer (generate an analysis, score it, refine it from the feedback).
2. **An agent**, where the LLM directs its own process. Our Investment Research Agent plans its research for a symbol, calls tools dynamically, reflects on the quality of its own output, and keeps memory across runs.

The workflows are built and demonstrated standalone first, then reused inside the agent. The deliverable is a notebook that shows every behavior running, with the explanations and visualizations a reader needs to follow what happened and why.

## Contributors

AAI 520 Group 1:

- **Ali Abdul-Hameed**
- **Ian Schmitt**
- **Jackson Kenyon**
- **Nina Zhao**

Lane assignments and the contribution log are recorded in [`docs/contributions.md`](docs/contributions.md).

## Methods Used

- Natural Language Processing (text preprocessing, named-entity extraction, sentiment classification)
- Generative AI and prompt engineering (structured JSON prompts, rubric-in-prompt evaluation)
- Agentic AI (planning, tool use, self-reflection, memory across runs)
- LLM workflow patterns (prompt chaining, routing, evaluator-optimizer)
- Data visualization

## Technologies

- **Python 3.12**, managed with **[uv](https://docs.astral.sh/uv/)** (pinned dependencies, committed lockfile)
- **`openai`** Python SDK against any OpenAI-compatible endpoint (cloud or local), selected by environment variables
- **`yfinance`** for prices, fundamentals, and news
- **spaCy / NLTK** for preprocessing and entity extraction
- **pandas** and **matplotlib** for tables and figures
- **Jupyter** for the deliverable notebook; **ruff** for PEP 8

## Project Description

### Data

All market data comes from Yahoo Finance through the `yfinance` package: daily price history, company fundamentals (`Ticker.info` and financial statements), and recent news headlines with summaries. Every tool response is cached as JSON under `data/cache/` and committed, so the notebook reruns offline, results are reproducible, and API rate limits never interrupt a demonstration. The demonstration uses two symbols: one run twice to show memory at work, and one run once.

### Questions we are exploring

- Can a fixed workflow of small, checkable LLM steps turn a batch of raw headlines into labeled, structured, summarized evidence reliably?
- Does routing to specialists with narrower prompts and dedicated data produce better analysis than one general prompt?
- Does an evaluator loop measurably improve a generated analysis, and how many rounds are worth running?
- When the agent keeps notes between runs, does the next run's plan or first-pass quality actually change?

### How the work is organized

Each rubric requirement maps to one component, and each component has its own section of the notebook.

| Requirement | Component | Demonstrated by |
|---|---|---|
| Prompt chaining | `src/chain.py` | Per-article labels table; sentiment chart |
| Routing | `src/route.py` | Routing-decision table for a mixed batch |
| Evaluator-optimizer | `src/evaluate.py` | Score per iteration plot; before/after excerpt |
| Agent plans | `src/agent.py` | The printed plan for a symbol |
| Agent uses tools dynamically | `src/agent.py` + `src/tools.py` | Tool-call log per run |
| Agent self-reflects | `src/evaluate.py` + reflection note | Reflection output on the final report |
| Agent learns across runs | `memory/memory.json` | Two runs on one symbol; memory diff and the changed plan |

### Repository structure

```
not-financial-advice/
├── notebook.ipynb     # the deliverable; sections mirror the table above
├── src/               # llm.py, tools.py, chain.py, route.py, evaluate.py, agent.py
├── data/cache/        # committed JSON responses from yfinance
├── memory/            # memory.json, the agent's notes across runs
├── docs/              # contribution log, AI-use disclosure
├── setup.md           # environment and run instructions
├── pyproject.toml     # uv-managed dependencies
└── README.md          # this file
```

### Roadblocks / challenges

Getting reliable structured (JSON) output from the LLM, since the classifier, router, evaluator, and planner all depend on it. Making "learns across runs" visibly true rather than a file that gets written and never read. Schema drift and rate limits in `yfinance`, handled by the cache. Keeping every LLM loop bounded so nothing can run away. Exporting a long notebook to a PDF that is still readable.

## Installation

Full instructions in [`setup.md`](setup.md). The short version:

```bash
git clone https://github.com/nazeshinjite/not-financial-advice.git
cd not-financial-advice
uv sync                      # creates .venv and installs pinned dependencies
cp .env.example .env         # then fill in LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
uv run jupyter lab           # open notebook.ipynb
```

The notebook runs from the committed cache without network access. A live LLM endpoint is required; any OpenAI-compatible server works.

## Scope fence (explicitly not doing)

No agent framework (the agent loop is plain Python, as in the course lab). No retrieval-augmented generation or vector store. No data sources beyond Yahoo Finance. No multi-symbol portfolios, forecasting, backtesting, or trading recommendations. No user interface. The output is research, not investment advice.

## Integrity and AI-use disclosure

This course permits AI-assisted tools with disclosure. The running log in [`docs/ai-use-log.md`](docs/ai-use-log.md) records which tools were used, for what, and what was verified or changed afterward, so the notebook's disclosure is accurate. Every team member must understand and be able to defend every part of the submission.

## License

Released under the [MIT License](LICENSE).

## Acknowledgments

Prof. Andrew Van Benschoten, Ph.D. (AAI-520 instructor); Anthropic's *Building Effective Agents*, whose workflow vocabulary this project follows; and the maintainers of `yfinance` and the open-source Python ecosystem.
