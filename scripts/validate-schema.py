#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate all locale JSON files against locales.schema.json.

Usage:
    python3 scripts/validate-schema.py
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

META_REQUIRED_FIELDS = ["locale", "name", "english_name", "is_rtl"]


def locale_paths(root: Path) -> list[Path]:
    """Every locale file under `root`, excluding the schema itself."""
    return sorted(p for p in root.glob("*.json") if p.name != "locales.schema.json")


def schema_errors(
    locale_files: list[Path], schema: dict
) -> tuple[list[str], list[str]]:
    """Validate with jsonschema. Returns (errors, summaries)."""
    if jsonschema is None:
        raise RuntimeError("jsonschema is not installed")

    errors, summaries = [], []
    for path in locale_files:
        code = path.stem
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            jsonschema.validate(instance=data, schema=schema)
            summaries.append(f"  {code}.json: OK ({len(data)} keys)")
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")
        except jsonschema.ValidationError as e:
            field = (
                ".".join(str(p) for p in e.absolute_path)
                if e.absolute_path
                else "(root)"
            )
            errors.append(f"{code}.json: {field} — {e.message}")

    return errors, summaries


def basic_errors(
    locale_files: list[Path], schema: dict
) -> tuple[list[str], list[str]]:
    """Validate without jsonschema. Returns (errors, summaries).

    CI installs jsonschema best-effort, so this path is reachable in a
    real pipeline rather than only on a developer machine.
    """
    required_keys = set(schema.get("required", []))
    errors, summaries = [], []

    for path in locale_files:
        code = path.stem
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            actual_keys = set(data.keys())
            missing = required_keys - actual_keys
            if missing:
                errors.append(f"{code}.json: Missing {len(missing)} required keys")
                for k in sorted(missing)[:5]:
                    errors.append(f"  - {k}")
                if len(missing) > 5:
                    errors.append(f"  ... and {len(missing) - 5} more")

            meta = data.get("_meta")
            if meta is not None:
                if not isinstance(meta, dict):
                    errors.append(f"{code}.json: _meta must be an object")
                else:
                    for field in META_REQUIRED_FIELDS:
                        if field not in meta:
                            errors.append(f"{code}.json: _meta.{field} is required")

            for key, value in data.items():
                if key == "_meta":
                    continue
                if not isinstance(value, str):
                    errors.append(
                        f"{code}.json: '{key}' must be a string, "
                        f"got {type(value).__name__}"
                    )
                elif len(value) == 0:
                    errors.append(f"{code}.json: '{key}' must not be empty")

            summaries.append(f"  {code}.json: OK ({len(data)} keys)")
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")

    return errors, summaries


def report(
    errors: list[str], summaries: list[str], failure_label: str, success: str
) -> int:
    for line in summaries:
        print(line)

    if errors:
        print(f"\n{failure_label} FAILED ({len(errors)} error(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"\nPASSED: {success}")
    return 0


def main() -> int:
    repo_root = Path(__file__).parent.parent
    schema_path = repo_root / "locales.schema.json"

    if not schema_path.exists():
        print(f"ERROR: Schema file not found at {schema_path}")
        return 1

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    locale_files = locale_paths(repo_root)

    if not locale_files:
        print("ERROR: No locale JSON files found")
        return 1

    if jsonschema is None:
        print("WARNING: jsonschema not installed — falling back to basic type checks")
        errors, summaries = basic_errors(locale_files, schema)
        return report(
            errors,
            summaries,
            "BASIC VALIDATION",
            f"All {len(locale_files)} locale files pass basic validation",
        )

    errors, summaries = schema_errors(locale_files, schema)
    return report(
        errors,
        summaries,
        "SCHEMA VALIDATION",
        f"All {len(locale_files)} locale files match schema",
    )


if __name__ == "__main__":
    sys.exit(main())
