"""Extras for Django admin fieldsets: layout with inlines, per-fieldset save."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django import forms
from django.contrib.admin.helpers import AdminForm, Fieldset, InlineAdminFormSet
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.admin.utils import flatten_fieldsets, quote
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, URLPattern, path, reverse
from django.utils.translation import gettext
from django.views.decorators.http import require_POST

from django_admin_fieldsets_extra.types import FieldsetSpec, Layout

if TYPE_CHECKING:
    from django.template.response import _TemplateForResponseT
    from typing_extensions import TypeIs


def is_inline(entry: object) -> TypeIs[type[InlineModelAdmin]]:
    return isinstance(entry, type) and issubclass(entry, InlineModelAdmin)


#: Fieldset options of this package; removed before Django sees them (its
#: ``Fieldset`` rejects unknown options).
LAYOUT_OPTIONS = frozenset({"save_button"})


def django_fieldset(
    entry: FieldsetSpec,
) -> FieldsetSpec:
    """A layout fieldset as Django expects it, without this package's options.

    Malformed entries are returned as they are, for the checks to report.
    """
    if not (isinstance(entry, list | tuple) and len(entry) == 2):
        return entry
    name, options = entry
    if not isinstance(options, dict) or not LAYOUT_OPTIONS & set(options):
        return entry
    return name, {k: v for k, v in options.items() if k not in LAYOUT_OPTIONS}


def split_layout(
    layout: Layout,
) -> tuple[list[FieldsetSpec], list[type[InlineModelAdmin]]]:
    """The fieldsets (Django-ready) and the inline classes of a layout."""
    fieldsets = [django_fieldset(entry) for entry in layout if not is_inline(entry)]
    inlines = [entry for entry in layout if is_inline(entry)]
    return fieldsets, inlines


@dataclass(frozen=True)
class LayoutItem:
    """What the change form renders at one position of the layout."""

    fieldset: Fieldset | None = None
    #: Position of the fieldset in ``get_fieldsets()`` (its id suffix).
    index: int | None = None
    inline_admin_formset: InlineAdminFormSet | None = None
    #: Endpoint of the fieldset's save button, if it has one.
    save_url: str | None = None
    save_label: str = ""

    @property
    def is_inline(self) -> bool:
        return self.inline_admin_formset is not None


class FieldsetsExtraMixin:
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
    """

    fieldsets_with_inlines: Layout = ()
    change_form_template: _TemplateForResponseT | None = (
        "admin/fieldsets_extra/change_form.html"
    )
    fieldset_save_response_template = "admin/fieldsets_extra/fieldset_response.html"
    _fieldsets_with_inlines_conflicts: list[str] = []

    # Provided by ModelAdmin.
    fieldsets: Any
    inlines: Any
    model: Any
    opts: Any
    admin_site: Any

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
    ) -> Layout:
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
        can_save = (
            obj is not None
            and obj.pk is not None
            and self.has_change_permission(request, obj)  # type: ignore[attr-defined]
        )
        items: list[LayoutItem] = []
        for entry in self.get_fieldsets_with_inlines(request, obj):
            if is_inline(entry):
                match = next((f for f in formsets if type(f.opts) is entry), None)
                if match is not None:
                    formsets.remove(match)
                    items.append(LayoutItem(inline_admin_formset=match))
            elif fieldsets:
                index, fieldset = fieldsets.pop(0)
                save_url = None
                if can_save and entry[1].get("save_button"):
                    save_url = self._fieldset_save_url(obj, index)
                items.append(
                    LayoutItem(
                        fieldset=fieldset,
                        index=index,
                        save_url=save_url,
                        save_label=self.get_fieldset_save_label(entry[0]),
                    )
                )
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

    # Saving a fieldset ----------------------------------------------------

    @property
    def media(self) -> forms.Media:
        return super().media + forms.Media(  # type: ignore[misc]
            js=["fieldsets_extra/js/fieldsets_extra.js"],
            css={"all": ["fieldsets_extra/css/fieldsets_extra.css"]},
        )

    def get_urls(self) -> list[URLPattern]:
        opts = self.model._meta
        return [
            path(
                "<path:object_id>/fieldsets/<int:index>/save/",
                self.admin_site.admin_view(self.fieldset_save_view),
                name=f"{opts.app_label}_{opts.model_name}_fieldset_save",
            ),
            *super().get_urls(),  # type: ignore[misc]
        ]

    def _fieldset_save_url(self, obj: Any, index: int) -> str | None:
        opts = self.model._meta
        try:
            return reverse(
                f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}"
                "_fieldset_save",
                args=[quote(obj.pk), index],
            )
        except NoReverseMatch:  # pragma: no cover - get_urls() was overridden
            return None

    def get_fieldset_save_label(self, name: str | None) -> str:
        """Text of a fieldset's save button."""
        if name:
            return gettext("Save %(name)s") % {"name": name}
        return gettext("Save")

    def fieldset_save_view(
        self, request: HttpRequest, object_id: str, index: int
    ) -> HttpResponse:
        return require_POST(self._fieldset_save)(request, object_id, index)

    def _fieldset_save(
        self, request: HttpRequest, object_id: str, index: int
    ) -> HttpResponse:
        request.current_app = self.admin_site.name
        obj = self.get_object(request, object_id)  # type: ignore[attr-defined]
        if obj is None:
            raise Http404
        if not self.has_change_permission(request, obj):  # type: ignore[attr-defined]
            raise PermissionDenied
        layout_fieldsets = [
            entry
            for entry in self.get_fieldsets_with_inlines(request, obj)
            if not is_inline(entry)
        ]
        if index >= len(layout_fieldsets) or not layout_fieldsets[index][1].get(
            "save_button"
        ):
            raise Http404("This fieldset has no save button.")
        name, options = django_fieldset(layout_fieldsets[index])
        readonly = list(self.get_readonly_fields(request, obj))  # type: ignore[attr-defined]
        fields = [
            field
            for field in flatten_fieldsets([(name, options)])  # type: ignore[list-item]
            if field not in readonly
        ]
        if not fields:
            raise Http404("This fieldset has no editable fields.")

        # Only this fieldset's fields, on the object as stored now: the rest
        # of the change form is neither submitted nor overwritten.
        form_class = self.get_form(request, obj, change=True, fields=fields)  # type: ignore[attr-defined]
        form = form_class(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            with transaction.atomic(using=router.db_for_write(self.model)):
                obj = self.save_form(request, form, change=True)  # type: ignore[attr-defined]
                self.save_model(request, obj, form, change=True)  # type: ignore[attr-defined]
                form.save_m2m()
                message = self.construct_change_message(request, form, [])  # type: ignore[attr-defined]
                if message:
                    self.log_change(request, obj, message)  # type: ignore[attr-defined]
            status, text = "saved", gettext("Saved.")
            non_field_errors = None
            form = form_class(instance=obj)
        else:
            status, text = "invalid", gettext("Please correct the errors below.")
            non_field_errors = form.non_field_errors()

        adminform = AdminForm(
            form,
            [(name, options)],
            {},
            readonly,
            model_admin=self,  # type: ignore[arg-type]
        )
        item = LayoutItem(
            fieldset=next(iter(adminform)),
            index=index,
            save_url=request.path,
            save_label=self.get_fieldset_save_label(name),
        )
        return TemplateResponse(
            request,
            self.fieldset_save_response_template,
            {
                "item": item,
                "status": status,
                "message": text,
                "non_field_errors": non_field_errors,
                "opts": self.opts,
                "original": obj,
                "change": True,
                "is_popup": False,
            },
        )

    def check(self, **kwargs: Any) -> list[Any]:
        from django_admin_fieldsets_extra.checks import (
            check_fieldsets_with_inlines,
        )

        return [*super().check(**kwargs), *check_fieldsets_with_inlines(self)]  # type: ignore[misc]


__all__ = [
    "LAYOUT_OPTIONS",
    "FieldsetsExtraMixin",
    "LayoutItem",
    "django_fieldset",
    "split_layout",
]
