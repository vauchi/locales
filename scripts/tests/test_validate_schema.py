#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the schema conformance gate.

The gate has two validators: jsonschema when the library is installed,
and a hand-rolled fallback when it is not. CI installs jsonschema with a
trailing `|| true`, so the fallback is a real pipeline path and is
tested unconditionally; the jsonschema path is tested where available.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scriptloader import SCRIPTS_DIR, load

schema_gate = load("validate-schema.py")

SCHEMA = {
    "type": "object",
    "required": ["_meta", "a.x", "b.y"],
    "properties": {
        "_meta": {
            "type": "object",
            "required": ["locale", "name", "english_name", "is_rtl"],
            "properties": {
                "locale": {"type": "string"},
                "name": {"type": "string"},
                "english_name": {"type": "string"},
                "is_rtl": {"type": "boolean"},
            },
            "additionalProperties": False,
        }
    },
    "patternProperties": {
        "^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_.]*$": {"type": "string", "minLength": 1}
    },
    "additionalProperties": False,
}

META = {
    "locale": "en",
    "name": "English",
    "english_name": "English",
    "is_rtl": False,
}


def conforming(**overrides) -> dict:
    data = {"_meta": dict(META), "a.x": "A", "b.y": "B"}
    data.update(overrides)
    return data


class LocaleFiles:
    def __init__(self, test_case, **files):
        tmp = tempfile.TemporaryDirectory()
        test_case.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.paths = []
        for code, data in files.items():
            payload = data if isinstance(data, str) else json.dumps(data)
            path = self.root / f"{code}.json"
            path.write_text(payload, encoding="utf-8")
            self.paths.append(path)


class BasicValidation(unittest.TestCase):
    """The fallback that runs when jsonschema is absent."""

    def check(self, **files):
        return schema_gate.basic_errors(LocaleFiles(self, **files).paths, SCHEMA)

    def test_a_conforming_file_is_summarized_not_reported(self):
        errors, summaries = self.check(en=conforming())

        self.assertEqual(errors, [])
        self.assertEqual(summaries, ["  en.json: OK (3 keys)"])

    def test_a_missing_required_key_is_reported_by_name(self):
        errors, _ = self.check(en={"_meta": dict(META), "a.x": "A"})

        self.assertEqual(
            errors, ["en.json: Missing 1 required keys", "  - b.y"]
        )

    def test_at_most_five_missing_keys_are_listed_then_counted(self):
        big = dict(SCHEMA, required=["_meta"] + [f"k.{i:02d}" for i in range(9)])

        errors, _ = schema_gate.basic_errors(
            LocaleFiles(self, en={"_meta": dict(META)}).paths, big
        )

        self.assertEqual(errors[0], "en.json: Missing 9 required keys")
        self.assertEqual(errors[1:6], [f"  - k.{i:02d}" for i in range(5)])
        self.assertEqual(errors[6], "  ... and 4 more")

    def test_a_non_object_meta_is_reported(self):
        errors, _ = self.check(en=conforming(_meta="oops"))

        self.assertIn("en.json: _meta must be an object", errors)

    def test_each_missing_meta_field_is_reported(self):
        errors, _ = self.check(en=conforming(_meta={"locale": "en"}))

        for field in ("name", "english_name", "is_rtl"):
            self.assertIn(f"en.json: _meta.{field} is required", errors)
        self.assertNotIn("en.json: _meta.locale is required", errors)

    def test_an_absent_meta_block_is_not_reported_as_malformed(self):
        errors, _ = schema_gate.basic_errors(
            LocaleFiles(self, en={"a.x": "A", "b.y": "B"}).paths,
            dict(SCHEMA, required=["a.x", "b.y"]),
        )

        self.assertEqual(errors, [])

    def test_a_non_string_translation_is_reported_with_its_type(self):
        errors, _ = self.check(en=conforming(**{"a.x": 42}))

        self.assertIn("en.json: 'a.x' must be a string, got int", errors)

    def test_an_empty_translation_is_reported(self):
        errors, _ = self.check(en=conforming(**{"a.x": ""}))

        self.assertIn("en.json: 'a.x' must not be empty", errors)

    def test_a_whitespace_translation_is_accepted_here(self):
        """Blank-but-not-empty is the parity gate's job, not this one."""
        errors, _ = self.check(en=conforming(**{"a.x": " "}))

        self.assertEqual(errors, [])

    def test_an_unparsable_file_is_reported_and_not_summarized(self):
        errors, summaries = self.check(en="{not json")

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("en.json: Invalid JSON — "))
        self.assertEqual(summaries, [])

    def test_a_conforming_file_alongside_a_broken_one_is_still_summarized(self):
        errors, summaries = self.check(de="{not json", en=conforming())

        self.assertEqual(summaries, ["  en.json: OK (3 keys)"])
        self.assertEqual(len(errors), 1)


