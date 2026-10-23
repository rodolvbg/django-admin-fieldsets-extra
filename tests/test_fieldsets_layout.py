import re

from demo.admin import ArticleInline, AuthorAdmin, BookInline
from demo.models import Article, Author, Book
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from unittest_parametrize import ParametrizedTestCase, parametrize

from django_admin_fieldsets_extra.mixins import (
    FieldsetSaveMixin,
    FieldsetsExtraMixin,
    FieldsetsLayoutMixin,
    split_layout,
)


def order(html):
    """The parent form's name field, named fieldsets (by heading) and inline
    groups, in page order. Unnamed fieldsets are ambiguous (stacked inlines
    have them) and heading ids only exist on Django 5.1+, hence the names."""
    pattern = re.compile(
        r"<h2[^>]*>\s*(Contact|Biography)\s*</h2>"
        r'|inline-group"\s+id="([\w-]+)-group"'
        r'|(name="name")'
    )
    found = []
    for match in pattern.finditer(html):
        if match.group(1) is not None:
            found.append(match.group(1))
        elif match.group(2) is not None:
            found.append(f"{match.group(2)}-group")
        else:
            found.append("name")
    return found


def ids(**attrs):
    admin_class = type(
        "Admin",
        (FieldsetsExtraMixin, admin.ModelAdmin),
        {"__module__": __name__, **attrs},
    )
    return [error.id for error in admin_class(Author, admin.AdminSite()).check()]


def hook_admin_ids(**attrs):
    def get_fieldsets_with_inlines(self, request, obj=None):
        return [(None, {"fields": ["name"]}), BookInline]

    return ids(get_fieldsets_with_inlines=get_fieldsets_with_inlines, **attrs)


class TestFieldsetsExtraMixin(TestCase):
    """Deriving and rendering the layout."""

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

    def test_derived_fieldsets_and_inlines(self):
        assert AuthorAdmin.fieldsets == [
            (None, {"fields": ["name"]}),
            ("Contact", {"fields": ["email", "phone"]}),
            ("Biography", {"fields": ["bio"], "classes": ["collapse"]}),
            ("Status", {"fields": ["active", "notes"]}),
        ]
        assert AuthorAdmin.inlines == [BookInline, ArticleInline]

    def test_change_form_renders_in_layout_order(self):
        url = reverse("admin:demo_author_change", args=[self.author.pk])
        html = self.client.get(url).content.decode()

        assert order(html) == [
            "name",
            "books-group",
            "Contact",
            "articles-group",
            "Biography",
        ]
        # Inlines are rendered once, not also after the fieldsets.
        assert html.count('id="books-group"') == 1

    def test_add_view_renders_in_layout_order(self):
        html = self.client.get(reverse("admin:demo_author_add")).content.decode()

        assert order(html)[:3] == ["name", "books-group", "Contact"]

    def test_saving_the_whole_form_still_works(self):
        book = self.author.books.get()
        article = self.author.articles.get()
        data = {
            "name": "Renamed",
            "email": "",
            "phone": "",
            "bio": "",
            "books-TOTAL_FORMS": "1",
            "books-INITIAL_FORMS": "1",
            "books-0-id": str(book.pk),
            "books-0-author": str(self.author.pk),
            "books-0-title": "Retitled",
            "articles-TOTAL_FORMS": "1",
            "articles-INITIAL_FORMS": "1",
            "articles-0-id": str(article.pk),
            "articles-0-author": str(self.author.pk),
            "articles-0-title": "An article",
        }
        url = reverse("admin:demo_author_change", args=[self.author.pk])
        response = self.client.post(url, data)

        assert response.status_code == 302
        self.author.refresh_from_db()
        book.refresh_from_db()
        assert (self.author.name, book.title) == ("Renamed", "Retitled")

    def test_dynamic_layout_and_hidden_inline(self):
        url = reverse("test_admin:demo_author_change", args=[self.author.pk])
        html = self.client.get(url).content.decode()

        # The inline without view permission is skipped, not left as a hole.
        assert order(html) == ["Contact", "name", "books-group"]
        assert 'id="articles-group"' not in html

        compact = self.client.get(f"{url}?compact=1").content.decode()
        assert order(compact) == ["name", "books-group"]
        assert 'name="email"' in compact

    def test_unlisted_fieldsets_and_inlines_are_appended(self):
        class Admin(FieldsetsExtraMixin, admin.ModelAdmin):
            fieldsets_with_inlines = [BookInline]

            def get_fieldsets(self, request, obj=None):
                return [(None, {"fields": ["name"]})]

            def get_inlines(self, request, obj):
                return [BookInline, ArticleInline]

        model_admin = Admin(Author, admin.AdminSite())
        request = RequestFactory().get("/")
        request.user = self.user
        formsets, inline_instances = model_admin._create_formsets(
            request, self.author, change=True
        )
        inline_admin_formsets = model_admin.get_inline_formsets(
            request, formsets, inline_instances, self.author
        )
        adminform = admin.helpers.AdminForm(
            model_admin.get_form(request, self.author)(instance=self.author),
            model_admin.get_fieldsets(request, self.author),
            {},
        )
        items = model_admin.get_layout_items(
            request, self.author, adminform, inline_admin_formsets
        )

        assert [
            type(i.inline_admin_formset.opts).__name__ if i.is_inline else i.index
            for i in items
        ] == ["BookInline", 0, "ArticleInline"]

    def test_without_a_layout_it_is_a_plain_model_admin(self):
        class Admin(FieldsetsExtraMixin, admin.ModelAdmin):
            inlines = [BookInline]

        model_admin = Admin(Author, admin.AdminSite())
        request = RequestFactory().get("/")

        assert model_admin.get_inlines(request, None) == [BookInline]
        assert model_admin.get_fieldsets(request, None) == [
            (None, {"fields": ["name", "email", "phone", "bio", "active", "notes"]})
        ]
        assert model_admin.check() == []

    def test_mixin_without_layout_renders_the_regular_form(self):
        book = self.author.books.get()
        url = reverse("test_admin:demo_book_change", args=[book.pk])
        response = self.client.get(url)

        assert response.status_code == 200
        assert "fieldsets_with_inlines" not in response.context
        assert 'name="title"' in response.content.decode()

    def test_layout_with_more_fieldsets_than_the_form(self):
        class Admin(FieldsetsExtraMixin, admin.ModelAdmin):
            fieldsets_with_inlines = [
                (None, {"fields": ["name"]}),
                ("Gone", {"fields": ["email"]}),
            ]

        model_admin = Admin(Author, admin.AdminSite())
        request = RequestFactory().get("/")
        request.user = self.user
        adminform = admin.helpers.AdminForm(
            model_admin.get_form(request, self.author)(instance=self.author),
            [(None, {"fields": ["name"]})],
            {},
        )

        items = model_admin.get_layout_items(request, self.author, adminform, [])
        assert [item.index for item in items] == [0]


