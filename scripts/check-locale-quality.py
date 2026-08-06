#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mattia Egloff <mattia.egloff@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Locale quality gates that key parity and JSON validity cannot catch.

Each check exists because the corresponding defect reached main:

  placeholder  a translation that drops {count} ships a broken string
  untranslated 112 keys sat in every locale as verbatim English
  register     formal/informal address mixed within one file
  punctuation  47 Spanish keys were missing their opening ¿ / ¡

Register is checked in three layers because address is carried three
different ways, and each layer was discovered only after the previous
one was believed complete:

  1. pronouns             Sie / usted / tu / Lei
  2. imperative verbs     "Geben Sie" / "Introduzca" / "Inserisca"
  3. indicative verbs     "Ha personalizado" / "Ora ha" / "vedrà"

Usage:  check-locale-quality.py [locale-dir]
Exit 1 on any finding. Intended for both the pre-commit hook and CI.
"""
import json
import re
import sys
from pathlib import Path

# Keys whose English is genuinely reused verbatim, not a missing translation.
UNTRANSLATED_ALLOW = {
    # "Contacts"/"contacts" and "Toast" are spelled identically in these
    # languages, so matching English is the correct translation.
    "fr": {
        "labels.detail.contacts_count",
        "privacy.delete.contacts_title",
        "contacts.count",
        "tags_list.member_count_plural",
    },
}

# Spelled identically in every target language, so matching English here is
# the correct translation rather than a missing one.
UNTRANSLATED_ALLOW_ALL = {"a11y.toast_prefix"}

# Namespaces that are developer-facing output, not user-facing copy.
TECHNICAL = ("cli.", "bluetooth.", "audio.", "app.", "ble.", "nfc.", "diag.")

# A shorter string is usually a cognate ("Navigation", "Privacy"), not a miss.
UNTRANSLATED_MIN_CHARS = 16

REGISTER = {
    "de": {
        "form": "informal (du)",
        "wrong": (
            r"\b[A-ZÄÖÜ][a-zäöüß]{2,} Sie\b"  # formal imperative: "Geben Sie"
            r"|\bIhnen\b"
        ),
        # 'Sie' here means 'they' — the changes, the contacts, your contacts.
        "allow": {
            "faq.offline_updates.answer",
            "faq.phone_lost.answer",
            "recovery.proof_submitted_detail",
        },
    },
    "es": {
        "form": "informal (tú)",
        "wrong": (
            r"\busted\w*\b"
            r"|\b(Introduzca|Pegue|Seleccione|Escanee|Toque|Abra|Verifique|Elija"
            r"|Comparta|Vaya|Cree|Genere|Pida|Descargue|Solicite|Añada|Modifique"
            r"|Entregue|Desvincule|Permita|Compare|Asegúrese|Reúnase)\b"
            # Third-person verb ALONE is ambiguous: "Debe tener al menos {min}"
            # is impersonal, not formal address. Require a formal possessive in
            # the same string, which is what "Ha personalizado su tarjeta" and
            # "Puede encontrar el contacto en su lista" both carry.
            r"|^(Ha|Puede|Debe|Tiene|Verá|Podrá|Deberá|Necesita|Recibirá)\b(?=.*\bsus?\b)"
        ),
        "allow": set(),
    },
    "fr": {
        "form": "formal (vous)",
        # Bare 'ta'/'te' collide with common nouns; 'tu|ton|tes' are unambiguous.
        "wrong": r"\b(tu|ton|tes)\b",
        "allow": set(),
    },
    "it": {
        "form": "informal (tu)",
        "wrong": (
            r"(?<!^)\b(Lei|Suo|Sua|Suoi|Sue)\b"
            r"|\b(Inserisca|Incolli|Scansioni|Selezioni|Tocchi|Verifichi|Scelga"
            r"|Condivida|Vada|Crei|Chieda|Incontri|Consegni|Prema|Gestisca"
            r"|Aggiunga|Personalizzi|Controlli|Apra|Generi|Avvii)\b"
            # Same caveat as Spanish: "Deve contenere almeno {min}" is
            # impersonal. Require a formal possessive alongside the verb.
            r"|^(Ha|Può|Deve|Vedrà|Avrà|Riceverà|Potrà|Dovrà)\b(?=.*\bSu[aoei]\b)"
        ),
        # "Può proporre contatti" describes the contact's capability, not the
        # user — third person is correct here.
        "allow": {"contact_detail.can_propose_contacts_label"},
    },
}


def placeholders(text: str) -> list[str]:
    return sorted(re.findall(r"\{(\w+)\}", text))


def load(directory: Path) -> dict[str, dict[str, str]]:
    locales = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "locales.schema.json":
            continue
        blob = json.loads(path.read_text(encoding="utf-8"))
        blob.pop("_meta", None)
        locales[path.stem] = blob
    return locales


def check_spanish_punctuation(strings: dict[str, str]) -> list[str]:
    """Spanish opens questions and exclamations, not just closes them."""
    findings = []
    for key, value in strings.items():
        for line in value.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if "?" in stripped and "¿" not in stripped:
                findings.append(f"es.json: {key} — '?' without '¿': {stripped[:60]!r}")
            if "!" in stripped and "¡" not in stripped:
                findings.append(f"es.json: {key} — '!' without '¡': {stripped[:60]!r}")
    return findings


def check(directory: Path) -> list[str]:
    locales = load(directory)
    english = locales.get("en")
    if english is None:
        return ["en.json missing — English is the source of truth"]

    findings: list[str] = []
    for code, strings in sorted(locales.items()):
        if code == "en":
            continue
        allow_untranslated = UNTRANSLATED_ALLOW.get(code, set()) | UNTRANSLATED_ALLOW_ALL

        for key, value in strings.items():
            source = english.get(key, "")

            if placeholders(value) != placeholders(source):
                findings.append(
                    f"{code}.json: {key} — placeholder mismatch: "
                    f"en={placeholders(source)} vs {placeholders(value)}"
                )

            # A value that is only placeholders and punctuation ("{group}:
            # {status}") has no prose to translate, so matching English is
            # correct rather than a miss.
            prose = re.sub(r"\{\w+\}", "", value).strip(" :()[]{}—-·|/,.")

            if (
                value == source
                and " " in value.strip()
                and len(value) >= UNTRANSLATED_MIN_CHARS
                and len(prose) >= 4
                and not key.startswith(TECHNICAL)
                and key not in allow_untranslated
            ):
                findings.append(f"{code}.json: {key} — still English: {value[:55]!r}")

        rule = REGISTER.get(code)
        if rule is not None:
            for key, value in strings.items():
                if key in rule["allow"]:
                    continue
                if re.search(rule["wrong"], value, re.MULTILINE):
                    findings.append(
                        f"{code}.json: {key} — file is {rule['form']}, "
                        f"found: {value[:55]!r}"
                    )

        if code == "es":
            findings.extend(check_spanish_punctuation(strings))

    return findings


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    findings = check(directory)
    if not findings:
        print("Locale quality checks passed.")
        return 0

    for finding in findings[:40]:
        print(f"  {finding}")
    if len(findings) > 40:
        print(f"  ... and {len(findings) - 40} more")
    print()
    print(f"FAILED — {len(findings)} locale quality issue(s).")
    print("Each check maps to a defect that previously reached main; see the")
    print("module docstring for what each one is guarding against.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
