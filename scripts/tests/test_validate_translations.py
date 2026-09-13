#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the critical-translation gate.

This gate runs in the locales repo so that a broken string is caught
before it propagates to the consumer repos, which means a hole in it is
only visible downstream.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scriptloader import SCRIPTS_DIR, load

translations = load("validate-translations.py")

CRITICAL_KEYS = translations.CRITICAL_KEYS


def complete_locale(code: str, **overrides) -> dict:
    data: dict = {key: f"value for {key}" for key in CRITICAL_KEYS}
    data["_meta"] = {"locale": code}
    data.update(overrides)
    return data


class MetaLocaleAgreement(unittest.TestCase):
    def test_a_locale_code_disagreeing_with_its_filename_is_reported(self):
        errors = translations.check_meta_locale({"de": {"_meta": {"locale": "fr"}}})

        self.assertEqual(
            errors, ["de.json: _meta.locale is 'fr', expected 'de'"]
        )

    def test_an_agreeing_locale_code_is_accepted(self):
        self.assertEqual(
            translations.check_meta_locale({"de": {"_meta": {"locale": "de"}}}), []
        )

    def test_an_absent_meta_block_is_not_reported(self):
        self.assertEqual(translations.check_meta_locale({"de": {"nav.home": "X"}}), [])

    def test_an_empty_locale_code_is_not_reported(self):
        self.assertEqual(
            translations.check_meta_locale({"de": {"_meta": {"locale": ""}}}), []
        )

    def test_a_non_object_meta_block_is_skipped_rather_than_crashing(self):
        self.assertEqual(translations.check_meta_locale({"de": {"_meta": "oops"}}), [])


class CriticalKeys(unittest.TestCase):
    def test_a_complete_locale_is_summarized_not_reported(self):
        errors, summaries = translations.check_critical_keys(
            {"de": complete_locale("de")}
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            summaries,
            [f"  de.json: All {len(CRITICAL_KEYS)} critical keys present"],
        )

    def test_a_single_missing_key_is_reported_by_name(self):
        locale = complete_locale("de")
        del locale["error.generic"]

        errors, summaries = translations.check_critical_keys({"de": locale})

        self.assertEqual(
            errors, ["de.json: Missing 1 critical keys: error.generic"]
        )
        self.assertEqual(summaries, [])

    def test_at_most_five_missing_keys_are_named_before_an_ellipsis(self):
        errors, _ = translations.check_critical_keys({"de": {"_meta": {}}})

        self.assertEqual(
            errors,
            [
                f"de.json: Missing {len(CRITICAL_KEYS)} critical keys: "
                + ", ".join(CRITICAL_KEYS[:5])
                + "..."
            ],
        )

    def test_exactly_five_missing_keys_are_named_without_an_ellipsis(self):
        locale = complete_locale("de")
        for key in CRITICAL_KEYS[:5]:
            del locale[key]

        errors, _ = translations.check_critical_keys({"de": locale})

        self.assertEqual(
            errors,
            [
                "de.json: Missing 5 critical keys: "
                + ", ".join(CRITICAL_KEYS[:5])
            ],
        )
        self.assertNotIn("...", errors[0])


class KnownTranslations(unittest.TestCase):
    def test_an_expected_substring_present_is_accepted(self):
        self.assertEqual(
            translations.check_expected_translations(
                {
                    code: {**expected}
                    for code, expected in translations.EXPECTED_TRANSLATIONS.items()
                }
            ),
            [],
        )

    def test_an_overwritten_translation_is_reported_with_its_value(self):
        locales = {
            code: {**expected}
            for code, expected in translations.EXPECTED_TRANSLATIONS.items()
        }
        locales["de"]["welcome.title"] = "Hallo"

        errors = translations.check_expected_translations(locales)

        self.assertEqual(
            errors,
            [
                "de.json: 'welcome.title' = 'Hallo' — "
                "expected to contain 'Willkommen'"
            ],
        )

    def test_a_missing_key_is_reported_as_an_empty_value(self):
        locales = {
            code: {**expected}
            for code, expected in translations.EXPECTED_TRANSLATIONS.items()
        }
        del locales["fr"]["app.name"]

        errors = translations.check_expected_translations(locales)

        self.assertEqual(
            errors,
            ["fr.json: 'app.name' = '' — expected to contain 'Vauchi'"],
        )

    def test_an_absent_expected_locale_is_reported(self):
        errors = translations.check_expected_translations({})

        self.assertEqual(
            sorted(errors),
            sorted(
                f"{code}.json: Expected locale file not found"
                for code in translations.EXPECTED_TRANSLATIONS
            ),
        )

    def test_a_substring_match_accepts_a_longer_translation(self):
        locales = {
            code: {**expected}
            for code, expected in translations.EXPECTED_TRANSLATIONS.items()
        }
        locales["es"]["welcome.title"] = "Bienvenido a Vauchi"

        self.assertEqual(translations.check_expected_translations(locales), [])


class AllGatesTogether(unittest.TestCase):
    def test_a_sound_locale_set_produces_no_errors(self):
        locales = {
            code: complete_locale(code, **expected)
            for code, expected in translations.EXPECTED_TRANSLATIONS.items()
        }

        errors, summaries = translations.check_translations(locales)

        self.assertEqual(errors, [])
        self.assertEqual(len(summaries), len(locales))

    def test_findings_are_ordered_meta_then_critical_then_smoke(self):
        locales = {
            code: complete_locale(code, **expected)
            for code, expected in translations.EXPECTED_TRANSLATIONS.items()
        }
        locales["de"]["_meta"] = {"locale": "xx"}
        del locales["fr"]["error.generic"]
        locales["es"]["welcome.title"] = "Hola"

        errors, _ = translations.check_translations(locales)

        self.assertEqual(len(errors), 3)
        self.assertIn("_meta.locale", errors[0])
        self.assertIn("critical keys", errors[1])
        self.assertIn("expected to contain", errors[2])


class Loading(unittest.TestCase):
    def _root(self, **files) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name, data in files.items():
            payload = data if isinstance(data, str) else json.dumps(data)
            (root / f"{name}.json").write_text(payload, encoding="utf-8")
        return root

    def test_readable_files_are_parsed(self):
        root = self._root(en={"nav.home": "Home"})

        locales, errors = translations.load_locales(root)

        self.assertEqual(locales, {"en": {"nav.home": "Home"}})
        self.assertEqual(errors, [])

    def test_an_unparsable_file_is_reported_and_excluded(self):
        root = self._root(en={"nav.home": "Home"}, de="{not json")

        locales, errors = translations.load_locales(root)

        self.assertEqual(list(locales), ["en"])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("de.json: Invalid JSON — "))

    def test_the_schema_file_is_not_read_as_a_locale(self):
        root = self._root(en={"nav.home": "Home"})
        (root / "locales.schema.json").write_text("{}", encoding="utf-8")

        self.assertEqual(translations.locale_paths(root), [root / "en.json"])


class CommittedLocales(unittest.TestCase):
    def test_the_shipped_locale_files_pass_every_gate(self):
        locales, load_errors = translations.load_locales(SCRIPTS_DIR.parent)
        errors, summaries = translations.check_translations(locales)

        self.assertEqual(load_errors + errors, [])
        self.assertEqual(len(summaries), len(locales))

    def test_every_expected_locale_is_actually_shipped(self):
        locales, _ = translations.load_locales(SCRIPTS_DIR.parent)

        for code in translations.EXPECTED_TRANSLATIONS:
            self.assertIn(code, locales)


if __name__ == "__main__":
    unittest.main()
