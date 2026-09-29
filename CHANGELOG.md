# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added

- `FieldsetsWithInlinesMixin`: `fieldsets_with_inlines` renders fieldsets
  and inlines interleaved, deriving `fieldsets` and `inlines`;
  `get_fieldsets_with_inlines()` for dynamic layouts.
- Change form template overriding only Django's `field_sets` and
  `inline_field_sets` blocks, with `layout_fieldset` / `layout_inline`
  blocks.
- `"save_button": True` on a layout fieldset: a button that saves only its
  fields, re-rendering the fieldset in place.
- System checks.
