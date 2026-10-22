"""Extras for Django admin fieldsets: layout with inlines, per-fieldset save.

``FieldsetsExtraMixin`` puts them together; each one is a mixin of its own
(``FieldsetsLayoutMixin``, ``FieldsetSaveMixin``).
"""

from __future__ import annotations

from django_admin_fieldsets_extra.layout import (
    LAYOUT_OPTIONS,
    FieldsetsLayoutMixin,
    LayoutItem,
    django_fieldset,
    is_inline,
    split_layout,
)
from django_admin_fieldsets_extra.save import FieldsetSaveMixin


class FieldsetsExtraMixin(FieldsetSaveMixin):
    """Render inlines between fieldsets, in the order you list them::

        @admin.register(Author)
        class AuthorAdmin(FieldsetsExtraMixin, admin.ModelAdmin):
            fieldsets_with_inlines = [
                (None, {"fields": ["name"]}),
                BookInline,
                ("Contact", {"fields": ["email", "phone"], "save_button": True}),
                ArticleInline,
            ]

    ``fieldsets`` and ``inlines`` are derived from it, so the admin's own
    checks and hooks keep working; don't set them as well. A fieldset with
    ``"save_button": True`` gets a button that saves only its fields.

    It's ``FieldsetsLayoutMixin`` (the layout) and ``FieldsetSaveMixin``
    (the save buttons, whose script loads only where a fieldset has one).
    """


__all__ = [
    "LAYOUT_OPTIONS",
    "FieldsetSaveMixin",
    "FieldsetsExtraMixin",
    "FieldsetsLayoutMixin",
    "LayoutItem",
    "django_fieldset",
    "is_inline",
    "split_layout",
]
