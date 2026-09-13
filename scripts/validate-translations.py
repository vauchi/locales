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


def locale_paths(root: Path) -> list[Path]:
    return sorted(
        p for p in root.glob("*.json") if not p.name.endswith(".schema.json")
    )


def load_locales(root: Path) -> tuple[dict[str, dict], list[str]]:
    """Read every locale file under `root`, collecting unreadable ones."""
    locales: dict[str, dict] = {}
    errors: list[str] = []

    for path in locale_paths(root):
        code = path.stem
        try:
            with open(path, encoding="utf-8") as f:
                locales[code] = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"{code}.json: Invalid JSON — {e}")

    return locales, errors


def check_meta_locale(locales: dict[str, dict]) -> list[str]:
    """The locale code inside a file must match the file it lives in."""
    errors = []
    for code, data in locales.items():
        meta = data.get("_meta", {})
        if isinstance(meta, dict):
            meta_locale = meta.get("locale", "")
            if meta_locale and meta_locale != code:
                errors.append(
                    f"{code}.json: _meta.locale is '{meta_locale}', expected '{code}'"
                )
    return errors


def check_critical_keys(locales: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Returns (errors, summaries) for the keys the English fallback needs."""
    errors, summaries = [], []
    for code, data in locales.items():
        missing = [k for k in CRITICAL_KEYS if k not in data]
        if missing:
            errors.append(
                f"{code}.json: Missing {len(missing)} critical keys: "
                + ", ".join(missing[:5])
                + ("..." if len(missing) > 5 else "")
            )
        else:
            summaries.append(
                f"  {code}.json: All {len(CRITICAL_KEYS)} critical keys present"
            )
    return errors, summaries


def check_expected_translations(locales: dict[str, dict]) -> list[str]:
    """Smoke-test known translations against accidental overwrites."""
    errors = []
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
    return errors


def check_translations(locales: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Run every translation gate. Returns (errors, summaries)."""
    errors = check_meta_locale(locales)
    critical_errors, summaries = check_critical_keys(locales)
    errors.extend(critical_errors)
    errors.extend(check_expected_translations(locales))
    return errors, summaries


def main():
    repo_root = Path(__file__).parent.parent

    if not locale_paths(repo_root):
        print("ERROR: No locale JSON files found")
        sys.exit(1)

    locales, errors = load_locales(repo_root)

    print(f"Validating translations for {len(locales)} locales...\n")

    check_errors, summaries = check_translations(locales)
    for line in summaries:
        print(line)
    errors.extend(check_errors)

    print()
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print("All critical translations validated.")


if __name__ == "__main__":
    main()
