"""Load and apply the JSON schemas in /schemas (Phase 1.3)."""

from __future__ import annotations

import json
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


class SchemaError(ValueError):
    """Raised when data does not conform to a schema."""


@lru_cache(maxsize=1)
def _registry() -> Registry:
    resources = []
    for p in sorted(SCHEMA_DIR.glob("*.schema.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        resources.append((s["$id"], Resource.from_contents(s, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


@cache
def _validator(name: str) -> Draft202012Validator:
    path = SCHEMA_DIR / f"{name}.schema.json"
    if not path.is_file():
        raise SchemaError(f"unknown schema: {name!r}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=_registry())


def schema_names() -> list[str]:
    return sorted(p.name.removesuffix(".schema.json") for p in SCHEMA_DIR.glob("*.schema.json"))


def validate(name: str, instance: Any) -> None:
    errors = sorted(_validator(name).iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        msg = "; ".join(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}" for e in errors[:5])
        raise SchemaError(f"{name} schema violation: {msg}")
