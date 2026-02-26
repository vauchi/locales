#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate locales.schema.json from en.json (source of truth).

This is a one-time generator. The resulting schema is committed and
maintained manually afterward. Re-run only when adding new keys to en.json.
"""

import json
import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).parent.parent
    en_path = repo_root / "en.json"

    if not en_path.exists():
        print(f"ERROR: {en_path} not found")
        sys.exit(1)

    with open(en_path, encoding="utf-8") as f:
        data = json.load(f)

    regular_keys = sorted([k for k in data.keys() if k != "_meta"])

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://vauchi.app/schemas/locales.schema.json",
        "title": "Locale",
        "description": "Locale file for Vauchi. Each file is a flat object mapping dot-notation keys to translated strings, with a _meta object.",
        "type": "object",
        "required": ["_meta"] + regular_keys,
        "properties": {
            "_meta": {
                "type": "object",
                "description": "Metadata about this locale file",
                "required": ["locale", "name", "english_name", "is_rtl"],
                "properties": {
                    "locale": {
                        "type": "string",
                        "pattern": "^[a-z]{2}(-[A-Z]{2})?$",
                        "description": "BCP-47 locale code (e.g. en, de, fr-CH)",
                    },
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Locale name in its own language",
                    },
                    "english_name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Locale name in English",
                    },
                    "is_rtl": {
                        "type": "boolean",
                        "description": "Whether this locale uses right-to-left text direction",
                    },
                },
                "additionalProperties": False,
            }
        },
        "patternProperties": {
            "^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_.]*$": {
                "type": "string",
                "minLength": 1,
                "description": "Translated string value (must not be empty)",
            }
        },
        "additionalProperties": False,
    }

    out_path = repo_root / "locales.schema.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Schema written to {out_path}")
    print(f"  Required keys: {len(regular_keys)} translation keys + _meta")


if __name__ == "__main__":
    main()
