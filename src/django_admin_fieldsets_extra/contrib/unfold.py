"""django-unfold integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

try:
    import unfold  # noqa: F401
except ImportError as e:
    raise ImportError(
        "django_admin_fieldsets_extra.contrib.unfold requires django-unfold. "
        "Install it with: pip install django-admin-fieldsets-extra[unfold]"
    ) from e

from django import forms
from django.core import checks
from django.http import HttpRequest, HttpResponse

from django_admin_fieldsets_extra.mixins import FieldsetsExtraMixin, is_inline


def is_tab(options: Mapping[str, Any]) -> bool:
    """Whether a fieldset is one of Unfold's tabs (``"classes": ["tab"]``)."""
    return "tab" in options.get("classes", ())


class UnfoldFieldsetsExtraMixin(FieldsetsExtraMixin):
    """``FieldsetsExtraMixin`` for Unfold's ``ModelAdmin``::

        from unfold.admin import ModelAdmin

        @admin.register(Author)
        class AuthorAdmin(UnfoldFieldsetsExtraMixin, ModelAdmin):
            fieldsets_with_inlines = [...]

    Styles the save buttons with Unfold's colors (light and dark). Unfold's
    tab fieldsets (``"classes": ["tab"]``) are rendered as its tabs, where
    the first of them is in the layout.
    """

    change_form_template = "admin/fieldsets_extra/unfold/change_form.html"

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: Any = None,
    ) -> HttpResponse:
        # Position of the first tab fieldset: Unfold renders all its tabs there.
        context["fieldsets_extra_tabs_index"] = next(
            (
                index
                for index, (_, options) in enumerate(self.get_fieldsets(request, obj))
                if is_tab(options)
            ),
            None,
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    @property
    def media(self) -> forms.Media:
        return super().media + forms.Media(
            css={"all": ["fieldsets_extra/css/contrib/unfold.css"]},
        )

    def check(self, **kwargs: Any) -> list[Any]:
        errors = super().check(**kwargs)
        layout = self.fieldsets_with_inlines
        if not isinstance(layout, list | tuple):
            return errors  # reported by E001
        for index, entry in enumerate(layout):
            if is_inline(entry) or not (
                isinstance(entry, list | tuple)
                and len(entry) == 2
                and isinstance(entry[1], Mapping)
            ):
                continue
            if entry[1].get("save_button") and is_tab(entry[1]):
                errors.append(
                    checks.Error(
                        f"'{type(self).__qualname__}.fieldsets_with_inlines"
                        f"[{index}]' is one of Unfold's tabs, which can't have "
                        "a 'save_button'.",
                        obj=type(self),
                        id="admin_fieldsets_extra.E101",
                    )
                )
        return errors


__all__ = ["UnfoldFieldsetsExtraMixin"]
