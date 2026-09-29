import ast
import gettext
import re
from pathlib import Path
from typing import Any

import pytest
from django.urls import reverse
from django.utils import translation

LOCALE_DIR = Path(__file__).parent.parent / "src/django_admin_fieldsets_extra/locale"
CATALOGS = sorted(LOCALE_DIR.glob("*/LC_MESSAGES/django.po"))


def po_entries(path):
    """``([msgstr...], fuzzy)`` for every message of a .po file."""
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        if not re.search(r"^msgid ", block, re.M) or 'msgid ""\nmsgstr ""\n"' in block:
            continue
        yield (
            re.findall(r'^msgstr(?:\[\d+\])? "(.*)"$', block, re.M),
            "#, fuzzy" in block,
            block.splitlines()[-1],
        )


PO_LINE = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?) (".*")$')


def po_messages(path):
    """``{msgid: msgstr}`` (``{(msgid, n): msgstr}`` for plurals) of a .po file."""
    messages: dict[Any, str] = {}
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        fields: dict[str, str] = {}
        key = None
        for line in block.splitlines():
            match = PO_LINE.match(line)
            if match:
                key = match.group(1)
                fields[key] = ast.literal_eval(match.group(2))
            elif line.startswith('"') and key:
                fields[key] += ast.literal_eval(line)
        msgid = fields.get("msgid")
        if not msgid or "#, fuzzy" in block:
            continue
        if "msgctxt" in fields:
            msgid = f"{fields['msgctxt']}\x04{msgid}"
        if "msgid_plural" in fields:
            for name, value in fields.items():
                if name.startswith("msgstr["):
                    messages[(msgid, int(name[7:-1]))] = value
        else:
            messages[msgid] = fields["msgstr"]
    return messages


def mo_messages(path):
    """The same, from the compiled .mo (as Django will load it)."""
    with path.open("rb") as file:
        catalog = getattr(gettext.GNUTranslations(file), "_catalog")  # noqa: B009
    return {key: value for key, value in catalog.items() if key != ""}


def test_there_is_a_spanish_catalog():
    assert [c.parent.parent.name for c in CATALOGS] == ["es"]


@pytest.mark.parametrize("catalog", CATALOGS, ids=lambda c: c.parent.parent.name)
def test_every_message_is_translated(catalog):
    problems = [
        line
        for msgstrs, fuzzy, line in po_entries(catalog)
        if fuzzy or not all(s.strip() for s in msgstrs)
    ]
    assert problems == []


@pytest.mark.parametrize("catalog", CATALOGS, ids=lambda c: c.parent.parent.name)
def test_compiled_catalog_is_up_to_date(catalog):
    """The shipped .mo has exactly the .po's translations (not compared by
    date: a git checkout gives both files arbitrary modification times)."""
    compiled = catalog.with_suffix(".mo")

    assert compiled.exists()
    assert mo_messages(compiled) == po_messages(catalog)


def test_save_button_in_spanish(admin_client, author):
    url = reverse("admin:demo_author_change", args=[author.pk])
    with translation.override("es"):
        html = admin_client.get(url).content.decode()

    assert ">Guardar Contact</button>" in html
    assert 'title="Guarda solo esta sección.' in html
    assert 'data-fieldset-save-failed="No se pudieron guardar los cambios.' in html


def test_save_status_in_spanish(admin_client, author):
    url = reverse("admin:demo_author_fieldset_save", args=[author.pk, 1])
    with translation.override("es"):
        saved = admin_client.post(url, {"email": "a@example.com", "phone": ""})
        invalid = admin_client.post(url, {"email": "nope", "phone": ""})

    assert ">Guardado.</span>" in saved.content.decode()
    assert (
        "Por favor, corrija los errores detallados abajo." in invalid.content.decode()
    )
    assert "Introduzca una dirección de correo electrónico válida." in (
        invalid.content.decode()
    )
