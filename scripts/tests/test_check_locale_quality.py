#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the locale quality gates.

Every gate in check-locale-quality.py guards a defect that reached main,
and every gate carries deliberate exemptions. Both halves are asserted
here: the defect is caught, and the exemption is not a false positive.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scriptloader import SCRIPTS_DIR, load

quality = load("check-locale-quality.py")


class LocaleDirectory:
    """A throwaway locale directory, written from keyword arguments."""

    def __init__(self, test_case, **locales):
        self._tmp = tempfile.TemporaryDirectory()
        test_case.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name)
        for code, strings in locales.items():
            (self.path / f"{code}.json").write_text(
                json.dumps(strings, ensure_ascii=False), encoding="utf-8"
            )

    def findings(self) -> list[str]:
        return quality.check(self.path)


class Placeholders(unittest.TestCase):
    def test_a_renamed_placeholder_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"greeting.hello": "Hello {name}"},
            de={"greeting.hello": "Hallo {nome}"},
        ).findings()

        self.assertEqual(
            findings,
            [
                "de.json: greeting.hello — placeholder mismatch: "
                "en=['name'] vs ['nome']"
            ],
        )

    def test_a_dropped_placeholder_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"cart.count": "{count} items"},
            de={"cart.count": "Artikel"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("placeholder mismatch: en=['count'] vs []", findings[0])

    def test_placeholder_order_does_not_matter(self):
        findings = LocaleDirectory(
            self,
            en={"transfer.line": "{from} to {to}"},
            de={"transfer.line": "nach {to} von {from}"},
        ).findings()

        self.assertEqual(findings, [])

    def test_placeholders_extracts_names_sorted_and_deduplicated_by_position(self):
        self.assertEqual(quality.placeholders("{b} {a} {b}"), ["a", "b", "b"])
        self.assertEqual(quality.placeholders("no placeholders here"), [])


class UntranslatedStrings(unittest.TestCase):
    LONG_ENGLISH = "Share your contact card safely"

    def test_a_verbatim_english_sentence_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"welcome.subtitle": self.LONG_ENGLISH},
            de={"welcome.subtitle": self.LONG_ENGLISH},
        ).findings()

        self.assertEqual(
            findings,
            [
                "de.json: welcome.subtitle — still English: "
                f"{self.LONG_ENGLISH!r}"
            ],
        )

    def test_a_translated_sentence_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"welcome.subtitle": self.LONG_ENGLISH},
            de={"welcome.subtitle": "Teile deine Kontaktkarte sicher"},
        ).findings()

        self.assertEqual(findings, [])

    def test_a_short_cognate_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"nav.section": "Open menu"},
            de={"nav.section": "Open menu"},
        ).findings()

        self.assertEqual(findings, [])

    def test_a_single_word_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"nav.navigation": "Navigationsleiste"},
            de={"nav.navigation": "Navigationsleiste"},
        ).findings()

        self.assertEqual(findings, [])

    def test_a_value_that_is_only_placeholders_and_punctuation_is_not_reported(self):
        template = "{group}: {status} — {detail}"

        findings = LocaleDirectory(
            self,
            en={"labels.summary": template},
            de={"labels.summary": template},
        ).findings()

        self.assertEqual(findings, [])

    def test_developer_facing_namespaces_are_exempt(self):
        for namespace in quality.TECHNICAL:
            with self.subTest(namespace=namespace):
                key = f"{namespace}diagnostic_report"
                findings = LocaleDirectory(
                    self,
                    en={key: self.LONG_ENGLISH},
                    de={key: self.LONG_ENGLISH},
                ).findings()

                self.assertEqual(findings, [])

    def test_a_key_allowed_for_every_locale_is_exempt(self):
        key = sorted(quality.UNTRANSLATED_ALLOW_ALL)[0]

        findings = LocaleDirectory(
            self,
            en={key: self.LONG_ENGLISH},
            de={key: self.LONG_ENGLISH},
        ).findings()

        self.assertEqual(findings, [])

    def test_a_key_allowed_for_one_locale_is_exempt_only_there(self):
        key = "contacts.count"
        self.assertIn(key, quality.UNTRANSLATED_ALLOW["fr"])

        exempt = LocaleDirectory(
            self,
            en={key: self.LONG_ENGLISH},
            fr={key: self.LONG_ENGLISH},
        ).findings()
        self.assertEqual(exempt, [])

        not_exempt = LocaleDirectory(
            self,
            en={key: self.LONG_ENGLISH},
            de={key: self.LONG_ENGLISH},
        ).findings()
        self.assertEqual(len(not_exempt), 1)
        self.assertIn("still English", not_exempt[0])


