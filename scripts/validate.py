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


def main():
    strict = "--strict" in sys.argv
    repo_root = Path(__file__).parent.parent
    locale_files = sorted(repo_root.glob("*.json"))

    if not locale_files:
        print("ERROR: No locale JSON files found")
        sys.exit(1)

    # Load all locales
    locales = {}
    errors = []

    for path in locale_files:
        code = path.stem
        try:
            data = load_locale(path)
            locales[code] = data
            print(f"  {code}.json: {len(data)} keys — OK")
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")

    if not locales:
        print("ERROR: No valid locale files")
        sys.exit(1)

    # Check for empty values
    for code, data in locales.items():
        for key, value in data.items():
            if isinstance(value, str) and value.strip() == "":
                errors.append(f"{code}.json: Empty value for key '{key}'")

    # Check key parity against English (source of truth)
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
                    print(f"  WARNING: {msg}")

            if extra:
                msg = f"{code}.json: {len(extra)} extra keys not in en.json"
                if strict:
                    errors.append(msg)
                else:
                    print(f"  WARNING: {msg}")

    # Check JSON is sorted
    for code, data in locales.items():
        keys = list(data.keys())
        if keys != sorted(keys):
            msg = f"{code}.json: Keys not sorted alphabetically"
            if strict:
                errors.append(msg)
            else:
                print(f"  WARNING: {msg}")

    if errors:
        print(f"\n{'ERRORS' if strict else 'FAILURES'}:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print(f"\nAll {len(locales)} locale files valid.")


if __name__ == "__main__":
    main()
