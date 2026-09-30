import importlib
import sys

import pytest
from django.contrib import admin
from django.urls import reverse

pytest.importorskip("unfold")

from demo.models import Author  # noqa: E402

from django_admin_fieldsets_extra.contrib.unfold import (  # noqa: E402
    UnfoldFieldsetsExtraMixin,
)


def test_import_without_unfold_raises_helpful_error(monkeypatch):
    module = "django_admin_fieldsets_extra.contrib.unfold"
    monkeypatch.setitem(sys.modules, "unfold", None)
    monkeypatch.delitem(sys.modules, module, raising=False)

    with pytest.raises(ImportError, match=r"django-admin-fieldsets-extra\[unfold\]"):
        importlib.import_module(module)


def test_tabs_render_where_the_first_one_is(admin_client, author):
    url = reverse("unfold_admin:demo_author_change", args=[author.pk])
    html = admin_client.get(url).content.decode()

    # Both tabs, once, between "name" and the books inline.
    assert html.count("activeFieldsetTab = 'phone'") == 1
    assert html.count("activeFieldsetTab = 'biography'") == 1
    assert html.index('name="name"') < html.index("activeFieldsetTab = 'phone'")
    assert html.index("activeFieldsetTab = 'biography'") < html.index(
        'id="books-group"'
    )
    assert html.index('name="bio"') < html.index('id="books-group"')
    # The other fieldsets as usual, with their save button.
    assert html.index('id="books-group"') < html.index(">Save Contact</button>")
    assert "fieldsets_extra/css/contrib/unfold.css" in html


def test_save_works_on_unfold(admin_client, author):
    url = reverse("unfold_admin:demo_author_fieldset_save", args=[author.pk, 2])
    response = admin_client.post(url, {"email": "new@example.com"})

    assert b"fieldset-save-status-saved" in response.content
    author.refresh_from_db()
    assert author.email == "new@example.com"


def make_admin(layout):
    admin_class = type(
        "AuthorAdmin",
        (UnfoldFieldsetsExtraMixin, admin.ModelAdmin),
        {"fieldsets_with_inlines": layout},
    )
    return admin_class(Author, admin.AdminSite(name="check_unfold"))


def test_a_tab_cannot_have_a_save_button():
    tab = ("Bio", {"fields": ["bio"], "classes": ["tab"], "save_button": True})
    ids = [
        error.id for error in make_admin([(None, {"fields": ["name"]}), tab]).check()
    ]

    assert "admin_fieldsets_extra.E101" in ids


def test_checks_skip_what_other_checks_report():
    assert make_admin("nope").check()[0].id == "admin_fieldsets_extra.E001"
    ids = [error.id for error in make_admin([("x",)]).check()]
    assert "admin_fieldsets_extra.E101" not in ids
