#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later

# Gate 7: Cross-repo locale key validation
# (frontend architecture audit 2026-03-18; fix-and-tighten 2026-05-08)
#
# Extracts string-literal i18n key references from source code and
# verifies each one exists in en.json. Catches typo'd / stale keys
# BEFORE merge — they would otherwise ship as the runtime fallback
# `format!("Missing: {}", key)` (vauchi/core: vauchi-app/src/i18n.rs).
#
# What this script can and cannot detect:
#
#   ✓ Literal-string i18n keys passed directly to a known call site:
#       get_string(locale, "ui.contact.add_button")
#       NSLocalizedString("ui.contact.add_button", ...)
#       t("ui.contact.add_button")
#   ✗ Variable-key call sites (statically unreachable):
#       get_string(locale, &computed_key)
#       t(`ui.contact.${name}`)
#     — covered by test discipline + runtime fallback, not this gate.
#
# Usage:
#   check-locale-key-coverage.sh <source-dir> [options]
#
# Options:
#   --locales-dir <dir>   Locales JSON dir (default: ../locales relative
#                         to this script's parent)
#   --language <lang>     rust | swift | kotlin | ts (default: inferred
#                         from --pattern extension)
#   --pattern <glob>      File glob to scan (default: per-language)
#   --allowlist <file>    Allowlist of permitted non-en.json keys
#                         (default: <script-dir>/.key-coverage-allow)
#
# Backward-compatible positional form (deprecated, but supported):
#   check-locale-key-coverage.sh <source-dir> <locales-dir> [file-pattern]
#
# Examples:
#   check-locale-key-coverage.sh ../core/vauchi-app/src --language rust
#   check-locale-key-coverage.sh ../ios/Vauchi --language swift
#   check-locale-key-coverage.sh ../tui/src --pattern '*.rs'
#
# Requires: rg (ripgrep), jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- argument parsing -----------------------------------------------------

SOURCE_DIR=""
LOCALES_DIR=""
LANGUAGE=""
FILE_PATTERN=""
ALLOWLIST_FILE="$SCRIPT_DIR/.key-coverage-allow"
POSITIONAL_COUNT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --locales-dir)  LOCALES_DIR="$2"; shift 2 ;;
        --language)     LANGUAGE="$2";    shift 2 ;;
        --pattern)      FILE_PATTERN="$2"; shift 2 ;;
        --allowlist)    ALLOWLIST_FILE="$2"; shift 2 ;;
        --help|-h)
            sed -n '5,46p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
            exit 0
            ;;
        --*)
            echo "ERROR: unknown option: $1" >&2
            exit 2
            ;;
        *)
            POSITIONAL_COUNT=$((POSITIONAL_COUNT + 1))
            case "$POSITIONAL_COUNT" in
                1)  SOURCE_DIR="$1" ;;
                2)  LOCALES_DIR="${LOCALES_DIR:-$1}" ;;  # legacy positional
                3)  FILE_PATTERN="${FILE_PATTERN:-$1}" ;;
                *)  echo "ERROR: too many positional args" >&2; exit 2 ;;
            esac
            shift
            ;;
    esac
done

if [[ -z "$SOURCE_DIR" ]]; then
    echo "ERROR: <source-dir> required. See --help." >&2
    exit 2
fi
if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "ERROR: source dir not found: $SOURCE_DIR" >&2
    exit 1
fi

# Default locales dir relative to this script (locales/scripts/ → locales/)
if [[ -z "$LOCALES_DIR" ]]; then
    LOCALES_DIR="$SCRIPT_DIR/.."
fi
if [[ ! -d "$LOCALES_DIR" ]]; then
    echo "ERROR: locales dir not found: $LOCALES_DIR" >&2
    exit 1
fi

EN_FILE="$LOCALES_DIR/en.json"
if [[ ! -f "$EN_FILE" ]]; then
    echo "ERROR: en.json not found in $LOCALES_DIR" >&2
    exit 1
fi

# ---- language → regex / default-pattern -----------------------------------

# Infer language from --pattern if not explicit.
if [[ -z "$LANGUAGE" && -n "$FILE_PATTERN" ]]; then
    case "$FILE_PATTERN" in
        *.rs)     LANGUAGE="rust" ;;
        *.swift)  LANGUAGE="swift" ;;
        *.kt|*.kts) LANGUAGE="kotlin" ;;
        *.ts|*.tsx) LANGUAGE="ts" ;;
    esac