class GermanRegister(unittest.TestCase):
    """de is informal (du); formal address is the defect."""

    def test_a_formal_imperative_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"exchange.prompt": "Enter the code"},
            de={"exchange.prompt": "Geben Sie den Code ein"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is informal (du)", findings[0])
        self.assertIn("Geben Sie den Code ein", findings[0])

    def test_the_formal_dative_pronoun_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"sync.note": "We will tell you"},
            de={"sync.note": "Wir sagen Ihnen Bescheid"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is informal (du)", findings[0])

    def test_informal_address_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"exchange.prompt": "Enter the code"},
            de={"exchange.prompt": "Gib den Code ein"},
        ).findings()

        self.assertEqual(findings, [])

    def test_keys_where_sie_means_they_are_exempt(self):
        key = sorted(quality.REGISTER["de"]["allow"])[0]

        findings = LocaleDirectory(
            self,
            en={key: "They update automatically"},
            de={key: "Die Karten werden Ihnen automatisch gesendet"},
        ).findings()

        self.assertEqual(findings, [])


class SpanishRegister(unittest.TestCase):
    """es is informal (tú); usted and formal verbs are the defect."""

    def test_the_formal_pronoun_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"welcome.line": "Welcome back"},
            es={"welcome.line": "Bienvenido, usted ya tiene una cuenta"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is informal (tú)", findings[0])

    def test_a_formal_imperative_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"exchange.prompt": "Enter the code"},
            es={"exchange.prompt": "Introduzca el código"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is informal (tú)", findings[0])

    def test_a_third_person_verb_with_a_formal_possessive_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"card.done": "You customized your card"},
            es={"card.done": "Ha personalizado su tarjeta"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is informal (tú)", findings[0])

    def test_an_impersonal_third_person_verb_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"pin.rule": "Must be at least {min} characters"},
            es={"pin.rule": "Debe tener al menos {min} caracteres"},
        ).findings()

        self.assertEqual(findings, [])

    def test_informal_address_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"exchange.prompt": "Enter the code"},
            es={"exchange.prompt": "Escribe el código"},
        ).findings()

        self.assertEqual(findings, [])


class FrenchRegister(unittest.TestCase):
    """fr is formal (vous); informal address is the defect."""

    def test_an_informal_possessive_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"nav.menu": "Open your menu"},
            fr={"nav.menu": "Ouvrez ton menu"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is formal (vous)", findings[0])

    def test_formal_address_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"nav.menu": "Open your menu"},
            fr={"nav.menu": "Ouvrez votre menu"},
        ).findings()

        self.assertEqual(findings, [])

    def test_the_ambiguous_ta_is_deliberately_not_matched(self):
        findings = LocaleDirectory(
            self,
            en={"card.note": "We saved the card"},
            fr={"card.note": "Nous avons enregistré ta carte"},
        ).findings()

        self.assertEqual(findings, [])


