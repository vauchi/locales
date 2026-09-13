#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the NFC normalization gate.

NFD strings compare unequal to their NFC twins, so a locale value typed
on macOS can silently fail a lookup on Linux. The gate exists to keep
that out of the committed files.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scriptloader import SCRIPTS_DIR, load

nfc = load("check-nfc.py")

ACCENTED_NFC = unicodedata.normalize("NFC", "Añadir café")
ACCENTED_NFD = unicodedata.normalize("NFD", "Añadir café")


def locale_file(test_case, payload: dict) -> str:
    tmp = tempfile.TemporaryDirectory()
    test_case.addCleanup(tmp.cleanup)
    path = Path(tmp.name) / "xx.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def run_check(path: str) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        errors = nfc.check_file(path)
    return errors, output.getvalue()


class NormalizedValues(unittest.TestCase):
    def test_an_nfc_value_is_accepted(self):
        errors, output = run_check(
            locale_file(self, {"contacts.add": ACCENTED_NFC})
        )

        self.assertEqual(errors, 0)
        self.assertEqual(output, "")

    def test_a_plain_ascii_value_is_accepted(self):
        errors, _ = run_check(locale_file(self, {"nav.home": "Home"}))

        self.assertEqual(errors, 0)

    def test_an_empty_file_is_accepted(self):
        errors, _ = run_check(locale_file(self, {}))

        self.assertEqual(errors, 0)


class DecomposedValues(unittest.TestCase):
    def test_an_nfd_value_is_reported_with_its_key(self):
        path = locale_file(self, {"contacts.add": ACCENTED_NFD})

        errors, output = run_check(path)

        self.assertEqual(errors, 1)
        self.assertIn("key 'contacts.add' is not NFC-normalized", output)

    def test_every_decomposed_value_is_counted(self):
        path = locale_file(
            self,
            {
                "a.one": ACCENTED_NFD,
                "a.two": ACCENTED_NFD,
                "a.three": ACCENTED_NFC,
            },
        )

        errors, output = run_check(path)

        self.assertEqual(errors, 2)
        self.assertNotIn("a.three", output)

    def test_a_decomposed_value_nested_one_level_is_reported_with_a_dotted_key(self):
        path = locale_file(self, {"_meta": {"name": ACCENTED_NFD}})

        errors, output = run_check(path)

        self.assertEqual(errors, 1)
        self.assertIn("key '_meta.name' is not NFC-normalized", output)

    def test_non_string_values_are_ignored(self):
        path = locale_file(
            self, {"_meta": {"is_rtl": False, "name": ACCENTED_NFC}}
        )

        errors, _ = run_check(path)

        self.assertEqual(errors, 0)


class CommandLine(unittest.TestCase):
    """The gate is invoked as `check-nfc.py *.json`, so drive it that way."""

    script = str(SCRIPTS_DIR / "check-nfc.py")

    def _run(self, *paths, env=None):
        return subprocess.run(
            [sys.executable, self.script, *paths],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_committed_locales_pass(self):
        locales = sorted(
            str(p)
            for p in SCRIPTS_DIR.parent.glob("*.json")
            if p.name != "locales.schema.json"
        )
        self.assertTrue(locales, "no locale files found to check")

        result = self._run(*locales)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("All locale strings are NFC", result.stdout)

    def test_a_decomposed_file_exits_nonzero(self):
        path = locale_file(self, {"contacts.add": ACCENTED_NFD})

        result = self._run(path)

        self.assertEqual(result.returncode, 1)
        self.assertIn("1 non-NFC string(s) found.", result.stdout)

    def test_no_arguments_reports_usage(self):
        result = self._run()

        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage: check-nfc.py", result.stdout)

    def test_accented_locales_are_read_under_a_non_utf8_locale(self):
        """CI containers commonly run with LC_ALL=C.

        Python then picks ASCII for `open()` without an explicit encoding,
        and the gate dies on the very accents it exists to inspect.
        """
        path = locale_file(self, {"contacts.add": ACCENTED_NFC})
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("LANG", "LC_CTYPE", "PYTHONUTF8")
        }
        env["LC_ALL"] = "C"
        env["PYTHONUTF8"] = "0"
        env["PYTHONCOERCECLOCALE"] = "0"

        result = self._run(path, env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("All locale strings are NFC", result.stdout)


if __name__ == "__main__":
    unittest.main()
