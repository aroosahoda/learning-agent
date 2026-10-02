# Learning Agent

Local-first agentic AI tutor. Design: `docs/architecture.md`. Roadmap phase: **1 - Foundation** (this repo state).

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                                   # all green before you touch anything
python -m modules.cli init && python -m modules.cli start "My topic" && python -m modules.cli validate
```

Read next: `docs/PHASE1_PLAN.md` (what/who/when) and `docs/COLLABORATION.md` (how we work).
