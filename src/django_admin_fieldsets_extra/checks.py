"""System checks for ``FieldsetsExtraMixin``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core import checks

from django_admin_fieldsets_extra.mixins import is_inline


def check_fieldsets_with_inlines(model_admin: Any) -> list[checks.CheckMessage]:
    errors: list[checks.CheckMessage] = []
    name = type(model_admin).__qualname__
    layout = model_admin.fieldsets_with_inlines

    def error(msg: str, id: str) -> None:
        errors.append(checks.Error(msg, obj=type(model_admin), id=id))

    if not isinstance(layout, list | tuple):
        error(
            f"The value of '{name}.fieldsets_with_inlines' must be a list or tuple.",
            "admin_fieldsets_extra.E001",
        )
        return errors

    for index, entry in enumerate(layout):
        if is_inline(entry):
            continue
        if not (
            isinstance(entry, list | tuple)
            and len(entry) == 2
            and isinstance(entry[1], Mapping)
            and "fields" in entry[1]
        ):
            error(
                f"The value of '{name}.fieldsets_with_inlines[{index}]' must be a "
                "fieldset — a (name, {'fields': ...}) pair — or an inline class.",
                "admin_fieldsets_extra.E002",
            )
            continue
        save_button = entry[1].get("save_button", False)
        if not isinstance(save_button, bool):
            error(
                f"'save_button' in '{name}.fieldsets_with_inlines[{index}]' must "
                "be True or False.",
                "admin_fieldsets_extra.E004",
            )

    from django_admin_fieldsets_extra.mixins import FieldsetsExtraMixin

    hook_overridden = (
        type(model_admin).get_fieldsets_with_inlines
        is not FieldsetsExtraMixin.get_fieldsets_with_inlines
    )
    if hook_overridden:
        derived = model_admin._fieldsets_with_inlines_derived
        for option in ("fieldsets", "inlines"):
            if getattr(model_admin, option) and option not in derived:
                errors.append(
                    checks.Warning(
                        f"'{name}' overrides 'get_fieldsets_with_inlines()' and "
                        f"also sets '{option}', which is ignored whenever that "
                        "method returns a layout.",
                        hint=f"Remove '{option}', or return it from "
                        "get_fieldsets_with_inlines() when there is no layout.",
                        obj=type(model_admin),
                        id="admin_fieldsets_extra.W001",
                    )
                )

    for option in getattr(model_admin, "_fieldsets_with_inlines_conflicts", ()):
        error(
            f"'{name}' sets both 'fieldsets_with_inlines' and '{option}'; "
            f"'{option}' is derived from 'fieldsets_with_inlines', remove it.",
            "admin_fieldsets_extra.E003",
        )
    return errors
