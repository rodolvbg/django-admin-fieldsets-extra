"""Type aliases used across the package."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeAlias

from django.contrib.admin.options import InlineModelAdmin

#: A fieldset, as in ``ModelAdmin.fieldsets``: ``(name, options)``.
FieldsetSpec: TypeAlias = tuple[str | None, dict[str, Any]]
#: One entry of ``fieldsets_with_inlines``: a fieldset or an inline class.
LayoutEntry: TypeAlias = FieldsetSpec | type[InlineModelAdmin]
#: The whole ``fieldsets_with_inlines``.
Layout: TypeAlias = Sequence[LayoutEntry]

__all__ = ["FieldsetSpec", "Layout", "LayoutEntry"]
