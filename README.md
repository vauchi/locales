<!-- SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me> -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

> **Mirror:** This repo is a read-only mirror of [gitlab.com/vauchi/locales](https://gitlab.com/vauchi/locales). Please open issues and merge requests there.

[![Pipeline](https://img.shields.io/endpoint?url=https://vauchi.gitlab.io/locales/badges/pipeline.json&label=pipeline)](https://gitlab.com/vauchi/locales/-/pipelines)
[![REUSE](https://api.reuse.software/badge/gitlab.com/vauchi/locales)](https://api.reuse.software/info/gitlab.com/vauchi/locales)

# Vauchi Locales

Locale JSON files for [Vauchi](https://vauchi.com) — privacy-focused updatable contact cards.

## Languages

| File | Language | Status |
|------|----------|--------|
| `en.json` | English | Source of truth |
| `de.json` | German | Complete |
| `fr.json` | French | Complete |
| `es.json` | Spanish | Complete |

## Contributing Translations

We welcome community translations! To contribute:

1. Fork this repo
2. Copy `en.json` to your language code (e.g., `it.json` for Italian)
3. Translate all values — keep keys identical
4. Submit a merge request

### Guidelines

- Keep the same JSON structure and key names
- Do not translate placeholder tokens like `{count}`, `{name}`, etc.
- Preserve any HTML or markdown formatting in values
- When unsure about context, check the [Vauchi app](https://vauchi.com) or open an issue

## Format

Each file is a flat JSON object with dot-notation keys:

```json
{
  "_meta.locale": "en",
  "_meta.name": "English",
  "welcome.title": "Welcome to Vauchi",
  "contacts.count": "{count} contacts"
}
```

## License

GPL-3.0-or-later
