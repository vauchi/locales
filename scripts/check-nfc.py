#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Verify all strings in locale JSON files are NFC-normalized.

Catches NFD strings that cause cross-platform comparison failures.
macOS text input produces NFD; Linux/Windows produce NFC.
"""

import json
import sys
import unicodedata


def check_file(path: str) -> int:
    errors = 0
    with open(path) as f:
        data = json.load(f)
    for key, value in data.items():
        if isinstance(value, str) and value != unicodedata.normalize("NFC", value):
            print(f"  {path}: key '{key}' is not NFC-normalized")
            errors += 1
        if isinstance(value, dict):
            for subkey, subval in value.items():
                if isinstance(subval, str) and subval != unicodedata.normalize("NFC", subval):
                    print(f"  {path}: key '{key}.{subkey}' is not NFC-normalized")
                    errors += 1
    return errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: check-nfc.py <file.json> [file2.json ...]")
        sys.exit(2)

    total = 0
    for path in sys.argv[1:]:
        total += check_file(path)

    if total:
        print(f"\n{total} non-NFC string(s) found.")
        sys.exit(1)

    print("All locale strings are NFC ✓")