fi

# Default pattern per language.
if [[ -z "$FILE_PATTERN" ]]; then
    case "$LANGUAGE" in
        rust)    FILE_PATTERN="*.rs" ;;
        swift)   FILE_PATTERN="*.swift" ;;
        kotlin)  FILE_PATTERN="*.kt" ;;
        ts)      FILE_PATTERN="*.ts" ;;
        "")
            echo "ERROR: --language not specified and cannot infer from pattern" >&2
            echo "       Pass --language rust|swift|kotlin|ts" >&2
            exit 2
            ;;
        *)
            echo "ERROR: unknown language: $LANGUAGE" >&2
            exit 2
            ;;
    esac
fi

# Per-language extraction regexes. Each rg invocation captures only the
# string-literal arg of a known i18n call site; this is the tightening
# pass that retired the over-broad `"[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*"`
# heuristic (the old version matched log targets, module paths, and
# format strings like `nav.*`).
# Strip line comments before regex extraction so call-site shapes
# inside doc comments don't false-positive (e.g. `/// get_string(
# locale, "nav.*")` in navigation.rs). All four supported languages
# use `//`-led line comments. Trade-off: this also strips trailing
# `//`-text inside ordinary string literals containing `//` (e.g.
# `"https://example.com"`). False negatives there are acceptable;
# false positives would block merges.
_stream_stripped() {
    local dir="$1" pattern="$2"
    find "$dir" -type f -name "$pattern" -print0 \
        | xargs -0 sed 's|//.*||' 2>/dev/null
}

extract_keys_rust() {
    _stream_stripped "$1" "$2" \
        | rg -oI --pcre2 \
            '\bget_string(?:_with_args)?\s*\([^,]*,\s*"([^"]+)"' \
            -r '$1' 2>/dev/null || true
}
extract_keys_swift() {
    # Two shapes:
    #   - NSLocalizedString("…", comment: …)  — Apple-native (legacy)
    #   - <obj>.t("…")                         — vauchi convention via
    #     `LocalizationService.t(_:)` / `localizationManager.t(…)`,
    #     which wraps the UniFFI `mobile_get_string` binding.
    # The `.t(` form is matched with a leading `\.` so an unrelated
    # bare `t(` (e.g. `t.x()` on a tuple variable) doesn't false-
    # positive. Kotlin/TS use bare `t(` (different convention).
    _stream_stripped "$1" "$2" \
        | rg -oI --pcre2 \
            '\b(?:NSLocalizedString\s*\(|\.t\s*\()\s*"([^"]+)"' \
            -r '$1' 2>/dev/null || true
}
extract_keys_kotlin() {
    # Compose: t("key") / i18n.get("key"). Android resource-IDs
    # (R.string.foo) are not literal strings; not handled here.
    _stream_stripped "$1" "$2" \
        | rg -oI --pcre2 \
            '\b(?:t|i18n\.get)\s*\(\s*"([^"]+)"' \
            -r '$1' 2>/dev/null || true
}
extract_keys_ts() {
    # t("key") / t('key') / i18n.get("key") — both quote styles.
    {
        _stream_stripped "$1" "$2" \
            | rg -oI --pcre2 \
                '\b(?:t|i18n\.get)\s*\(\s*"([^"]+)"' \
                -r '$1' 2>/dev/null || true
        _stream_stripped "$1" "$2" \
            | rg -oI --pcre2 \
                "\\b(?:t|i18n\\.get)\\s*\\(\\s*'([^']+)'" \
                -r '$1' 2>/dev/null || true
    }
}

case "$LANGUAGE" in
    rust)    REFERENCED_KEYS=$(extract_keys_rust   "$SOURCE_DIR" "$FILE_PATTERN" | sort -u) ;;
    swift)   REFERENCED_KEYS=$(extract_keys_swift  "$SOURCE_DIR" "$FILE_PATTERN" | sort -u) ;;
    kotlin)  REFERENCED_KEYS=$(extract_keys_kotlin "$SOURCE_DIR" "$FILE_PATTERN" | sort -u) ;;
    ts)      REFERENCED_KEYS=$(extract_keys_ts     "$SOURCE_DIR" "$FILE_PATTERN" | sort -u) ;;
