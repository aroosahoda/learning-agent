"""Agent states (architecture 3.1). Transition rules arrive in Phase 2.1."""

from enum import StrEnum


class State(StrEnum):
    GREET = "GREET"
    PROBE = "PROBE"
    PLAN = "PLAN"
    TEACH = "TEACH"
    QUIZ = "QUIZ"
    ANALYZE = "ANALYZE"
    REMEDIATE = "REMEDIATE"
    SRS_REVIEW = "SRS_REVIEW"
    WRAP = "WRAP"
