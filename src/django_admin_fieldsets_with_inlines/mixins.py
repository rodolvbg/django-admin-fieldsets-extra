"""Interleave fieldsets and inlines in the Django admin change form."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib.admin.helpers import Fieldset, InlineAdminFormSet
from django.contrib.admin.options import InlineModelAdmin
from django.http import HttpRequest, HttpResponse

if TYPE_CHECKING:
    from django.template.response import _TemplateForResponseT

#: One entry of ``fieldsets_with_inlines``: a fieldset, as in
#: ``ModelAdmin.fieldsets``, or an inline class, as in ``ModelAdmin.inlines``.
LayoutEntry = tuple[str | None, dict[str, Any]] | type[InlineModelAdmin]


def is_inline(entry: Any) -> bool:
    return isinstance(entry, type) and issubclass(entry, InlineModelAdmin)


def split_layout(
    layout: Sequence[Any],
) -> tuple[list[tuple[str | None, dict[str, Any]]], list[type[InlineModelAdmin]]]:
    """The fieldsets and the inline classes of a layout, each in order."""
    fieldsets = [entry for entry in layout if not is_inline(entry)]
    inlines = [entry for entry in layout if is_inline(entry)]
    return fieldsets, inlines


@dataclass(frozen=True)
class LayoutItem:
    """What the change form renders at one position of the layout."""

    fieldset: Fieldset | None = None
    #: Position of the fieldset in ``get_fieldsets()`` (its id suffix).
    index: int | None = None
    inline_admin_formset: InlineAdminFormSet | None = None

    @property
    def is_inline(self) -> bool:
        return self.inline_admin_formset is not None


class FieldsetsWithInlinesMixin:
    """Render inlines between fieldsets, in the order you list them::

        @admin.register(Author)
        class AuthorAdmin(FieldsetsWithInlinesMixin, admin.ModelAdmin):
            fieldsets_with_inlines = [
                (None, {"fields": ["name"]}),
                BookInline,
                ("Contact", {"fields": ["email", "phone"]}),
                ArticleInline,
            ]

    ``fieldsets`` and ``inlines`` are derived from it, so the admin's own
    checks and hooks keep working; don't set them as well.
    """

    fieldsets_with_inlines: Sequence[Any] = ()
    change_form_template: _TemplateForResponseT | None = (
        "admin/fieldsets_with_inlines/change_form.html"
    )
    _fieldsets_with_inlines_conflicts: list[str] = []

    # Provided by ModelAdmin.
    fieldsets: Any
    inlines: Any

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        layout = cls.__dict__.get("fieldsets_with_inlines")
        if not layout or isinstance(layout, str):
            return
        # Checked by check_fieldsets_with_inlines() (E003).
        cls._fieldsets_with_inlines_conflicts = [
            name for name in ("fieldsets", "inlines") if cls.__dict__.get(name)
        ]
        try:
            fieldsets, inlines = split_layout(layout)
        except TypeError:  # pragma: no cover - not iterable, reported by E001
            return
        if not cls.__dict__.get("fieldsets"):
            cls.fieldsets = fieldsets
        if not cls.__dict__.get("inlines"):
            cls.inlines = inlines

    def get_fieldsets_with_inlines(
        self, request: HttpRequest, obj: Any = None
    ) -> Sequence[Any]:
        """The layout for this request. Override to make it dynamic."""
        return self.fieldsets_with_inlines

    def get_fieldsets(self, request: HttpRequest, obj: Any = None) -> Any:
        layout = self.get_fieldsets_with_inlines(request, obj)
        if not layout:
            return super().get_fieldsets(request, obj)  # type: ignore[misc]
        return split_layout(layout)[0]

    def get_inlines(self, request: HttpRequest, obj: Any) -> Any:
        layout = self.get_fieldsets_with_inlines(request, obj)
        if not layout:
            return super().get_inlines(request, obj)  # type: ignore[misc]
        return split_layout(layout)[1]

    def get_layout_items(
        self,
        request: HttpRequest,
        obj: Any,
        adminform: Any,
        inline_admin_formsets: Sequence[InlineAdminFormSet],
    ) -> list[LayoutItem]:
        """Pair the layout with what the change view built.

        Fieldsets are matched by position and inlines by class; inlines the
        user can't see are skipped. Anything the layout doesn't mention
        (e.g. from overridden ``get_fieldsets()`` / ``get_inlines()``) is
        appended at the end, as the admin would render it.
        """
        fieldsets = list(enumerate(adminform))
        formsets = list(inline_admin_formsets)
        items: list[LayoutItem] = []
        for entry in self.get_fieldsets_with_inlines(request, obj):
            if is_inline(entry):
                match = next((f for f in formsets if type(f.opts) is entry), None)
                if match is not None:
                    formsets.remove(match)
                    items.append(LayoutItem(inline_admin_formset=match))
            elif fieldsets:
                index, fieldset = fieldsets.pop(0)
                items.append(LayoutItem(fieldset=fieldset, index=index))
        items.extend(LayoutItem(fieldset=f, index=i) for i, f in fieldsets)
        items.extend(LayoutItem(inline_admin_formset=f) for f in formsets)
        return items

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: Any = None,
    ) -> HttpResponse:
        if self.get_fieldsets_with_inlines(request, obj):
            context["fieldsets_with_inlines"] = self.get_layout_items(
                request,
                obj,
                context["adminform"],
                context["inline_admin_formsets"],
            )
        return super().render_change_form(  # type: ignore[misc]
            request, context, add, change, form_url, obj
        )

    def check(self, **kwargs: Any) -> list[Any]:
        from django_admin_fieldsets_with_inlines.checks import (
            check_fieldsets_with_inlines,
        )

        return [*super().check(**kwargs), *check_fieldsets_with_inlines(self)]  # type: ignore[misc]


__all__ = ["FieldsetsWithInlinesMixin", "LayoutItem", "split_layout"]
