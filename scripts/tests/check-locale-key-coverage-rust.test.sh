#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later

# Rust extraction for check-locale-key-coverage.sh.
#
# The gate ran in core's CI throughout, yet `hardware.error_title` and
# four siblings reached main absent from every locale and turned four
# tests red. Cause: extract_keys_rust matched only `get_string(…)`, and
# only within one line. `self.t("…")` — 1414 call sites in vauchi-app,
# the dominant convention — was matched for Swift but not Rust, and a
# call rustfmt split across lines put the key on its own line where
# line-based matching never saw it. The gate checked 48 keys out of 974.
#
# Per CC-27 each case below plants a key that does not exist and asserts
# the gate REPORTS it; the negative cases assert it stays quiet, because
# a false positive here blocks merges.

set -uo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
GATE="$DIR/check-locale-key-coverage.sh"
LOCALES="$(cd "$DIR/.." && pwd)"

pass=0
fail=0

# run_gate <source-dir> → prints the gate output.
#
# The output is captured before matching, never piped into grep: the gate
# exits non-zero by design when it finds a missing key, and under
# `pipefail` that failure would mask grep's success and make every
# positive case look like it had not fired.
run_gate() {
    bash "$GATE" "$1" "$LOCALES" '*.rs' 2>&1 || true
}

expect_reported() {
    name="$1"; key="$2"; src="$3"
    out=$(run_gate "$src")
    if printf '%s' "$out" | grep -q -- "$key"; then
        printf '  PASS %s\n' "$name"; pass=$((pass + 1))
    else
        printf '  FAIL %s — gate did not report %s\n' "$name" "$key" >&2
        fail=$((fail + 1))
    fi
}

expect_quiet() {
    name="$1"; needle="$2"; src="$3"
    out=$(run_gate "$src")
    if printf '%s' "$out" | grep -q -- "$needle"; then
        printf '  FAIL %s — gate wrongly reported %s\n' "$name" "$needle" >&2
        fail=$((fail + 1))
    else
        printf '  PASS %s\n' "$name"; pass=$((pass + 1))
    fi
}

mksrc() {
    d=$(mktemp -d)/src
    mkdir -p "$d"
    cat >"$d/probe.rs"
    printf '%s' "$d"
}

# ── 1. self.t("…") — the shape that was invisible ─────────────────────
src=$(mksrc <<'RS'
fn title(&self) -> String {
    self.t("zzz.self_t_missing")
}
RS
)
expect_reported "self.t() reference is seen" "zzz.self_t_missing" "$src"

# ── 2. multi-line call — rustfmt's output for a long argument list ────
# This is the exact shape of the real hardware-copy call in routing.rs.
src=$(mksrc <<'RS'
fn message(&self) -> String {
    crate::i18n::get_string_with_args(
        self.render_context.resolved_locale(),
        "zzz.multi_line_missing",
        &[("name", &name)],
    )
}
RS
)
expect_reported "key on its own line is seen" "zzz.multi_line_missing" "$src"

# ── 3. the original single-line shape still works ─────────────────────
src=$(mksrc <<'RS'
fn one(&self) -> String { get_string(locale, "zzz.single_line_missing") }
RS
)
expect_reported "single-line get_string still seen" "zzz.single_line_missing" "$src"

# ── 4. a real key must not be reported ────────────────────────────────
src=$(mksrc <<'RS'
fn ok(&self) -> String { self.t("action.cancel") }
RS
)
expect_quiet "existing key stays quiet" "action.cancel" "$src"

# ── 5. `.t(` on an unrelated receiver must not inject a reference ─────
# Keys must look dotted-and-lowercase, so arbitrary `.t("…")` calls on
# some other type cannot manufacture a bogus finding that blocks a merge.
src=$(mksrc <<'RS'
fn unrelated(&self) -> String {
    parser.t("Some Free Text");
    tuple.t("NotAKey")
}
RS
)
expect_quiet "non-key .t() argument ignored" "NotAKey" "$src"

# ── 6. the system bash runs the gate ──────────────────────────────────
# On macOS /bin/bash is 3.2, and a CI shell runner there resolves `bash`
# to it. Anything bash-4-only in the gate aborts it before it can report.
if [ -x /bin/bash ]; then
    src=$(mksrc <<'RS'
fn title(&self) -> String { self.t("zzz.system_bash_missing") }
RS
)
    out=$(/bin/bash "$GATE" "$src" "$LOCALES" '*.rs' 2>&1 || true)
    if printf '%s' "$out" | grep -q -- "- zzz.system_bash_missing"; then
        printf '  PASS gate reports under /bin/bash\n'; pass=$((pass + 1))
    else
        printf '  FAIL gate did not report under /bin/bash\n' >&2
        printf '%s\n' "$out" | tail -4 | sed 's/^/      /' >&2
        fail=$((fail + 1))
    fi
fi

# ── 7. the live tree passes ───────────────────────────────────────────
# Guards against an extractor so eager it blocks what already ships.
ws="$(cd "$LOCALES/.." && pwd)"
if [ -d "$ws/core/vauchi-app/src" ]; then
    live_out=$(run_gate "$ws/core/vauchi-app/src")
    if printf '%s' "$live_out" | grep -q "^OK:"; then
        printf '  PASS live vauchi-app source passes\n'; pass=$((pass + 1))
    else
        printf '  FAIL live vauchi-app source now fails the gate\n' >&2
        run_gate "$ws/core/vauchi-app/src" | tail -6 | sed 's/^/      /' >&2
        fail=$((fail + 1))
    fi
fi

# ── 8. a ripgrep without PCRE2 fails loudly ──────────────────────────
# Every extraction regex needs `rg --pcre2`. A build without it made each
# search come back empty, so the gate saw no call sites at all and the
# failures above were all it could say (locales!164 on the allyson runner,
# 2026-09-25). The gate must name the missing capability instead.
real_rg=$(command -v rg || true)
if [ -n "$real_rg" ]; then
    fake=$(mktemp -d)
    cat >"$fake/rg" <<SH
#!/bin/sh
for arg in "\$@"; do
    case "\$arg" in
        --pcre2-version) echo "PCRE2 is not available in this build of ripgrep."; exit 1 ;;
        --pcre2) echo "PCRE2 is not available in this build of ripgrep." >&2; exit 2 ;;
    esac
done
exec "$real_rg" "\$@"
SH
    chmod +x "$fake/rg"
    src=$(mksrc <<'RS'
fn title(&self) -> String { self.t("zzz.no_pcre2_missing") }
RS
)
    status=0
    out=$(PATH="$fake:$PATH" bash "$GATE" "$src" "$LOCALES" '*.rs' 2>&1) || status=$?
    if [ "$status" -ne 0 ] && printf '%s' "$out" | grep -q "PCRE2"; then
        printf '  PASS a ripgrep without PCRE2 fails loudly\n'; pass=$((pass + 1))
    else
        printf '  FAIL a ripgrep without PCRE2 did not fail loudly (exit %s)\n' "$status" >&2
        printf '%s\n' "$out" | tail -4 | sed 's/^/      /' >&2
        fail=$((fail + 1))
    fi
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
