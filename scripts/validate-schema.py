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


def main() -> int:
    repo_root = Path(__file__).parent.parent
    schema_path = repo_root / "locales.schema.json"

    if not schema_path.exists():
        print(f"ERROR: Schema file not found at {schema_path}")
        return 1

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    locale_files = sorted(repo_root.glob("*.json"))
    # Exclude the schema file itself
    locale_files = [p for p in locale_files if p.name != "locales.schema.json"]

    if not locale_files:
        print("ERROR: No locale JSON files found")
        return 1

    if jsonschema is None:
        print("WARNING: jsonschema not installed — falling back to basic type checks")
        return validate_basic(locale_files, schema)

    errors = []
    for path in locale_files:
        code = path.stem
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            jsonschema.validate(instance=data, schema=schema)
            print(f"  {code}.json: OK ({len(data)} keys)")
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")
        except jsonschema.ValidationError as e:
            # Provide a concise error message
            field = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "(root)"
            errors.append(f"{code}.json: {field} — {e.message}")

    if errors:
        print(f"\nSCHEMA VALIDATION FAILED ({len(errors)} error(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"\nPASSED: All {len(locale_files)} locale files match schema")
    return 0


def validate_basic(locale_files: list[Path], schema: dict) -> int:
    """Fallback validation without jsonschema library."""
    required_keys = set(schema.get("required", []))
    errors = []

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

            # Check _meta structure
            meta = data.get("_meta")
            if meta is not None:
                if not isinstance(meta, dict):
                    errors.append(f"{code}.json: _meta must be an object")
                else:
                    for field in ["locale", "name", "english_name", "is_rtl"]:
                        if field not in meta:
                            errors.append(f"{code}.json: _meta.{field} is required")

            # Check translation values are non-empty strings
            for key, value in data.items():
                if key == "_meta":
                    continue
                if not isinstance(value, str):
                    errors.append(f"{code}.json: '{key}' must be a string, got {type(value).__name__}")
                elif len(value) == 0:
                    errors.append(f"{code}.json: '{key}' must not be empty")

            print(f"  {code}.json: OK ({len(data)} keys)")
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")

    if errors:
        print(f"\nBASIC VALIDATION FAILED ({len(errors)} error(s)):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"\nPASSED: All {len(locale_files)} locale files pass basic validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
