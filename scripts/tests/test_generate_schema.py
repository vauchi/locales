#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the locale schema generator.

The schema this produces is what validate-schema.py enforces, so the
generator's output shape is the contract every locale file is held to.
"""

import json
import unittest

from scriptloader import SCRIPTS_DIR, load

generator = load("generate-schema.py")
schema_gate = load("validate-schema.py")
parity_gate = load("validate.py")

KEY_PATTERN = "^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_.]*$"


class RequiredKeys(unittest.TestCase):
    def test_every_translation_key_becomes_required(self):
        schema = generator.build_schema({"b.y": "B", "a.x": "A"})

        self.assertEqual(schema["required"], ["_meta", "a.x", "b.y"])

    def test_meta_is_required_and_not_listed_as_a_translation_key(self):
        schema = generator.build_schema({"_meta": {"locale": "en"}, "a.x": "A"})

        self.assertEqual(schema["required"], ["_meta", "a.x"])

    def test_translation_keys_are_sorted_regardless_of_input_order(self):
        shuffled = generator.build_schema({"z.z": "", "m.m": "", "a.a": ""})

        self.assertEqual(shuffled["required"], ["_meta", "a.a", "m.m", "z.z"])

    def test_an_english_file_with_only_meta_requires_only_meta(self):
        schema = generator.build_schema({"_meta": {"locale": "en"}})

        self.assertEqual(schema["required"], ["_meta"])


class SchemaShape(unittest.TestCase):
    def setUp(self):
        self.schema = generator.build_schema({"_meta": {}, "a.x": "A"})

    def test_the_document_is_a_closed_object(self):
        self.assertEqual(self.schema["type"], "object")
        self.assertIs(self.schema["additionalProperties"], False)

    def test_meta_is_a_closed_object_with_four_required_fields(self):
        meta = self.schema["properties"]["_meta"]

        self.assertEqual(
            meta["required"], ["locale", "name", "english_name", "is_rtl"]
        )
        self.assertIs(meta["additionalProperties"], False)
        self.assertEqual(meta["properties"]["is_rtl"]["type"], "boolean")

    def test_translation_values_must_be_non_empty_strings(self):
        value = self.schema["patternProperties"][KEY_PATTERN]

        self.assertEqual(value["type"], "string")
        self.assertEqual(value["minLength"], 1)

    def test_meta_is_the_only_declared_property(self):
        self.assertEqual(list(self.schema["properties"]), ["_meta"])


class Rendering(unittest.TestCase):
    def test_the_rendered_schema_is_indented_json_ending_in_a_newline(self):
        rendered = generator.render({"a": 1})

        self.assertEqual(rendered, '{\n  "a": 1\n}\n')

    def test_non_ascii_content_is_written_verbatim_not_escaped(self):
        rendered = generator.render({"name": "Español"})

        self.assertIn("Español", rendered)

    def test_the_rendered_schema_round_trips(self):
        schema = generator.build_schema({"_meta": {}, "a.x": "A"})

        self.assertEqual(json.loads(generator.render(schema)), schema)


class GeneratedSchemaAcceptsRealLocales(unittest.TestCase):
    """The generator's output is what every locale file is validated against."""

    def setUp(self):
        self.root = SCRIPTS_DIR.parent
        self.english = json.loads(
            (self.root / "en.json").read_text(encoding="utf-8")
        )
        self.generated = generator.build_schema(self.english)

    def test_the_committed_schema_is_what_the_generator_produces(self):
        committed = (self.root / "locales.schema.json").read_text(encoding="utf-8")

        self.assertEqual(generator.render(self.generated), committed)

    def test_every_shipped_locale_passes_basic_validation_against_it(self):
        errors, _ = schema_gate.basic_errors(
            schema_gate.locale_paths(self.root), self.generated
        )

        self.assertEqual(errors, [])

    @unittest.skipIf(
        schema_gate.jsonschema is None, "jsonschema is not installed"
    )
    def test_every_shipped_locale_matches_it_under_jsonschema(self):
        errors, _ = schema_gate.schema_errors(
            schema_gate.locale_paths(self.root), self.generated
        )

        self.assertEqual(errors, [])

    @unittest.skipIf(
        schema_gate.jsonschema is None, "jsonschema is not installed"
    )
    def test_a_well_named_key_absent_from_english_is_accepted_here(self):
        """Extra keys are the parity gate's job, not the schema's.

        patternProperties admits any dot-notation key, so the schema
        cannot see that one is missing from en.json — validate.py
        --strict is what reports it.
        """
        import jsonschema

        extra = dict(self.english)
        extra["not.in.english"] = "x"

        jsonschema.validate(instance=extra, schema=self.generated)

        _, warnings = parity_gate.check_locales(
            {"en": self.english, "de": extra}, strict=False
        )
        self.assertIn("de.json: 1 extra keys not in en.json", warnings)

    @unittest.skipIf(
        schema_gate.jsonschema is None, "jsonschema is not installed"
    )
    def test_a_badly_named_key_is_rejected_by_the_generated_schema(self):
        import jsonschema

        for bad_key in ("NotLowercase.x", "nodot", "9leading.digit", "a..x"):
            with self.subTest(key=bad_key):
                rogue = dict(self.english)
                rogue[bad_key] = "x"

                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(instance=rogue, schema=self.generated)


if __name__ == "__main__":
    unittest.main()
