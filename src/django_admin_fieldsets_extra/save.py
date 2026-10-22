"""A button that saves only one fieldset's fields."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from django import forms
from django.contrib.admin.helpers import AdminForm, Fieldset
from django.contrib.admin.utils import flatten_fieldsets, quote
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import NoReverseMatch, URLPattern, path, reverse
from django.utils.translation import gettext
from django.views.decorators.http import require_POST

from .layout import FieldsetsLayoutMixin, LayoutItem, django_fieldset, is_inline

if TYPE_CHECKING:
    from django_admin_fieldsets_extra.types import FieldsetSpec


class FieldsetSaveMixin(FieldsetsLayoutMixin):
    """A fieldset of the layout with ``"save_button": True`` gets a button
    that saves only its fields, and answers with the fieldset re-rendered."""

    fieldset_save_response_template = "admin/fieldsets_extra/fieldset_response.html"

    @property
    def uses_fieldset_save(self) -> bool:
        """Whether any fieldset may have a save button: one in
        ``fieldsets_with_inlines`` has, or the layout is decided per
        request (``get_fieldsets_with_inlines()`` overridden)."""
        if (
            type(self).get_fieldsets_with_inlines
            is not FieldsetsLayoutMixin.get_fieldsets_with_inlines
        ):
            return True
        return any(
            not is_inline(entry)
            and isinstance(entry, list | tuple)
            and len(entry) == 2
            and isinstance(entry[1], dict)
            and entry[1].get("save_button")
            for entry in self.fieldsets_with_inlines or ()
        )

    @property
    def media(self) -> forms.Media:
        media = super().media  # type: ignore[misc]
        if self.uses_fieldset_save:
            media += forms.Media(
                js=["fieldsets_extra/js/fieldsets_extra.js"],
                css={"all": ["fieldsets_extra/css/fieldsets_extra.css"]},
            )
        return media

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

    def get_fieldset_layout_item(
        self,
        request: HttpRequest,
        obj: Any,
        entry: FieldsetSpec,
        index: int,
        fieldset: Fieldset,
    ) -> LayoutItem:
        item = super().get_fieldset_layout_item(request, obj, entry, index, fieldset)
        save_url = None
        if (
            obj is not None
            and obj.pk is not None
            and entry[1].get("save_button")
            and self.has_change_permission(request, obj)  # type: ignore[attr-defined]
        ):
            save_url = self._fieldset_save_url(obj, index)
        return dataclasses.replace(
            item, save_url=save_url, save_label=self.get_fieldset_save_label(entry[0])
        )

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
