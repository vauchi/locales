<!-- SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me> -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# CLAUDE.md - vauchi/locales

> **Inherits**: See root repo [CLAUDE.md](https://gitlab.com/vauchi/vauchi/-/blob/main/CLAUDE.md) for project-wide rules.

Locale JSON files for Vauchi. This repo is the source of truth for all translations.

## Rules

- English (`en.json`) is the source of truth — all keys must exist here first
- All locale files must have the same keys as `en.json` (CI validates parity)
- No empty string values allowed
- JSON must be valid and sorted alphabetically by key
- Keys use dot notation: `section.subsection.name`

## Structure

```
en.json   # English (source of truth, 620+ keys)
de.json   # German
fr.json   # French
es.json   # Spanish
```

## Commands

```bash
# Validate all locale files (CI runs this)
python3 scripts/validate.py

# Check key parity across all locales
python3 scripts/validate.py --strict
```

## Consumers

- `core/vauchi-core` — loads at runtime via `i18n::init(resource_dir)`
- `desktop/src-tauri/resources/locales/` — bundled as Tauri resources
- iOS/Android — bundled as app resources, loaded via `init_locales()`
- CDN — published for over-the-air updates via content system

## Adding a New Language

1. Copy `en.json` to `{code}.json`
2. Translate all values (keep keys identical)
3. Add the locale enum variant in `core/vauchi-core/src/i18n.rs`
4. Submit an MR
