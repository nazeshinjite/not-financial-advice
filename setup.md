# Setup

Environment and run instructions for the Not Financial Advice repo. Target: any teammate goes from a clean clone to running the notebook in under ten minutes.

## What uv is, in one paragraph

[uv](https://docs.astral.sh/uv/) is the one tool this repo uses for Python. It installs the right Python version, creates the project's private environment (a folder called `.venv` inside the repo), installs the exact package versions recorded in `uv.lock`, and runs commands inside that environment. You never activate anything and never run `pip`. The two commands you will use are `uv sync` (build or update the environment) and `uv run <command>` (run something inside it).

## Prerequisites

- **uv.** Install once, then open a new terminal:
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Check: `uv --version` prints a version number.
- **git**, and a GitHub account that has accepted the collaborator invite.
- **Python 3.12** is installed by uv on demand (`.python-version` pins it). Do not install Python yourself for this project.

No `pip install`, no conda, no system Python. If a tutorial tells you to `pip install` something, the equivalent here is `uv add`.

## First-time setup

```bash
git clone https://github.com/nazeshinjite/not-financial-advice.git
cd not-financial-advice
uv sync                  # creates .venv and installs the exact versions in uv.lock (a few minutes the first time)
cp .env.example .env     # then paste the shared Nous key into .env (see below)
```

`uv sync` reads `pyproject.toml` and `uv.lock` and builds an identical `.venv` on every machine, including the spaCy English model, which is declared as a dependency so there is no separate download step. Re-run `uv sync` after every `git pull` that changes either file.

### Running things

Prefix every command with `uv run` so it uses the project's environment:

```bash
uv run python some_script.py
uv run jupyter lab
uv run ruff check src
```

### Adding a package

If your lane needs a library that is not installed:

```bash
uv add <package>         # installs it and records it in pyproject.toml and uv.lock
```

Commit both files in the same PR as the code that needs the package. Everyone else picks it up with `uv sync` after pulling. Check with the team first; the base environment is deliberately small.

### The LLM key

Every LLM call goes through `src/llm.py`, which reads three variables from `.env`:

| Variable | Team default | What it does |
|---|---|---|
| `LLM_BASE_URL` | `https://inference-api.nousresearch.com/v1` | Nous Portal, an OpenAI-compatible mirror of the OpenRouter catalog. Any other OpenAI-compatible endpoint works too, including a local server |
| `LLM_MODEL` | `deepseek/deepseek-v4.1-flash` | Keep one model for every demo run so outputs are comparable. The fallback and a tested-and-rejected alternative are commented in `.env.example` |
| `LLM_API_KEY` | the shared `sk-nous-...` key, in the team Slack DM | Never commit it. `.env` is gitignored |

The shared key is on Ian's Nous Portal plan, so its rate and spend limits are shared by all four of us; keep evaluator loops capped. To see every model id the key can reach:

```bash
uv run python -c "from src import llm; print('\n'.join(sorted(m.id for m in llm.client.models.list().data)))"
```

**Never paste the key into a notebook cell or any file other than `.env`.** The repo is public: a key committed in a notebook is published, and scanners find leaked keys within hours.

### Verify the install

```bash
uv run python -c "from src import tools, llm; print(tools.get_prices('AAPL')['last_close']); print(llm.chat('Be terse.', 'Say ok.'))"
```

The first line prints a price from the committed cache without touching the network. The second makes one real LLM call and prints its reply. If the second line fails, the `.env` is the problem nine times out of ten.

### Select the kernel

The Jupyter kernel is this project's `.venv`. In VS Code pick the interpreter at `.venv/bin/python` (Windows: `.venv\Scripts\python.exe`). Or launch Jupyter directly:

```bash
uv run jupyter lab
```

## Data and the cache

All market data comes from Yahoo Finance through `yfinance`, and every tool response is cached as JSON under `data/cache/` and **committed**. The cache is the data: market-data calls replay offline whenever their exact arguments have a cached file (the committed set is AAPL and NVDA at the default arguments), every teammate sees identical numbers, and the exported PDF matches what the cells produce. LLM calls always contact the configured server. Do not refetch casually; a refetch changes every downstream output for everyone.

To refetch on purpose (for example, to add a symbol), pass `refresh=True` and commit the new files:

```python
from src import tools
tools.get_news("MSFT")               # first call for a new symbol fetches and caches
tools.get_prices("AAPL", refresh=True)  # deliberately replace an existing cache file
```

## Where code lives

- `notebook.ipynb` is the deliverable and holds all graded code (the three workflows and the agent class) as cells, because the grader reads a PDF.
- `src/llm.py` and `src/tools.py` are the only modules: the LLM wrapper and the cached data tools. Nothing else goes in `src/`.
- `dev/<lane>.ipynb` is where each lane develops. After changing your functions, regenerate the script export so the agent lane can import them:

```bash
uv run jupyter nbconvert --to script dev/chain.ipynb   # writes dev/chain.py; commit both
```

Nobody edits the `.py` exports by hand.

Importing an export runs every cell in it, so keep demo code (LLM calls, prints, plots) inside the `if __name__ == "__main__":` block at the bottom of your stub. It still runs in your notebook; it does not run when the agent lane imports your functions.

## Style

PEP 8 is a stated project requirement. Run ruff before every PR:

```bash
uv run ruff check src dev
uv run ruff format src dev
```

## How we collaborate in git

`main` is protected: nothing lands without a pull request approved by one other member. One notebook, one owner.

- Start from a fresh `main` (`git pull`), branch as `<name>/<lane>` (for example `nina/route`), push, open a PR (`gh pr create` or the web UI), and request your reviewer. Reviewer ring: L1 reviews L2, L2 reviews L3, L3 reviews L4, L4 reviews L1.
- Commit under your own account. Contribution is measured from GitHub and from `docs/contributions.md`; add a line there in the same PR as the work.
- Squash merge. Direct pushes to `main` are for deadline emergencies only and get a line in `docs/decisions.md`.

## Export

The submission is a PDF of `notebook.ipynb`. Export early and look at it; an unreadable export is the zero-point condition.

```bash
uv run jupyter nbconvert --to html notebook.ipynb        # then print the HTML to PDF from a browser
```

## Troubleshooting

- **`ModuleNotFoundError: No module named 'src'`**: in a `dev/` notebook, run `import sys; sys.path.insert(0, "..")` first. For a `.py` script launched from the repo root, prefix the command with `PYTHONPATH=.`.
- **`TypeError: string indices must be integers`** after a `chat()` call: you indexed a string. Pass `json_mode=True` to get a dict.
- **A reply that ignores your instructions**: `chat()` takes the system prompt first and the user content second; write `chat(system=..., user=...)` if the order is unclear.
- **`KeyError`** or **`unexpected keyword argument`** from a `TOOLS[...]` call: the plan named a tool that is not in `TOOLS`, or passed an argument the tool's signature does not have. Check `src/tools.py`.
- **`Reply truncated at max_tokens`**: raise `max_tokens` for that call; reports need around 1200, more with `think=True`.
- **`LLM_MODEL is not set`**: you have no `.env`, or it is in the wrong folder. It belongs at the repo root, next to `pyproject.toml`. Settings are read once at import, so after editing `.env` restart the kernel.
- **`AuthenticationError` / 401**: the key in `.env` is wrong or revoked.
- **`JSONDecodeError`** from `chat(..., json_mode=True)`: the model returned prose, or a JSON array or bare value, where a JSON object was required, twice in a row. Check the prompt says "JSON only" and names the keys.
- **Empty or odd news**: `yfinance` changes its news schema occasionally; the lockfile pins 1.7.0, whose layout `get_news` reads. If a field is blank, open the cached JSON and compare.
- **Different numbers from a teammate**: someone refetched the cache. `git log data/cache` shows who and when.