class TestSplitLayout(SimpleTestCase):
    """split_layout()."""

    def test_split_layout(self):
        assert split_layout([(None, {"fields": ["a"]}), BookInline]) == (
            [(None, {"fields": ["a"]})],
            [BookInline],
        )


class TestLayoutChecks(ParametrizedTestCase, SimpleTestCase):
    """System checks of the layout (E001-E003, W001)."""

    def test_valid_layout_has_no_errors(self):
        assert (
            ids(fieldsets_with_inlines=[(None, {"fields": ["name"]}), BookInline]) == []
        )

    @parametrize(
        ("attrs", "error_id"),
        [
            ({"fieldsets_with_inlines": "name"}, "admin_fieldsets_extra.E001"),
            ({"fieldsets_with_inlines": [("x",)]}, "admin_fieldsets_extra.E002"),
            ({"fieldsets_with_inlines": [("x", {})]}, "admin_fieldsets_extra.E002"),
            ({"fieldsets_with_inlines": [object]}, "admin_fieldsets_extra.E002"),
            (
                {
                    "fieldsets_with_inlines": [(None, {"fields": ["name"]})],
                    "fieldsets": [(None, {"fields": ["name"]})],
                },
                "admin_fieldsets_extra.E003",
            ),
            (
                {
                    "fieldsets_with_inlines": [(None, {"fields": ["name"]})],
                    "inlines": [BookInline],
                },
                "admin_fieldsets_extra.E003",
            ),
        ],
    )
    def test_invalid_layout(self, attrs, error_id):
        assert error_id in ids(**attrs)

    def test_admin_checks_run_on_derived_options(self):
        # Django's own fieldsets checks see the derived fieldsets.
        layout = [(None, {"fields": ["name"]}), ("Again", {"fields": ["name"]})]

        assert "admin.E012" in ids(fieldsets_with_inlines=layout)

    @parametrize(
        "attrs",
        [
            {"fieldsets": [(None, {"fields": ["name"]})]},
            {"inlines": [BookInline]},
        ],
    )
    def test_hook_with_static_options_warns(self, attrs):
        assert "admin_fieldsets_extra.W001" in hook_admin_ids(**attrs)

    @parametrize(
        "attrs",
        [
            {},
            # fieldsets/inlines are derived from the attribute, not set by hand.
            {"fieldsets_with_inlines": [(None, {"fields": ["name"]}), BookInline]},
        ],
        ids=["hook_alone", "with_the_layout_attribute"],
    )
    def test_hook_without_static_options_does_not_warn(self, attrs):
        assert "admin_fieldsets_extra.W001" not in hook_admin_ids(**attrs)

    def test_inherited_static_options_warn_too(self):
        class Base(admin.ModelAdmin):
            fieldsets = [(None, {"fields": ["name"]})]

        class Admin(FieldsetsExtraMixin, Base):
            def get_fieldsets_with_inlines(self, request, obj=None):
                return [(None, {"fields": ["name"]})]

        ids_ = [e.id for e in Admin(Author, admin.AdminSite()).check()]
        assert "admin_fieldsets_extra.W001" in ids_


SCRIPT = "fieldsets_extra/js/fieldsets_extra.js"


class TestLayoutAndSave(SimpleTestCase):
    """The mixin is the layout and the save buttons; the layout works alone."""

    def test_the_mixin_is_both(self):
        assert issubclass(FieldsetsExtraMixin, FieldsetSaveMixin)
        assert issubclass(FieldsetsExtraMixin, FieldsetsLayoutMixin)

    def test_the_layout_alone(self):
        class LayoutAdmin(FieldsetsLayoutMixin, admin.ModelAdmin):
            fieldsets_with_inlines = [(None, {"fields": ["name"]}), BookInline]

        model_admin = LayoutAdmin(Author, admin.site)
        assert model_admin.inlines == [BookInline]
        assert SCRIPT not in str(model_admin.media)
