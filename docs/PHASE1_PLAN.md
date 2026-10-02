# Phase 1 - Foundation: detailed plan

Stack assumption (confirm together on Day 1, then record as ADR-001): **Python 3.11+**, `jsonschema`, `filelock`, `pytest`.
The starter code in this repo already implements a first version of every Phase 1 task. Phase 1 is therefore
**review -> harden -> extend -> prove**, not "write from zero". Each item below says what "done" means.

## Task cards

### 1.1 Repository & module structure  (Owner: Dev B, Reviewer: Dev A)
- Deliverables: layout from architecture section 12 (`modules/ schemas/ skills/ adapters/ hooks/ tests/ docs/`), `pyproject.toml`, `.gitignore`, CI, PR template, CODEOWNERS.
- Done when: fresh clone -> `pip install -e ".[dev]" && pytest` is green on Linux AND Windows CI.
- Risks: `.alvar/` (personal learning data) committed by accident -> it is git-ignored; add a CI step that fails if any `.alvar/` path is tracked.

### 1.2 `.alvar/` state & folder structure  (Owner: Dev A, Reviewer: Dev B)
- Deliverables: `modules/state/paths.py` - `AlvarPaths.init()` (idempotent), safe path builders, session-id and topic slug rules.
- Done when: init twice never destroys data; every path helper provably stays inside `.alvar/`; dirs are `0700`, files `0600` (POSIX).
- Risks: path traversal via topic/session id; symlinked `.alvar` or subfolder redirecting writes; permissions on shared machines.

### 1.3 JSON schemas  (Owner: Dev B, Reviewer: Dev A)
- Deliverables: `schemas/` - `event`, `answer_record`, `node_contract`, `verdict`, `fsrs_card`, `review_queue`; loader with cross-schema `$ref`.
- Done when: each schema has one valid and >= 3 invalid test cases; state enum in schema == `State` enum in code (drift test exists).
- Encoded invariants: `confirmed` verdict needs >= 2 citations; node contract must have both recall and application items; URLs must be http(s); `additionalProperties: false` everywhere.
- Risks: schema drift from architecture (see "Decisions to record"); over-strict schemas blocking legitimate data later -> any change goes through ADR + both approvals.

### 1.4 Configuration management  (Owner: Dev B, Reviewer: Dev A)
- Deliverables: `config.toml` + `modules/config.py` - typed, frozen, validated; unknown keys/sections rejected; size-capped.
- Done when: every numeric has bounds; allowlist accepts bare hostnames only; missing file -> defaults, bad file -> error (never silently ignored).
- Risks: typos silently ignored (handled), secrets in config (documented: none allowed), config bounds disagreeing with the event-log window (`max_event_bytes` <= 64 KiB is enforced).

### 1.5 Event logging & state persistence  (Owner: Dev A, Reviewer: Dev B)
- Deliverables: `modules/state/atomic.py` (atomic write + cross-platform lock), `modules/state/events.py` (append-only JSONL, schema-validated, monotonic `seq`).
- Done when: 4 concurrent processes x 15 appends -> exactly seq 1..61 no gaps/dupes; torn final line is quarantined to `.torn`; mid-file corruption is reported, never skipped.
- Risks: crash mid-write, concurrent writers, log-injection through newlines in values (JSON escaping), oversized events, silent data loss.

### 1.6 Session init/resume  (Owner: Dev A, Reviewer: Dev B)
- Deliverables: `modules/state/session.py` (`start`, `resume`, `find_resumable`, `end`; state derived by pure `replay()`), `modules/cli.py` (`init/start/resume/validate`).
- Done when: kill -9 during a session then `resume` restores the last state; ended sessions cannot be resumed or written to; `validate` exits non-zero on any problem (CI uses it).
- Risks: writing on top of a corrupt log (handled: full strict read before every write), stale handle writing after another process ended the session (handled), frontmatter injection via topic (handled by JSON-quoting).

## Vulnerability & failure checklist (both reviewers use this on every PR)

