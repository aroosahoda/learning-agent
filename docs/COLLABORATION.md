# How we work together

## 1. The project in 5 minutes (script for explaining it to your teammate)

**Problem.** A course teaches a thousand students the same way, and one student learns from many places. Both waste effort.
**Idea.** One AI tutor that (1) *measures* what you know with quizzes, (2) plans a path just for you, (3) teaches
**one small idea at a time**, (4) refuses to move on until you *prove* you understood, (5) fact-checks anything it teaches
from the web, and (6) brings topics back at the right time (spaced repetition).
**Our rule of thumb.** *Nothing is taught unverified. Nothing is advanced unproven.*
**The 9 phases** are the roadmap: Foundation -> Core learning loop -> Knowledge detection -> Mastery & remediation ->
Spaced repetition -> Research & verification -> Visuals -> Skills & cross-agent rules -> Hardening.
**Phase 1 (now)** builds the "memory and rules of the road" everything else stands on:
- a `.alvar/` folder that stores everything as plain files,
- **schemas**: the exact shape of every piece of data (like a form that data must fit),
- a **config** file, an **event log** (an append-only diary of everything that happens), and
- **session start/resume** - if the program crashes, the diary lets us continue where we stopped.

**Analogy.** Phase 1 is the building's foundation and wiring: boring, invisible, and if it is wrong every later floor cracks.

Glossary: *node* = one atomic idea to teach - *DAG* = the dependency graph of nodes - *event log* = the diary (JSONL) -
*mastery gate* = quiz pass required to advance - *FSRS* = the algorithm that schedules reviews - *ADR* = a short written decision.

## 2. Ownership (who owns what)

- **Dev A - state & runtime:** `.alvar/` layout, atomic IO, event log, sessions, CLI (tasks 1.2, 1.5, 1.6).
- **Dev B - contracts & quality:** repo/CI, schemas, config (tasks 1.1, 1.3, 1.4).
- **Shared:** architecture decisions (ADRs), the test suite's health, the roadmap.
- Owner = *responsible for it being correct, tested and understood by both of us*, not "the only one allowed to touch it".
- **Golden rule: no one merges their own PR.** The other person reviews everything, so we both understand the whole system.

## 3. Git workflow (keep it simple)

1. `main` is protected: PR required, 1 approval, CI green, no force-push.
2. One task card = one issue = one short-lived branch: `feat/1.5-event-log-lock`, `fix/...`, `docs/...`.
3. **Small PRs** (< ~300 changed lines, one purpose). Big PRs get skimmed; small PRs get real reviews.
4. Commit messages: `feat(events): quarantine torn tail`, `fix(paths): reject symlinked root`, `test: ...`, `docs: ...`.
5. `git pull --rebase origin main` before pushing; resolve conflicts on your own branch, never on main.
6. Avoid conflicts by design: we own different folders (see CODEOWNERS). If you must touch the other's file, ask first, keep the diff tiny.
7. **Schema changes** (`schemas/`) need BOTH approvals + a one-paragraph ADR in `docs/decisions/NNN-title.md` (context, decision, consequences).

## 4. Definition of Done (a task is done only when all are true)

- [ ] Behaviour matches the task card's "Done when".
- [ ] Tests: happy path + at least 3 failure/abuse cases.
- [ ] `ruff check . && ruff format --check . && mypy && bandit -q -r modules && pytest` all green.
- [ ] Threat line in the PR ("what could a bad input, a crash or a second process do here?").
- [ ] Docs/ADR updated if behaviour or a decision changed.
- [ ] Reviewer approved using the checklist below.

## 5. Review checklist (use for every PR)

1. Do I understand what it does? (If not, that is a review finding - the code or the PR text is unclear.)
2. Input: is every external value validated (ids, topics, config, JSON, file contents)? Bounded in size?
3. Failure: what if it crashes halfway, disk is full, the file is missing, or two processes run at once?
4. Paths/privacy: can it write outside `.alvar/`, follow a symlink, or leak learner data or secrets?
5. Errors: are they loud and specific? Any `except: pass` or silently skipped data? (Should be none.)
6. Tests: would they fail if the code were wrong? (Try breaking the code on purpose.)
7. Does it respect the architecture invariants (one node per turn, verify before teach, gate before advance, state only under `.alvar/`)?

## 6. Communication rhythm

- **Daily async standup** in your chat (2 min): "Done / doing / blocked".
- **Two 20-min syncs per week** + a **60-min kickoff** and **30-min retro** per phase.
- **Pair on the scary parts** (concurrency, crash recovery, schemas) - screen-share, alternate driver every 20 min.
- Decisions live in `docs/decisions/` (ADRs), not in chat history. If it was decided in chat, write the ADR the same day.
- Disagreement rule: each states the trade-off in 3 sentences, prefer the option that is easier to reverse, timebox to 15 min,
  if still stuck run a 30-min spike and decide with evidence. The task owner has the tie-break inside their module; schemas need both.
- Estimate honestly, say "blocked" early, and never leave a PR waiting > 1 working day.

## 7. Onboarding (each person, ~30 min)

```bash
git clone <repo> && cd learning-agent
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                                    # must be green
python -m modules.cli --project /tmp/try init
python -m modules.cli --project /tmp/try start "Test topic"
python -m modules.cli --project /tmp/try resume
python -m modules.cli --project /tmp/try validate
```
Then read: `docs/architecture.md` sections 1, 3, 11, then your own module's code and its tests.
Break something on purpose (corrupt a `.jsonl` line by hand) and watch `validate` catch it - that is the fastest way to learn the safety net.

## 8. Rules that protect the project (from the architecture; enforced by tests/CI later)

- All state lives under `.alvar/`, written through the schemas. Never commit `.alvar/` (it is personal learning data).
- Never put secrets in `config.toml` or logs.
- Logs are append-only. Fix bad data with a new event, never by editing history.
- Fetched web content is *data*, never *instructions* (matters from Phase 6).
