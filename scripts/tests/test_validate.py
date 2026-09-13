#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the key-parity, empty-value and ordering gate.

Whether a finding is fatal depends on --strict: the merge-blocking job
runs strict, the informational one does not, so each rule is asserted in
both modes.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scriptloader import SCRIPTS_DIR, load

validate = load("validate.py")


def write_locales(test_case, **locales) -> Path:
    tmp = tempfile.TemporaryDirectory()
    test_case.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    for code, data in locales.items():
        payload = data if isinstance(data, str) else json.dumps(data)
        (root / f"{code}.json").write_text(payload, encoding="utf-8")
    return root


class KeyParity(unittest.TestCase):
    def test_missing_keys_warn_by_default(self):
        errors, warnings = validate.check_locales(
            {"en": {"a.x": "A", "b.y": "B"}, "de": {"a.x": "A"}}, strict=False
        )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["de.json: Missing 1 keys from en.json"])

    def test_missing_keys_are_fatal_under_strict(self):
        errors, warnings = validate.check_locales(
            {"en": {"a.x": "A", "b.y": "B"}, "de": {"a.x": "A"}}, strict=True
        )

        self.assertEqual(
            errors, ["de.json: Missing 1 keys from en.json", "  - b.y"]
        )
        self.assertEqual(warnings, [])

    def test_strict_lists_the_first_ten_missing_keys_then_a_count(self):
        english = {f"k.{i:02d}": "v" for i in range(14)}

        errors, _ = validate.check_locales(
            {"en": english, "de": {"k.00": "v"}}, strict=True
        )

        self.assertEqual(errors[0], "de.json: Missing 13 keys from en.json")
        self.assertEqual(errors[1:11], [f"  - k.{i:02d}" for i in range(1, 11)])
        self.assertEqual(errors[11], "  ... and 3 more")
        self.assertEqual(len(errors), 12)

    def test_extra_keys_warn_by_default_and_are_fatal_under_strict(self):
        locales = {"en": {"a.x": "A"}, "de": {"a.x": "A", "z.z": "Z"}}

        errors, warnings = validate.check_locales(locales, strict=False)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["de.json: 1 extra keys not in en.json"])

        errors, warnings = validate.check_locales(locales, strict=True)
        self.assertEqual(errors, ["de.json: 1 extra keys not in en.json"])
        self.assertEqual(warnings, [])

    def test_a_locale_matching_english_produces_no_findings(self):
        locales = {"en": {"a.x": "A", "b.y": "B"}, "de": {"a.x": "A", "b.y": "B"}}

        self.assertEqual(validate.check_locales(locales, strict=True), ([], []))

    def test_english_alone_is_not_compared_against_itself(self):
        self.assertEqual(
            validate.check_locales({"en": {"a.x": "A"}}, strict=True), ([], [])
        )


