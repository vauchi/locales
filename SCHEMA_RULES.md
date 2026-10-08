<!-- SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me> -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Schema Evolution Rules — Locales

This document defines how `locales.schema.json` may be changed without
breaking downstream consumers.

## Schema File

- **`locales.schema.json`** — JSON Schema (2020-12 draft) defining the
  contract for all locale files.
- **`en.json`** — English locale, the source of truth. All keys in
  en.json are required by the schema, so `required` is the catalogue's
  key list.

## What Is a Breaking Change?

A **breaking change** is any schema modification that removes or
reshapes data consumers depend on. Consumers vendor the whole catalogue
(core `scripts/vendor-locales.sh`), so a new key arrives together with
its value; `validate-locales-strict` keeps every locale file in step
within the MR that adds it.

| Change | Breaking? | Why |
|--------|-----------|-----|
| Add a key to `required` | No | A new string; it ships with its value |
| Remove a key from `required` | **Yes** | Consumers may still use it |
| Remove a property from `properties` | **Yes** | Consumers expecting it break |
| Change a property's `type` | **Yes** | Existing data may not match |
| Add `additionalProperties: false` | **Yes** | Data with extra fields fails |
| Remove a `patternProperties` pattern | **Yes** | Values lose their rule |
| Add a new optional property | No | Existing data is unaffected |
| Add a new `patternProperties` pattern | No | Existing data is unaffected |
| Relax `minLength` or drop a `pattern` | No | Existing data still passes |

## Rules

### 1. Adding a New Locale Key

When a new translation key is needed:

1. Add the key to `en.json` (source of truth) with its English value.
2. Add the key to all other locale files (CI enforces parity).
3. Add the key to the `required` array in `locales.schema.json`.
4. `check-schema-compat` reports it as `INFO`; the MR is not blocked.

Use `scripts/generate-schema.py` to regenerate the schema from `en.json`
if many keys are added at once.

### 2. Removing a Locale Key

When a translation key is no longer needed:

1. Verify no consumers reference the key (search `core/`, `cli/`,
   `desktop/`, `ios/`, `android/`).
2. Remove the key from all locale files.
3. Remove the key from the `required` array in `locales.schema.json`.
4. `check-schema-compat` fails this as breaking. State in the MR why no
   consumer uses the key any more.

### 3. Renaming a Locale Key

Renaming is an add-then-remove:

1. Add the new key (not breaking).
2. Update all consumers to use the new key.
3. Remove the old key (breaking — see rule 2).
4. Ship as two separate MRs to avoid a window where consumers reference
   a missing key.

### 4. Changing the `_meta` Structure

Changes to the `_meta` object affect every locale file:

- Adding a field to `_meta` is not breaking.
- Removing a field, or dropping it from `required`, is breaking if
  consumers depend on it.

## CI Enforcement

| Job | What It Checks |
|-----|---------------|
| `validate-schema` | All `*.json` files pass the schema |
| `check-schema-compat` | No breaking change vs `main` (see table above) |
| `validate-locales-strict` | Key parity, sorted keys, no empty values |
| `validate-translations` | Critical keys present, known translations |

## Versioning Strategy

The schema does not have a formal version number. Breaking changes are
detected automatically by CI comparing the MR branch schema against
`main`. If a breaking change is intentional:

1. Document the reason in the MR description.
2. Update all locale files in the same MR.
3. Coordinate with `core/` to update `min_app_version` if the change
   affects OTA content delivery.
