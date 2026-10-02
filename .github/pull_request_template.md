## What & why
<!-- 1-3 sentences. Link the task card (e.g. "Closes #4 - Task 1.5"). -->

## Checklist
- [ ] Tests added/updated; `pytest` passes locally
- [ ] `ruff check . && ruff format --check . && mypy && bandit -q -r modules` pass
- [ ] If a schema changed: `schemas/` updated, tests updated, ADR written, BOTH people approved
- [ ] Threat check: what could a bad input / crash / second process do to this code? (write 1 line)
- [ ] No secrets, no `.alvar/` data, no personal data committed
