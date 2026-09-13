#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Validate locale JSON files for key parity, valid JSON, and no empty values."""

import json
import sys
from pathlib import Path


def load_locale(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def locale_paths(root: Path) -> list[Path]:
    return sorted(
        p for p in root.glob("*.json") if not p.name.endswith(".schema.json")
    )


def load_locales(root: Path) -> tuple[dict[str, dict], list[str], list[str]]:
    """Read every locale file under `root`.

    Returns the parsed locales, the errors from unparsable files, and the
    per-file summary lines.
    """
    locales: dict[str, dict] = {}
    errors: list[str] = []
    summaries: list[str] = []

    for path in locale_paths(root):
        code = path.stem
        try:
            data = load_locale(path)
            locales[code] = data
            summaries.append(f"  {code}.json: {len(data)} keys — OK")
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")

    return locales, errors, summaries


def check_locales(
    locales: dict[str, dict], strict: bool
) -> tuple[list[str], list[str]]:
    """Check parity, empty values and key ordering.

    Returns (errors, warnings). Outside strict mode a parity or ordering
    finding is a warning; an empty value or a missing en.json is always an
    error.
    """
    errors: list[str] = []
    warnings: list[str] = []

    for code, data in locales.items():
        for key, value in data.items():
            if isinstance(value, str) and value.strip() == "":
                errors.append(f"{code}.json: Empty value for key '{key}'")

    if "en" not in locales:
        errors.append("en.json missing — English is the source of truth")
    else:
        en_keys = set(locales["en"].keys())

        for code, data in locales.items():
            if code == "en":
                continue

            other_keys = set(data.keys())
            missing = en_keys - other_keys
            extra = other_keys - en_keys

            if missing:
                msg = f"{code}.json: Missing {len(missing)} keys from en.json"
                if strict:
                    errors.append(msg)
                    for k in sorted(missing)[:10]:
                        errors.append(f"  - {k}")
                    if len(missing) > 10:
                        errors.append(f"  ... and {len(missing) - 10} more")
                else:
                    warnings.append(msg)

            if extra:
                msg = f"{code}.json: {len(extra)} extra keys not in en.json"
                if strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    for code, data in locales.items():
        keys = list(data.keys())
        if keys != sorted(keys):
            msg = f"{code}.json: Keys not sorted alphabetically"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

    return errors, warnings


def main():
    strict = "--strict" in sys.argv
    repo_root = Path(__file__).parent.parent

    if not locale_paths(repo_root):
        print("ERROR: No locale JSON files found")
        sys.exit(1)

    locales, errors, summaries = load_locales(repo_root)
    for line in summaries:
        print(line)

    if not locales:
        print("ERROR: No valid locale files")
        sys.exit(1)

    check_errors, warnings = check_locales(locales, strict)
    errors.extend(check_errors)

    for warning in warnings:
        print(f"  WARNING: {warning}")

    if errors:
        print(f"\n{'ERRORS' if strict else 'FAILURES'}:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print(f"\nAll {len(locales)} locale files valid.")


if __name__ == "__main__":
    main()
