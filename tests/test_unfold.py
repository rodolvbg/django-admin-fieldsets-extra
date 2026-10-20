import importlib
import sys
from unittest import mock

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

pytest.importorskip("unfold")

from demo.models import Article, Author, Book  # noqa: E402

from django_admin_fieldsets_extra.contrib.unfold import (  # noqa: E402
    UnfoldFieldsetsExtraMixin,
)


def make_admin(layout):
    admin_class = type(
        "AuthorAdmin",
        (UnfoldFieldsetsExtraMixin, admin.ModelAdmin),
        {"fieldsets_with_inlines": layout},
    )
    return admin_class(Author, admin.AdminSite(name="check_unfold"))


class TestUnfoldFieldsetsExtraMixin(TestCase):
    """The Unfold layout, tabs and save buttons."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.author = Author.objects.create(name="Author")
        Book.objects.create(author=cls.author, title="A book")
        Article.objects.create(author=cls.author, title="An article")

    def setUp(self):
        self.client.force_login(self.user)

    def test_import_without_unfold_raises_helpful_error(self):
        module = "django_admin_fieldsets_extra.contrib.unfold"
        with mock.patch.dict(sys.modules):
            sys.modules["unfold"] = None
            sys.modules.pop(module, None)

            with self.assertRaisesRegex(
                ImportError, r"django-admin-fieldsets-extra\[unfold\]"
            ):
                importlib.import_module(module)

    def test_tabs_render_where_the_first_one_is(self):
        url = reverse("unfold_admin:demo_author_change", args=[self.author.pk])
        html = self.client.get(url).content.decode()

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

    def test_save_works_on_unfold(self):
        url = reverse(
            "unfold_admin:demo_author_fieldset_save", args=[self.author.pk, 2]
        )
        response = self.client.post(url, {"email": "new@example.com"})

        assert b"fieldset-save-status-saved" in response.content
        self.author.refresh_from_db()
        assert self.author.email == "new@example.com"


class TestUnfoldChecks(SimpleTestCase):
    """System check E101."""

    def test_a_tab_cannot_have_a_save_button(self):
        tab = ("Bio", {"fields": ["bio"], "classes": ["tab"], "save_button": True})
        ids = [
            error.id
            for error in make_admin([(None, {"fields": ["name"]}), tab]).check()
        ]

        assert "admin_fieldsets_extra.E101" in ids

    def test_checks_skip_what_other_checks_report(self):
        assert make_admin("nope").check()[0].id == "admin_fieldsets_extra.E001"
        ids = [error.id for error in make_admin([("x",)]).check()]
        assert "admin_fieldsets_extra.E101" not in ids
