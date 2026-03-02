# CLAUDE.md - vauchi/locales

> **Inherits**: See root [CLAUDE.md](https://gitlab.com/vauchi/vauchi/-/blob/main/CLAUDE.md).

Locale JSON files. Source of truth for all translations.

## Rules

- `en.json` is source of truth — all keys must exist here first
- All locales must have same keys (CI validates parity). No empty values.
- JSON sorted alphabetically. Keys use dot notation: `section.subsection.name`
- Validate: `python3 scripts/validate.py --strict`