| # | Threat / failure | Where | Mitigation in starter | Proving test |
|---|---|---|---|---|
| 1 | Path traversal (`../../x`) | session ids, topics | regex-validated ids, slugify, resolve()+is_relative_to | `test_paths.py` |
| 2 | Symlink redirect of `.alvar/` | `_safe`, `init` | refuse symlinked root/components | `test_symlinked_*` |
| 3 | Crash mid-write | events, files | tmp+fsync+`os.replace`; torn-tail quarantine | `test_torn_tail_*` |
| 4 | Concurrent writers | event log | file lock + seq computed under lock | `test_concurrent_writers_*` |
| 5 | Log/record injection | event values | `json.dumps` escaping; schema `additionalProperties:false` | `test_newlines_*` |
| 6 | Unbounded input | events, config | max_event_bytes, maxLength on strings, 64 KiB config cap | `test_oversized_*` |
| 7 | Silent config typos | config | unknown keys rejected | `test_invalid_configs_rejected` |
| 8 | Writing over corruption | Session | full strict read before each write | `test_session_refuses_*` |
| 9 | Personal data leaks to git | repo | `.alvar/` git-ignored | (add CI check - task 1.1) |
| 10 | Vulnerable dependencies | deps | pinned ranges, `pip-audit` in CI | CI `audit` job |
| 11 | Unsafe YAML parsing (Phase 2+) | node contracts | NOT introduced yet; rule: `yaml.safe_load` only | (future) |
| 12 | Prompt injection via fetched pages (Phase 6) | research | out of scope now; log content is data, never instructions | (future) |

Commands that must stay green: `ruff check . && ruff format --check . && mypy && bandit -q -r modules && pytest && python -m modules.cli validate`

## Task split (two people)

Principle: **split by module ownership, cross-review by role swap.** Dev A owns "state at runtime" (1.2, 1.5, 1.6).
Dev B owns "contracts & quality gates" (1.1, 1.3, 1.4). The **schemas are the interface** between the two halves,
so nobody blocks anybody: Dev A codes against `schemas/event.schema.json`, Dev B changes it only via PR + ADR.

| | Dev A (state & runtime) | Dev B (contracts & quality) |
|---|---|---|
| Own | 1.2, 1.5, 1.6, CLI | 1.1, 1.3, 1.4, CI |
| Also | red-team review of schemas + config | red-team review of event log + sessions |
| Extra hardening tasks | (a) session-level lock so 2 processes can't drive one session; (b) log-size/rotation note; (c) crash test with `kill -9` | (a) CI check that no `.alvar/` is tracked; (b) property-based tests (hypothesis) for schemas; (c) verify Windows CI is green |

## Timeline (~7 working days; adjust to your college schedule)

| Day | Together | Dev A | Dev B |
|---|---|---|---|
| 1 | 60-min kickoff: read architecture sections 1-3, 11; agree stack + ADR-001; create repo, branch protection, issues 1.1-1.6 | env setup, run starter, read `state/` | env setup, run starter, read `schemas/` + `config` |
| 2 | 20-min sync | 1.2 hardening + tests | 1.3 schema review vs architecture, list deviations |
| 3 | | 1.5 extra tests (crash, kill -9) | 1.4 tests + allowlist rules; CI green on Windows |
| 4 | 20-min sync; **swap-review day 1** | review Dev B PRs with checklist | review Dev A PRs with checklist |
| 5 | | 1.6 session lock (extra a) | property-based schema tests, `.alvar` CI guard |
| 6 | **swap-review day 2**; fix all findings | | |
| 7 | Phase 1 demo (below) + retro (30 min) + write Phase 2 task cards | | |

**Phase 1 exit demo (definition of done for the whole phase):**
1. Fresh clone on both machines, CI green on Linux + Windows.
2. `init -> start -> (kill process) -> resume -> validate` works live.
3. Corrupt a log by hand -> `validate` fails with the exact line; torn tail is repaired on next append.
4. Every checklist row above has a passing test or a written reason it is deferred.

## Decisions to record as ADRs (starter deviates from / interprets the architecture)
1. **Event envelope**: added `session` and `seq` to every event (architecture examples have neither) - needed for ordering, resume, corruption detection.
2. **Confidence**: modelled as `high | low` (matches the 2x2 matrix in 9.3). Do we want a 3-level scale?
3. **`claim_verified` event** stores citation URLs only; the full `verdict` schema holds quotes. OK?
4. **`confirmed` requires >= 2 citations** at schema level (architecture 6.3). Stricter than the prose - intentional.
5. **Language**: Python. Alternative: TypeScript (ts-fsrs exists). Decide before Phase 5.
6. **Node contracts** are YAML in the architecture; schemas validate the parsed object. YAML library + `safe_load` rule decided in Phase 2/3.
7. **Threat model**: accidental damage and buggy agents, not a hostile local user (no tamper-proof hash chain). Revisit in Phase 8/9.

## Known limitations of the starter (be honest in the demo)
- Not run on Windows locally yet - CI matrix is the check. `fsync` of directories and file modes are POSIX-only behaviours.
- `Session` re-reads the whole log on every write: fine for thousands of events, revisit in Phase 9.
- `record_transition` accepts any state; the validated transition table is Phase 2.1.
- No session-level lock: two processes can both drive one session (extra task A-a).
