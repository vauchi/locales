<!-- SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me> -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Schema Evolution Rules — Locales

This document defines how `locales.schema.json` may be changed without breaking downstream consumers.

## Schema File

- **`locales.schema.json`** — JSON Schema (2020-12 draft) defining the contract for all locale files.
- **`en.json`** — English locale, the source of truth. All keys in en.json are required by the schema.

## What Is a Breaking Change?

A **breaking change** is any schema modification that causes previously valid locale data to fail validation, or that removes data consumers depend on.

| Change | Breaking? | Why |
|--------|-----------|-----|
| Add a key to `required` | **Yes** | Existing locale files missing the key will fail validation |
| Remove a property from `properties` | **Yes** | Consumers expecting the property will break |
| Change a property's `type` | **Yes** | Existing data may not match the new type |
| Add `additionalProperties: false` (was absent/true) | **Yes** | Existing data with extra fields will fail |
| Remove a `patternProperties` pattern | **Yes** | Values matching that pattern lose their validation rule |
| Add a new optional property | No | Existing data is unaffected |
| Remove a key from `required` | No | Relaxation — existing data still passes |
| Add a new `patternProperties` pattern | No | Existing data is unaffected |
| Relax `minLength` or remove a `pattern` constraint | No | Relaxation — existing data still passes |

## Rules

### 1. Adding a New Locale Key

When a new translation key is needed:

1. Add the key to `en.json` (source of truth) with its English value.
2. Add the key to all other locale files (CI enforces parity).
3. Add the key to the `required` array in `locales.schema.json`.
4. This is a **breaking change** — all locale files must be updated in the same MR.

Use `scripts/generate-schema.py` to regenerate the schema from `en.json` if many keys are added at once.

### 2. Removing a Locale Key

When a translation key is no longer needed:

1. Verify no consumers reference the key (search `core/`, `cli/`, `desktop/`, `ios/`, `android/`).
2. Remove the key from all locale files.
3. Remove the key from the `required` array in `locales.schema.json`.
4. This is a **non-breaking schema change** (relaxation), but a **consumer-breaking change** — coordinate with downstream repos.

### 3. Renaming a Locale Key

Renaming is an add-then-remove:

1. Add the new key (breaking schema change — all locales must include it).
2. Update all consumers to use the new key.
3. Remove the old key (non-breaking schema change).
4. Ship as two separate MRs to avoid a window where consumers reference a missing key.

### 4. Changing the `_meta` Structure

Changes to the `_meta` object affect every locale file. Follow the same breaking-change rules:
- Adding a required field to `_meta` is breaking.
- Adding an optional field is not breaking.
- Removing a field is breaking if consumers depend on it.

## CI Enforcement

| Job | What It Checks |
|-----|---------------|
| `validate-schema` | All `*.json` files pass `locales.schema.json` validation |
| `check-schema-compat` | No breaking changes vs `main` branch schema |
| `validate-locales-strict` | Key parity, sorted keys, no empty values |
| `validate-translations` | Critical keys present, smoke-test known translations |

## Versioning Strategy

The schema does not have a formal version number. Breaking changes are detected automatically by CI comparing the MR branch schema against `main`. If a breaking change is intentional:

1. Document the reason in the MR description.
2. Update all locale files in the same MR.
3. Coordinate with `core/` to update `min_app_version` if the change affects OTA content delivery.
