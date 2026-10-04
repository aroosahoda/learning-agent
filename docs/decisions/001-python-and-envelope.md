# ADR-001: Python Technology Stack and Event Envelope Architecture

- **Status:** accepted
- **Date:** 2026-10-04
- **Context:** The `learning-agent` runtime requires a standardized development stack, strict static type checks, and a resilient, offline local audit log mechanism without external database dependencies. We must establish clear standards for event validation, confidence categorization, citation enforcement, and cross-platform file append reliability.
- **Options considered:**
  - Standard Python 3.11+ stack with local `.jsonl` append-only logs and strict static typing.
  - Relational database (SQLite / PostgreSQL) with ORM models for state persistence.
  - Node.js runtime with plain JSON state files.
- **Decision:** We agree on the following 7 core decisions and implementation standards:
  1. **Technology Stack Selection:** Standardize on Python 3.11+ using standard library primitives, strict static typing (`mypy`), and developer tooling (`pytest`, `ruff`, `bandit`).
  2. **Local Event Log File Structure:** Store immutable event logs locally using JSON Lines (`.jsonl`) under `.alvar/events/`. Organize files per-session (e.g., `.alvar/events/.jsonl`) to prevent single monolithic files over long-term usage.
  3. **Event Envelope Standards:** Require all disk writes to contain standard header fields (`session_id`, sequence number `seq`, `event_id`, `timestamp`, `event_type`, `payload`, `metadata`). Timestamps must strictly enforce ISO 8601 UTC standards (`datetime.now(timezone.utc).isoformat()`) to prevent timezone skew across cross-platform environments.
  4. **Confidence Level Classification:** Standardize evaluation confidence levels strictly to `high` or `low` across all execution and scoring metrics.
  5. **Strict Verdict Citation Enforcement:** Require a minimum of two distinct, independent citations embedded in the payload before confirming any system verdict on learning outputs.
  6. **Threat Model Boundaries:** Focus security controls on system reliability, local file safety, and software bugs (path traversal, atomic write crashes, log corruption), explicitly excluding hostile multi-tenant local user threats.
  7. **Storage & Append Constraints:** Treat log files as append-only records with zero external database dependencies. Open files using `open(..., "a", encoding="utf-8")`, ensure all lines are newline-terminated (`\n`), and perform explicit flushes (`f.flush()`) or file-locking mechanisms to prevent torn/corrupted writes on Windows and POSIX systems during crashes or concurrent runs.
- **Consequences:** 
  - *Easier:* Fast offline execution, zero database setup, cross-platform timezone consistency, and strict linting/typing guarantees on every commit.
  - *Harder:* Requires schema envelope checks on every disk read and explicit handling of atomic writes, flushes, and per-session file rotation.
  - *Must be revisited:* File-locking overhead or archive strategies if session event counts grow excessively large in future phases.