class SourceOfTruth(unittest.TestCase):
    def test_a_missing_english_file_is_fatal_in_both_modes(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                errors, _ = validate.check_locales(
                    {"de": {"a.x": "A"}}, strict=strict
                )

                self.assertEqual(
                    errors, ["en.json missing — English is the source of truth"]
                )


class EmptyValues(unittest.TestCase):
    def test_an_empty_string_is_fatal_in_both_modes(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                errors, _ = validate.check_locales(
                    {"en": {"a.x": ""}}, strict=strict
                )

                self.assertEqual(errors, ["en.json: Empty value for key 'a.x'"])

    def test_a_whitespace_only_string_is_fatal(self):
        errors, _ = validate.check_locales({"en": {"a.x": " \t "}}, strict=False)

        self.assertEqual(errors, ["en.json: Empty value for key 'a.x'"])

    def test_non_string_values_are_not_treated_as_empty(self):
        errors, _ = validate.check_locales(
            {"en": {"_meta": {"is_rtl": False}}}, strict=False
        )

        self.assertEqual(errors, [])


class KeyOrdering(unittest.TestCase):
    def test_unsorted_keys_warn_by_default_and_are_fatal_under_strict(self):
        locales = {"en": {"b.y": "B", "a.x": "A"}}

        errors, warnings = validate.check_locales(locales, strict=False)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["en.json: Keys not sorted alphabetically"])

        errors, warnings = validate.check_locales(locales, strict=True)
        self.assertEqual(errors, ["en.json: Keys not sorted alphabetically"])
        self.assertEqual(warnings, [])

    def test_sorted_keys_produce_no_finding(self):
        errors, warnings = validate.check_locales(
            {"en": {"a.x": "A", "b.y": "B"}}, strict=True
        )

        self.assertEqual((errors, warnings), ([], []))


class Loading(unittest.TestCase):
    def test_each_readable_file_is_summarized_with_its_key_count(self):
        root = write_locales(self, en={"a.x": "A", "b.y": "B"})

        locales, errors, summaries = validate.load_locales(root)

        self.assertEqual(locales, {"en": {"a.x": "A", "b.y": "B"}})
        self.assertEqual(errors, [])
        self.assertEqual(summaries, ["  en.json: 2 keys — OK"])

    def test_an_unparsable_file_is_reported_and_excluded(self):
        root = write_locales(self, en={"a.x": "A"}, de="{not json")

        locales, errors, summaries = validate.load_locales(root)

        self.assertEqual(list(locales), ["en"])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("de.json: Invalid JSON — "))
        self.assertEqual(summaries, ["  en.json: 1 keys — OK"])

    def test_the_schema_file_is_not_read_as_a_locale(self):
        root = write_locales(self, en={"a.x": "A"})
        (root / "locales.schema.json").write_text("{}", encoding="utf-8")

        self.assertEqual(
            validate.locale_paths(root), [root / "en.json"]
        )

    def test_an_empty_directory_yields_no_locale_paths(self):
        root = write_locales(self)

        self.assertEqual(validate.locale_paths(root), [])


class CommandLine(unittest.TestCase):
    """The CI jobs consume the exit code, so pin it directly."""

    def _run(self, locales, *args):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "scripts").mkdir()
        for code, data in locales.items():
            payload = data if isinstance(data, str) else json.dumps(data)
            (root / f"{code}.json").write_text(payload, encoding="utf-8")
        script = root / "scripts" / "validate.py"
        shutil.copy(SCRIPTS_DIR / "validate.py", script)
        return subprocess.run(
            [sys.executable, str(script), *args], capture_output=True, text=True
        )

    def test_a_clean_locale_set_exits_zero(self):
        result = self._run({"en": {"a.x": "A"}, "de": {"a.x": "A"}}, "--strict")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("All 2 locale files valid.", result.stdout)

    def test_a_parity_gap_passes_by_default_and_fails_under_strict(self):
        locales = {"en": {"a.x": "A", "b.y": "B"}, "de": {"a.x": "A"}}

        lenient = self._run(locales)
        self.assertEqual(lenient.returncode, 0, lenient.stdout)
        self.assertIn("WARNING: de.json: Missing 1 keys", lenient.stdout)

        strict = self._run(locales, "--strict")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("ERRORS:", strict.stdout)

    def test_failures_outside_strict_mode_are_headed_failures(self):
        result = self._run({"en": {"a.x": ""}})

        self.assertEqual(result.returncode, 1)
        self.assertIn("FAILURES:", result.stdout)
        self.assertIn("Empty value for key 'a.x'", result.stdout)

    def test_an_empty_directory_exits_nonzero(self):
        result = self._run({})

        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: No locale JSON files found", result.stdout)

    def test_a_directory_of_only_unparsable_files_exits_nonzero(self):
        result = self._run({"en": "{not json"})

        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR: No valid locale files", result.stdout)


class CommittedLocales(unittest.TestCase):
    def test_the_shipped_locale_files_pass_in_strict_mode(self):
        locales, errors, _ = validate.load_locales(SCRIPTS_DIR.parent)
        check_errors, _ = validate.check_locales(locales, strict=True)

        self.assertEqual(errors + check_errors, [])
        self.assertIn("en", locales)


if __name__ == "__main__":
    unittest.main()
