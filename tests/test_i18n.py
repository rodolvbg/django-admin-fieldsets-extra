import re
from pathlib import Path

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
    compiled = catalog.with_suffix(".mo")

    assert compiled.exists()
    assert compiled.stat().st_mtime >= catalog.stat().st_mtime


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
