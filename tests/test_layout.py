import re

import pytest
from demo.admin import ArticleInline, AuthorAdmin, BookInline
from demo.models import Author
from django.contrib import admin
from django.urls import reverse

from django_admin_fieldsets_extra.mixins import (
    FieldsetsExtraMixin,
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


def test_derived_fieldsets_and_inlines():
    assert AuthorAdmin.fieldsets == [
        (None, {"fields": ["name"]}),
        ("Contact", {"fields": ["email", "phone"]}),
        ("Biography", {"fields": ["bio"], "classes": ["collapse"]}),
    ]
    assert AuthorAdmin.inlines == [BookInline, ArticleInline]


def test_change_form_renders_in_layout_order(admin_client, author):
    url = reverse("admin:demo_author_change", args=[author.pk])
    html = admin_client.get(url).content.decode()

    assert order(html) == [
        "name",
        "books-group",
        "Contact",
        "articles-group",
        "Biography",
    ]
    # Inlines are rendered once, not also after the fieldsets.
    assert html.count('id="books-group"') == 1


def test_add_view_renders_in_layout_order(admin_client, db):
    html = admin_client.get(reverse("admin:demo_author_add")).content.decode()

    assert order(html)[:3] == ["name", "books-group", "Contact"]


def test_saving_the_whole_form_still_works(admin_client, author):
    book = author.books.get()
    article = author.articles.get()
    data = {
        "name": "Renamed",
        "email": "",
        "phone": "",
        "bio": "",
        "books-TOTAL_FORMS": "1",
        "books-INITIAL_FORMS": "1",
        "books-0-id": str(book.pk),
        "books-0-author": str(author.pk),
        "books-0-title": "Retitled",
        "articles-TOTAL_FORMS": "1",
        "articles-INITIAL_FORMS": "1",
        "articles-0-id": str(article.pk),
        "articles-0-author": str(author.pk),
        "articles-0-title": "An article",
    }
    url = reverse("admin:demo_author_change", args=[author.pk])
    response = admin_client.post(url, data)

    assert response.status_code == 302
    author.refresh_from_db()
    book.refresh_from_db()
    assert (author.name, book.title) == ("Renamed", "Retitled")


def test_dynamic_layout_and_hidden_inline(admin_client, author):
    url = reverse("test_admin:demo_author_change", args=[author.pk])
    html = admin_client.get(url).content.decode()

    # The inline without view permission is skipped, not left as a hole.
    assert order(html) == ["Contact", "name", "books-group"]
    assert 'id="articles-group"' not in html

    compact = admin_client.get(f"{url}?compact=1").content.decode()
    assert order(compact) == ["name", "books-group"]
    assert 'name="email"' in compact


def test_unlisted_fieldsets_and_inlines_are_appended(admin_user, rf, author):
    class Admin(FieldsetsExtraMixin, admin.ModelAdmin):
        fieldsets_with_inlines = [BookInline]

        def get_fieldsets(self, request, obj=None):
            return [(None, {"fields": ["name"]})]

        def get_inlines(self, request, obj):
            return [BookInline, ArticleInline]

    model_admin = Admin(Author, admin.AdminSite())
    request = rf.get("/")
    request.user = admin_user
    formsets, inline_instances = model_admin._create_formsets(
        request, author, change=True
    )
    inline_admin_formsets = model_admin.get_inline_formsets(
        request, formsets, inline_instances, author
    )
    adminform = admin.helpers.AdminForm(
        model_admin.get_form(request, author)(instance=author),
        model_admin.get_fieldsets(request, author),
        {},
    )
    items = model_admin.get_layout_items(
        request, author, adminform, inline_admin_formsets
    )

    assert [
        type(i.inline_admin_formset.opts).__name__ if i.is_inline else i.index
        for i in items
    ] == ["BookInline", 0, "ArticleInline"]


def test_without_a_layout_it_is_a_plain_model_admin(admin_client, author, rf):
    class Admin(FieldsetsExtraMixin, admin.ModelAdmin):
        inlines = [BookInline]

    model_admin = Admin(Author, admin.AdminSite())
    request = rf.get("/")

    assert model_admin.get_inlines(request, None) == [BookInline]
    assert model_admin.get_fieldsets(request, None) == [
        (None, {"fields": ["name", "email", "phone", "bio"]})
    ]
    assert model_admin.check() == []


def test_split_layout():
    assert split_layout([(None, {"fields": ["a"]}), BookInline]) == (
        [(None, {"fields": ["a"]})],
        [BookInline],
    )


def ids(**attrs):
    admin_class = type(
        "Admin",
        (FieldsetsExtraMixin, admin.ModelAdmin),
        {"__module__": __name__, **attrs},
    )
    return [error.id for error in admin_class(Author, admin.AdminSite()).check()]


def test_valid_layout_has_no_errors():
    assert ids(fieldsets_with_inlines=[(None, {"fields": ["name"]}), BookInline]) == []


@pytest.mark.parametrize(
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
def test_invalid_layout(attrs, error_id):
    assert error_id in ids(**attrs)


def test_admin_checks_run_on_derived_options():
    # Django's own fieldsets checks see the derived fieldsets.
    layout = [(None, {"fields": ["name"]}), ("Again", {"fields": ["name"]})]

    assert "admin.E012" in ids(fieldsets_with_inlines=layout)


def test_mixin_without_layout_renders_the_regular_form(admin_client, author):
    book = author.books.get()
    url = reverse("test_admin:demo_book_change", args=[book.pk])
    response = admin_client.get(url)

    assert response.status_code == 200
    assert "fieldsets_with_inlines" not in response.context
    assert 'name="title"' in response.content.decode()


def test_layout_with_more_fieldsets_than_the_form(admin_user, rf, author):
    class Admin(FieldsetsExtraMixin, admin.ModelAdmin):
        fieldsets_with_inlines = [
            (None, {"fields": ["name"]}),
            ("Gone", {"fields": ["email"]}),
        ]

    model_admin = Admin(Author, admin.AdminSite())
    request = rf.get("/")
    request.user = admin_user
    adminform = admin.helpers.AdminForm(
        model_admin.get_form(request, author)(instance=author),
        [(None, {"fields": ["name"]})],
        {},
    )

    items = model_admin.get_layout_items(request, author, adminform, [])
    assert [item.index for item in items] == [0]
