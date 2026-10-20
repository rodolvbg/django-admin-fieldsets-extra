# System checks

| ID | Problem |
|---|---|
| `admin_fieldsets_extra.E001` | `fieldsets_with_inlines` is not a list or tuple. |
| `admin_fieldsets_extra.E002` | An entry is neither a `(name, {"fields": ...})` fieldset nor an inline class. |
| `admin_fieldsets_extra.E003` | `fieldsets` or `inlines` is set as well. |
| `admin_fieldsets_extra.E004` | A fieldset's `save_button` is not `True` or `False`. |
| `admin_fieldsets_extra.E101` | An Unfold tab fieldset (`"classes": ["tab"]`) has a `save_button` (`UnfoldFieldsetsExtraMixin`). |
| `admin_fieldsets_extra.W001` | `get_fieldsets_with_inlines()` is overridden and `fieldsets` or `inlines` is set too: they are ignored whenever it returns a layout (warning). |
