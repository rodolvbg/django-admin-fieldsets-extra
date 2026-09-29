# django-admin-fieldsets-with-inlines

[![Build status](https://github.com/rodolvbg/django-admin-fieldsets-with-inlines/actions/workflows/pytest.yml/badge.svg)](https://github.com/rodolvbg/django-admin-fieldsets-with-inlines/actions/workflows/pytest.yml)
[![PyPI version](https://img.shields.io/pypi/v/django-admin-fieldsets-with-inlines.svg)](https://pypi.org/project/django-admin-fieldsets-with-inlines/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-admin-fieldsets-with-inlines)](https://pypi.org/project/django-admin-fieldsets-with-inlines/)
[![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-admin-fieldsets-with-inlines)](https://pypi.org/project/django-admin-fieldsets-with-inlines/)
[![Downloads](https://static.pepy.tech/personalized-badge/django-admin-fieldsets-with-inlines?period=month&units=international_system&left_color=black&right_color=blue&left_text=Downloads/month)](https://pepy.tech/project/django-admin-fieldsets-with-inlines)

Interleave fieldsets and inlines in the Django admin change form: put an
inline right after the fields it belongs with, instead of always at the
bottom.

![Books inline between the name and the contact fieldset, articles before the biography](docs/screenshots/hero.png)

- One ordered list replaces `fieldsets` + `inlines`.
- No copy of Django's `change_form.html`: it only overrides its
  `field_sets` / `inline_field_sets` blocks, so it follows your Django
  version.
- Nothing changes in the inlines' DOM: Django's inline JS ("Add another",
  autocomplete, date pickers…) and inline templates work as usual.
- Works with [django-admin-inline-controls](https://github.com/rodolvbg/django-admin-inline-controls)
  (paginated / filterable inlines, save buttons on inlines and fieldsets).

## Install

```bash
pip install django-admin-fieldsets-with-inlines
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "django_admin_fieldsets_with_inlines",
]
```

## Usage

```python
from django.contrib import admin

from django_admin_fieldsets_with_inlines.mixins import FieldsetsWithInlinesMixin


class BookInline(admin.TabularInline):
    model = Book


class ArticleInline(admin.StackedInline):
    model = Article


@admin.register(Author)
class AuthorAdmin(FieldsetsWithInlinesMixin, admin.ModelAdmin):
    fieldsets_with_inlines = [
        (None, {"fields": ["name"]}),
        BookInline,
        ("Contact", {"fields": ["email", "phone"]}),
        ArticleInline,
        ("Biography", {"fields": ["bio"], "classes": ["collapse"]}),
    ]
```

Each entry is either a fieldset, exactly as in `ModelAdmin.fieldsets`, or an
inline class, as in `ModelAdmin.inlines`. They are rendered in that order.

- **`fieldsets` and `inlines` are derived from it** (in their relative
  order), so Django's admin checks and every hook that reads them keep
  working. Don't set them as well (`admin_fieldsets_with_inlines.E003`).
- **Dynamic layouts:** override `get_fieldsets_with_inlines(request,
  obj=None)`; `get_fieldsets()` and `get_inlines()` follow it.
- **Permissions:** an inline the user can't see is simply left out, as
  in the regular change form.
- **Anything not in the layout** (e.g. extra fieldsets or inlines from your
  own `get_fieldsets()` / `get_inlines()`) is rendered after it.
- Without `fieldsets_with_inlines`, the mixin does nothing: the regular
  change form.

## Customizing the template

The mixin sets `change_form_template` to
`admin/fieldsets_with_inlines/change_form.html`, which extends
`admin/change_form.html`. For your own change form template, extend this
one instead:

```django
{% extends "admin/fieldsets_with_inlines/change_form.html" %}

{% block layout_inline %}
  <div class="my-inline">{{ block.super }}</div>
{% endblock %}
```

| Block | Contains |
|---|---|
| `field_sets` | The whole layout (falls back to Django's when there is none). |
| `layout_fieldset` | One fieldset (`fieldset`, and `item.index`, its position in `get_fieldsets()`). |
| `layout_inline` | One inline (`inline_admin_formset`). |
| `inline_field_sets` | Empty when there is a layout (the inlines are already rendered). |

The layout is also in the context as `fieldsets_with_inlines`: a list of
items with `is_inline`, `fieldset`, `index` and `inline_admin_formset`.
`get_layout_items()` builds it, if you need to change how the layout is
matched to the form.

## With django-admin-inline-controls

Both mixins go on the `ModelAdmin`, `InlineControlsAdminMixin` first:

```python
from django_admin_inline_controls.mixins import (
    InlineControlsAdminMixin,
    InlineControlsMixin,
)


class BookInline(InlineControlsMixin, admin.TabularInline):
    model = Book
    inline_per_page = 20
    inline_save_button = True


@admin.register(Author)
class AuthorAdmin(
    InlineControlsAdminMixin, FieldsetsWithInlinesMixin, admin.ModelAdmin
):
    fieldsets_with_inlines = [
        (None, {"fields": ["name"]}),
        BookInline,
        (
            "Contact",
            {"fields": ["email", "phone"], "classes": ["inline-controls-save"]},
        ),
    ]
```

Neither package knows about the other: the controls are part of each
inline's own template, and the fieldset save buttons are attached to
fieldsets by their class, wherever the layout puts them. Fieldsets keep
their position in `get_fieldsets()`, which is how the save endpoint finds
them.

## System checks

| ID | Problem |
|---|---|
| `admin_fieldsets_with_inlines.E001` | `fieldsets_with_inlines` is not a list or tuple. |
| `admin_fieldsets_with_inlines.E002` | An entry is neither a `(name, {"fields": ...})` fieldset nor an inline class. |
| `admin_fieldsets_with_inlines.E003` | `fieldsets` or `inlines` is set as well. |

## Demo

```bash
cd example
python manage.py migrate
python manage.py seed_demo      # admin/admin + an author with books
python manage.py runserver
```

## Compatibility

Django 4.2 – 6.1, Python 3.10+.

## License

MIT