@unittest.skipIf(
    schema_gate.jsonschema is None, "jsonschema is not installed"
)
class JsonSchemaValidation(unittest.TestCase):
    def check(self, **files):
        return schema_gate.schema_errors(LocaleFiles(self, **files).paths, SCHEMA)

    def test_a_conforming_file_is_summarized_not_reported(self):
        errors, summaries = self.check(en=conforming())

        self.assertEqual(errors, [])
        self.assertEqual(summaries, ["  en.json: OK (3 keys)"])

    def test_a_missing_required_key_is_reported(self):
        errors, summaries = self.check(en={"_meta": dict(META), "a.x": "A"})

        self.assertEqual(len(errors), 1)
        self.assertIn("b.y", errors[0])
        self.assertEqual(summaries, [])

    def test_a_violation_inside_meta_is_reported_against_its_field_path(self):
        errors, _ = self.check(en=conforming(_meta={**META, "is_rtl": "no"}))

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("en.json: _meta.is_rtl — "))

    def test_a_root_level_violation_is_reported_against_root(self):
        errors, _ = self.check(en=conforming(**{"Not A Key": "x"}))

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("en.json: (root) — "))

    def test_an_unparsable_file_is_reported(self):
        errors, _ = self.check(en="{not json")

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("en.json: Invalid JSON — "))


class Reporting(unittest.TestCase):
    def _report(self, errors, summaries):
        output = io.StringIO()
        with redirect_stdout(output):
            code = schema_gate.report(errors, summaries, "BASIC VALIDATION", "all good")
        return code, output.getvalue()

    def test_no_errors_exits_zero_and_prints_the_success_line(self):
        code, output = self._report([], ["  en.json: OK (3 keys)"])

        self.assertEqual(code, 0)
        self.assertIn("  en.json: OK (3 keys)", output)
        self.assertIn("PASSED: all good", output)

    def test_errors_exit_nonzero_and_are_counted(self):
        code, output = self._report(["first", "second"], [])

        self.assertEqual(code, 1)
        self.assertIn("BASIC VALIDATION FAILED (2 error(s)):", output)
        self.assertIn("  - first", output)
        self.assertNotIn("PASSED", output)


class LocaleDiscovery(unittest.TestCase):
    def test_the_schema_file_is_not_validated_as_a_locale(self):
        files = LocaleFiles(self, en=conforming())
        (files.root / "locales.schema.json").write_text("{}", encoding="utf-8")

        self.assertEqual(
            schema_gate.locale_paths(files.root), [files.root / "en.json"]
        )

    def test_an_empty_directory_yields_nothing(self):
        files = LocaleFiles(self)

        self.assertEqual(schema_gate.locale_paths(files.root), [])


class CommittedLocales(unittest.TestCase):
    def setUp(self):
        root = SCRIPTS_DIR.parent
        self.paths = schema_gate.locale_paths(root)
        self.schema = json.loads(
            (root / "locales.schema.json").read_text(encoding="utf-8")
        )

    def test_the_shipped_locale_files_pass_basic_validation(self):
        errors, summaries = schema_gate.basic_errors(self.paths, self.schema)

        self.assertEqual(errors, [])
        self.assertEqual(len(summaries), len(self.paths))

    @unittest.skipIf(
        schema_gate.jsonschema is None, "jsonschema is not installed"
    )
    def test_the_shipped_locale_files_match_the_schema(self):
        errors, summaries = schema_gate.schema_errors(self.paths, self.schema)

        self.assertEqual(errors, [])
        self.assertEqual(len(summaries), len(self.paths))


if __name__ == "__main__":
    unittest.main()
