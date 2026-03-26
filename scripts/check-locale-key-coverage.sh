#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later

# Gate 7: Cross-repo locale key validation (frontend architecture audit 2026-03-18)
#
# Extracts i18n key references from source code and verifies they exist in all
# locale JSON files. Catches missing keys BEFORE merge (not at runtime fallback).
#
# Usage:
#   check-locale-key-coverage.sh <source-dir> <locales-dir> [file-pattern]
#
# Examples:
#   check-locale-key-coverage.sh ../tui/src ../locales '*.rs'
#   check-locale-key-coverage.sh ../ios/Vauchi ../locales '*.swift'
#   check-locale-key-coverage.sh ../android/app/src ../locales '*.kt'

set -euo pipefail

SOURCE_DIR="${1:?Usage: check-locale-key-coverage.sh <source-dir> <locales-dir> [file-pattern]}"
LOCALES_DIR="${2:?Usage: check-locale-key-coverage.sh <source-dir> <locales-dir> [file-pattern]}"
FILE_PATTERN="${3:-*}"

if [[ ! -d "$LOCALES_DIR" ]]; then
    echo "ERROR: Locales directory not found: $LOCALES_DIR"
    exit 1
fi

EN_FILE="$LOCALES_DIR/en.json"
if [[ ! -f "$EN_FILE" ]]; then
    echo "ERROR: en.json not found in $LOCALES_DIR"
    exit 1
fi

# Extract all locale keys from en.json (excluding _meta)
EN_KEYS=$(jq -r 'keys[] | select(startswith("_meta") | not)' "$EN_FILE" | sort)

# Extract referenced i18n keys from source code.
# Patterns we look for (covers Rust, Swift, Kotlin, TypeScript):
#   get_string(Locale::*, "key.name")
#   getString("key.name")
#   get_string_with_args(Locale::*, "key.name", ...)
#   getStringWithArgs("key.name", ...)
#   i18n::get("key.name")
#   t("key.name")
#   NSLocalizedString("key.name", ...)
# All patterns have the key as a quoted string with dot-separated segments.

REFERENCED_KEYS=$(
    rg -o '"([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*)"' --no-filename -r '$1' \
        --glob "$FILE_PATTERN" "$SOURCE_DIR" 2>/dev/null \
    | sort -u \
    | while IFS= read -r key; do
        # Only include keys that look like i18n keys (at least one dot, lowercase)
        if echo "$EN_KEYS" | grep -qFx "$key"; then
            echo "$key"
        fi
    done
)

if [[ -z "$REFERENCED_KEYS" ]]; then
    echo "INFO: No locale key references found in $SOURCE_DIR (pattern: $FILE_PATTERN)"
    exit 0
fi

REF_COUNT=$(echo "$REFERENCED_KEYS" | wc -l | tr -d ' ')
echo "Found $REF_COUNT locale key references in $SOURCE_DIR"

# Check that every referenced key exists in ALL locale files
ERRORS=0
for locale_file in "$LOCALES_DIR"/*.json; do
    filename=$(basename "$locale_file" .json)
    [[ "$filename" == *.schema ]] && continue
    [[ "$filename" == _* ]] && continue

    LOCALE_KEYS=$(jq -r 'keys[] | select(startswith("_meta") | not)' "$locale_file" | sort)

    MISSING=$(comm -23 <(echo "$REFERENCED_KEYS") <(echo "$LOCALE_KEYS"))
    if [[ -n "$MISSING" ]]; then
        MISS_COUNT=$(echo "$MISSING" | wc -l | tr -d ' ')
        echo ""
        echo "ERROR: $MISS_COUNT key(s) referenced in source but missing from $filename.json:"
        while IFS= read -r key; do echo "  $key"; done <<< "$MISSING"
        ERRORS=$((ERRORS + MISS_COUNT))
    fi
done

if [[ "$ERRORS" -gt 0 ]]; then
    echo ""
    echo "FAILED: $ERRORS missing locale key(s) found."
    echo "Add the missing keys to all locale files in $LOCALES_DIR/"
    exit 1
else
    echo "OK: All $REF_COUNT referenced keys exist in all locale files."
fi