class ItalianRegister(unittest.TestCase):
    """it is informal (tu); formal address is the defect."""

    def test_a_formal_pronoun_mid_line_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"sync.state": "Now you must confirm"},
            it={"sync.state": "Ora Lei deve confermare"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is informal (tu)", findings[0])

    def test_a_formal_imperative_is_reported(self):
        findings = LocaleDirectory(
            self,
            en={"exchange.prompt": "Enter the code"},
            it={"exchange.prompt": "Inserisca il codice"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("file is informal (tu)", findings[0])

    def test_an_impersonal_third_person_verb_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"pin.rule": "Must contain at least {min} characters"},
            it={"pin.rule": "Deve contenere almeno {min} caratteri"},
        ).findings()

        self.assertEqual(findings, [])

    def test_informal_address_is_not_reported(self):
        findings = LocaleDirectory(
            self,
            en={"exchange.prompt": "Enter the code"},
            it={"exchange.prompt": "Inserisci il codice"},
        ).findings()

        self.assertEqual(findings, [])

    def test_the_contact_capability_key_is_exempt(self):
        key = sorted(quality.REGISTER["it"]["allow"])[0]

        findings = LocaleDirectory(
            self,
            en={key: "Can propose contacts"},
            it={key: "Può proporre contatti"},
        ).findings()

        self.assertEqual(findings, [])


class SpanishPunctuation(unittest.TestCase):
    def test_a_question_mark_without_its_opening_pair_is_reported(self):
        findings = quality.check_spanish_punctuation(
            {"confirm.delete": "Seguro que quieres borrarlo?"}
        )

        self.assertEqual(
            findings,
            [
                "es.json: confirm.delete — '?' without '¿': "
                "'Seguro que quieres borrarlo?'"
            ],
        )

    def test_an_exclamation_without_its_opening_pair_is_reported(self):
        findings = quality.check_spanish_punctuation({"toast.saved": "Guardado!"})

        self.assertEqual(len(findings), 1)
        self.assertIn("'!' without '¡'", findings[0])

    def test_correctly_paired_punctuation_is_not_reported(self):
        findings = quality.check_spanish_punctuation(
            {
                "confirm.delete": "¿Seguro que quieres borrarlo?",
                "toast.saved": "¡Guardado!",
            }
        )

        self.assertEqual(findings, [])

    def test_each_line_is_paired_independently(self):
        findings = quality.check_spanish_punctuation(
            {"faq.answer": "¿Primera línea?\nSegunda línea?"}
        )

        self.assertEqual(len(findings), 1)
        self.assertIn("Segunda línea?", findings[0])

    def test_prose_without_either_mark_is_not_reported(self):
        findings = quality.check_spanish_punctuation({"note.plain": "Sin signos"})

        self.assertEqual(findings, [])

    def test_the_gate_runs_for_spanish_through_check(self):
        findings = LocaleDirectory(
            self,
            en={"confirm.delete": "Delete it"},
            es={"confirm.delete": "Borrarlo?"},
        ).findings()

        self.assertEqual(len(findings), 1)
        self.assertIn("'?' without '¿'", findings[0])

    def test_the_gate_does_not_run_for_other_locales(self):
        findings = LocaleDirectory(
            self,
            en={"confirm.delete": "Delete it"},
            de={"confirm.delete": "Löschen?"},
        ).findings()

        self.assertEqual(findings, [])


class SourceOfTruth(unittest.TestCase):
    def test_a_missing_english_file_is_the_only_finding(self):
        findings = LocaleDirectory(self, de={"nav.home": "Start"}).findings()

        self.assertEqual(
            findings, ["en.json missing — English is the source of truth"]
        )

    def test_english_itself_is_never_register_checked(self):
        findings = LocaleDirectory(
            self, en={"nav.menu": "Open your menu, tu, ton, tes"}
        ).findings()

        self.assertEqual(findings, [])

    def test_load_strips_meta_and_ignores_the_schema_file(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "en.json").write_text(
                json.dumps({"_meta": {"locale": "en"}, "nav.home": "Home"}),
                encoding="utf-8",
            )
            (root / "locales.schema.json").write_text("{}", encoding="utf-8")

            self.assertEqual(quality.load(root), {"en": {"nav.home": "Home"}})


class CommittedLocales(unittest.TestCase):
    def test_the_shipped_locale_files_pass_every_gate(self):
        self.assertEqual(quality.check(SCRIPTS_DIR.parent), [])


if __name__ == "__main__":
    unittest.main()
