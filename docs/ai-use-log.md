# AI-use log

Course policy requires disclosure of generative-AI use: the tool, what it produced, and what we verified or changed. One entry per piece of work.

| Date | Who | Tool | What it did | What we verified or changed |
|---|---|---|---|---|
| 2026-09-19 | Ian Schmitt | Claude Code (Anthropic, Claude Fable 5.1) | Drafted `src/llm.py` and `src/tools.py` from the handoff contract; drafted README and planning docs | Ran both modules live against a local model and Yahoo Finance; read every line; cache contents inspected |
| 2026-10-02 | Jackson Kenyon| GitHub Copilot in VS Code | Implemented the staged news-processing chain in `dev/chain.ipynb`, including classification, entity extraction, and a one-paragraph summary from labeled articles; diagnosed and fixed the summary response truncation | `run_chain` returns a JSON-compatible dict; notebook syntax and project metadata validated; demo cell subsequently ran successfully and returned a dict |