esac

# ---- allowlist + en.json key set -----------------------------------------

if [[ -f "$ALLOWLIST_FILE" ]]; then
    ALLOW=$(grep -v '^\s*#' "$ALLOWLIST_FILE" | grep -v '^\s*$' | sort -u || true)
else
    ALLOW=""
fi

EN_KEYS=$(jq -r 'keys[] | select(startswith("_meta") | not)' "$EN_FILE" | sort)

# ---- analysis -------------------------------------------------------------

echo "=== Locale Key Coverage ==="
echo "  source:    $SOURCE_DIR"
echo "  language:  $LANGUAGE  (pattern: $FILE_PATTERN)"
echo "  locales:   $LOCALES_DIR"
echo "  allowlist: $([ -f "$ALLOWLIST_FILE" ] && echo "$ALLOWLIST_FILE" || echo "(none)")"
echo ""

if [[ -z "$REFERENCED_KEYS" ]]; then
    echo "INFO: no $LANGUAGE i18n call-site references found in $SOURCE_DIR"
    exit 0
fi

REF_COUNT=$(echo "$REFERENCED_KEYS" | wc -l | tr -d ' ')
echo "Found $REF_COUNT unique key reference(s)"

ERRORS=0

# Pass 1 — typo/stale detection. Flag candidates that are NEITHER in
# en.json NOR in the allowlist. This is the gate the original script
# claimed to deliver but inverted with `grep -qFx` filter retention.
TYPOS=""
while IFS= read -r key; do
    [[ -z "$key" ]] && continue
    if echo "$EN_KEYS" | grep -qFx "$key"; then
        continue  # in en.json — valid
    fi
    if [[ -n "$ALLOW" ]] && echo "$ALLOW" | grep -qFx "$key"; then
        continue  # in allowlist — intentional non-i18n string
    fi
    TYPOS+="$key"$'\n'
done <<< "$REFERENCED_KEYS"

if [[ -n "$TYPOS" ]]; then
    TYPO_COUNT=$(echo -n "$TYPOS" | grep -c . || true)
    echo ""
    echo "ERROR: $TYPO_COUNT key(s) referenced in source but missing from en.json:"
    while IFS= read -r key; do
        [[ -z "$key" ]] && continue
        echo "  - $key"
    done <<< "$TYPOS"
    echo ""
    echo "  Likely causes: typo, stale call site after rename, or"
    echo "  legitimate non-i18n string (add to $ALLOWLIST_FILE)."
    ERRORS=$((ERRORS + TYPO_COUNT))
fi

# Pass 2 — defense in depth. Every key in en.json that's referenced in
# source must also exist in every other locale. validate.py --strict
# already covers this for ALL en.json keys (not just referenced ones);
# we keep this pass so a single-script CI job is self-contained.
VALID_REFERENCED=$(comm -12 <(echo "$REFERENCED_KEYS") <(echo "$EN_KEYS"))

if [[ -n "$VALID_REFERENCED" ]]; then
    for locale_file in "$LOCALES_DIR"/*.json; do
        filename=$(basename "$locale_file" .json)
        [[ "$filename" == *.schema ]] && continue
        [[ "$filename" == _* ]] && continue
        [[ "$filename" == "en" ]] && continue

        LOCALE_KEYS=$(jq -r 'keys[] | select(startswith("_meta") | not)' "$locale_file" | sort)
        MISSING=$(comm -23 <(echo "$VALID_REFERENCED") <(echo "$LOCALE_KEYS") || true)
        if [[ -n "$MISSING" ]]; then
            MISS_COUNT=$(echo "$MISSING" | grep -c . || true)
            echo ""
            echo "ERROR: $MISS_COUNT key(s) in en.json + source but missing from $filename.json:"
            while IFS= read -r key; do
                [[ -z "$key" ]] && continue
                echo "  - $key"
            done <<< "$MISSING"
            ERRORS=$((ERRORS + MISS_COUNT))
        fi
    done
fi

# ---- result ---------------------------------------------------------------

echo ""
if [[ "$ERRORS" -gt 0 ]]; then
    echo "FAILED: $ERRORS issue(s) found."
    exit 1
else
    echo "OK: all $REF_COUNT referenced key(s) exist in en.json + every locale."
fi
