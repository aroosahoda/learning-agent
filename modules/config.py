"""Configuration loading with strict validation (Phase 1.4)."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

MAX_CONFIG_BYTES = 64 * 1024
_HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class MasteryConfig:
    pass_threshold: float = 0.85


@dataclass(frozen=True)
class ProbeConfig:
    min_questions_per_strand: int = 2
    max_questions_per_strand: int = 4


@dataclass(frozen=True)
class FsrsConfig:
    desired_retention: float = 0.90
    maximum_interval_days: int = 365


@dataclass(frozen=True)
class ResearchConfig:
    min_independent_sources: int = 2
    source_allowlist: tuple[str, ...] = ()
    ttl_days_time_sensitive: int = 7
    ttl_days_default: int = 90


@dataclass(frozen=True)
class LoggingConfig:
    max_event_bytes: int = 16384


@dataclass(frozen=True)
class Config:
    mastery: MasteryConfig = field(default_factory=MasteryConfig)
    probe: ProbeConfig = field(default_factory=ProbeConfig)
    fsrs: FsrsConfig = field(default_factory=FsrsConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


_SECTIONS: dict[str, type] = {f.name: f.type for f in fields(Config)}  # type: ignore[misc]


def _int(section: str, key: str, v: Any, lo: int, hi: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ConfigError(f"[{section}] {key} must be an integer in [{lo}, {hi}], got {v!r}")
    return v


def _float(section: str, key: str, v: Any, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo < v <= hi:
        raise ConfigError(f"[{section}] {key} must be a number in ({lo}, {hi}], got {v!r}")
    return float(v)


def _build(section: str, cls: type, raw: dict[str, Any]) -> Any:
    known = {f.name for f in fields(cls)}
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"[{section}] unknown key(s): {sorted(unknown)}")
    return cls(**raw)


def parse_config(data: dict[str, Any]) -> Config:
    unknown = set(data) - set(_SECTIONS)
    if unknown:
        raise ConfigError(f"unknown section(s): {sorted(unknown)}")
    r = data.get("research", {})
    allow = r.get("source_allowlist", [])
    if not isinstance(allow, list) or not all(isinstance(h, str) for h in allow):
        raise ConfigError("[research] source_allowlist must be a list of hostnames")
    for h in allow:
        if not _HOST_RE.fullmatch(h):
            raise ConfigError(
                f"[research] source_allowlist entry {h!r} must be a bare lowercase hostname (no scheme/path/port)"
            )
    r = {**r, "source_allowlist": tuple(allow)}
    m, p, f, lg = (data.get(k, {}) for k in ("mastery", "probe", "fsrs", "logging"))
    cfg = Config(
        mastery=_build("mastery", MasteryConfig, m),
        probe=_build("probe", ProbeConfig, p),
        fsrs=_build("fsrs", FsrsConfig, f),
        research=_build("research", ResearchConfig, r),
        logging=_build("logging", LoggingConfig, lg),
    )
    _float("mastery", "pass_threshold", cfg.mastery.pass_threshold, 0.5, 1.0)
    lo = _int("probe", "min_questions_per_strand", cfg.probe.min_questions_per_strand, 1, 20)
    hi = _int("probe", "max_questions_per_strand", cfg.probe.max_questions_per_strand, 1, 20)
    if lo > hi:
        raise ConfigError("[probe] min_questions_per_strand must be <= max_questions_per_strand")
    _float("fsrs", "desired_retention", cfg.fsrs.desired_retention, 0.7, 0.99)
    _int("fsrs", "maximum_interval_days", cfg.fsrs.maximum_interval_days, 1, 36500)
    _int("research", "min_independent_sources", cfg.research.min_independent_sources, 2, 10)  # verify needs >= 2
    _int("research", "ttl_days_time_sensitive", cfg.research.ttl_days_time_sensitive, 0, 3650)
    _int("research", "ttl_days_default", cfg.research.ttl_days_default, 1, 3650)
    _int("logging", "max_event_bytes", cfg.logging.max_event_bytes, 1024, 65536)  # tail-scan window is 64 KiB
    return cfg


def load_config(path: Path | str | None) -> Config:
    """Missing file -> defaults. Malformed/invalid file -> ConfigError (never silently ignored)."""
    if path is None or not Path(path).exists():
        return Config()
    p = Path(path)
    if p.stat().st_size > MAX_CONFIG_BYTES:
        raise ConfigError(f"{p} is larger than {MAX_CONFIG_BYTES} bytes")
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ConfigError(f"{p}: {e}") from e
    return parse_config(data)
