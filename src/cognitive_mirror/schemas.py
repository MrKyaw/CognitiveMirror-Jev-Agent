"""Versioned JSON Schemas for every tool (MCP-007).

    python -m cognitive_mirror.schemas --write   regenerate src/cognitive_mirror/schemas/v1
    python -m cognitive_mirror.schemas --check   exit 1 if committed schemas drifted
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cognitive_mirror import SCHEMA_VERSION
from cognitive_mirror.catalog import TOOLS
from cognitive_mirror.models import Envelope, ErrorEnvelope

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas" / "v1"


def tool_schema(name: str) -> dict[str, Any]:
    spec = TOOLS[name]
    return {
        "$id": f"https://cognitive-mirror.dev/schemas/v1/{name}.json",
        "name": name,
        "title": spec.title,
        "description": spec.description,
        "tool_version": spec.version,
        "schema_version": SCHEMA_VERSION,
        "kind": spec.kind,
        "read_only": spec.read_only,
        "sensitive": spec.sensitive,
        "roles": sorted(spec.roles),
        "input": spec.input_model.model_json_schema(),
        "output": spec.output_model.model_json_schema(),
    }


def all_schemas() -> dict[str, dict[str, Any]]:
    out = {name: tool_schema(name) for name in TOOLS}
    out["_envelope"] = {"schema_version": SCHEMA_VERSION,
                        "success": Envelope.model_json_schema(),
                        "error": ErrorEnvelope.model_json_schema()}
    return out


def _dump(obj: dict[str, Any]) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def write(directory: Path = SCHEMA_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, schema in all_schemas().items():
        path = directory / f"{name.lstrip('_')}.json"
        path.write_text(_dump(schema))
        written.append(path)
    return written


def drift(directory: Path = SCHEMA_DIR) -> list[str]:
    """Names whose committed schema file differs from the models."""
    bad = []
    for name, schema in all_schemas().items():
        path = directory / f"{name.lstrip('_')}.json"
        if not path.exists() or path.read_text() != _dump(schema):
            bad.append(name)
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        for path in write():
            print(path)
        return 0
    bad = drift()
    print("schemas up to date" if not bad else f"schema drift: {', '.join(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
