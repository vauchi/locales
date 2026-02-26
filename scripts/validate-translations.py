#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Validate critical translation strings across all locale files.

Catches content issues early in the locales repo pipeline, before they
propagate to downstream consumer repos (TUI, CLI, desktop, mobile).

Checks:
  - Critical keys exist in all locales
  - Known translations contain expected substrings (smoke test)
  - _meta locale code matches the filename
"""

import json
import sys
from pathlib import Path

# Critical keys that must exist in every locale file.
# These are used by bundled_english() fallback and core UI elements.
CRITICAL_KEYS = [
    "app.name",
    "app.tagline",
    "welcome.title",
    "welcome.subtitle",
    "nav.home",
    "nav.contacts",
    "nav.settings",
    "exchange.title",
    "exchange.scan",
    "contacts.add",
    "action.cancel",
    "action.confirm",
    "action.save",
    "action.retry",
    "error.generic",
]

# Smoke-test: known translations must contain these substrings.
# Catches accidental overwrites or encoding issues.
EXPECTED_TRANSLATIONS = {
    "en": {
        "app.name": "Vauchi",
        "welcome.title": "Welcome",
    },
    "de": {
        "app.name": "Vauchi",
        "welcome.title": "Willkommen",
    },
    "fr": {
        "app.name": "Vauchi",
        "welcome.title": "Bienvenue",
    },
    "es": {
        "app.name": "Vauchi",
        "welcome.title": "Bienvenido",
    },
}


def main():
    repo_root = Path(__file__).parent.parent
    locale_files = sorted(
        p for p in repo_root.glob("*.json") if not p.name.endswith(".schema.json")
    )
    errors = []

    if not locale_files:
        print("ERROR: No locale JSON files found")
        sys.exit(1)

    locales = {}
    for path in locale_files:
        code = path.stem
        try:
            with open(path, encoding="utf-8") as f:
                locales[code] = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")

    print(f"Validating translations for {len(locales)} locales...\n")

    # Check _meta.locale matches filename
    for code, data in locales.items():
        meta = data.get("_meta", {})
        if isinstance(meta, dict):
            meta_locale = meta.get("locale", "")
            if meta_locale and meta_locale != code:
                errors.append(
                    f"{code}.json: _meta.locale is '{meta_locale}', expected '{code}'"
                )

    # Check critical keys exist in all locales
    for code, data in locales.items():
        missing = [k for k in CRITICAL_KEYS if k not in data]
        if missing:
            errors.append(
                f"{code}.json: Missing {len(missing)} critical keys: "
                + ", ".join(missing[:5])
                + ("..." if len(missing) > 5 else "")
            )
        else:
            print(f"  {code}.json: All {len(CRITICAL_KEYS)} critical keys present")

    # Smoke-test known translations
    for code, expected in EXPECTED_TRANSLATIONS.items():
        if code not in locales:
            errors.append(f"{code}.json: Expected locale file not found")
            continue

        data = locales[code]
        for key, substring in expected.items():
            value = data.get(key, "")
            if substring not in value:
                errors.append(
                    f"{code}.json: '{key}' = '{value}' — "
                    f"expected to contain '{substring}'"
                )

    print()
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print("All critical translations validated.")


if __name__ == "__main__":
    main()
