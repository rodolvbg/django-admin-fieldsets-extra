"""FieldsetsExtraMixin: the layout, and the save buttons, one mixin each."""

from demo.admin import AuthorAdmin, BookInline
from demo.models import Author, Book
from django.contrib import admin
from django.test import SimpleTestCase

from django_admin_fieldsets_extra.mixins import (
    FieldsetSaveMixin,
    FieldsetsExtraMixin,
    FieldsetsLayoutMixin,
)
from tests.admin import DynamicAuthorAdmin, PlainBookAdmin

SCRIPT = "fieldsets_extra/js/fieldsets_extra.js"
STYLE = "fieldsets_extra/css/fieldsets_extra.css"


def media(admin_class, model=Author):
    return str(admin_class(model, admin.site).media)


class TestFeatures(SimpleTestCase):
    def test_the_mixin_is_both(self):
        assert issubclass(FieldsetsExtraMixin, FieldsetSaveMixin)
        assert issubclass(FieldsetsExtraMixin, FieldsetsLayoutMixin)

    def test_the_save_script_only_where_a_fieldset_has_a_button(self):
        # The demo's layout has a "save_button" fieldset.
        assert SCRIPT in media(AuthorAdmin)
        assert STYLE in media(AuthorAdmin)

        class NoButtonAdmin(FieldsetsExtraMixin, admin.ModelAdmin):
            fieldsets_with_inlines = [(None, {"fields": ["name"]}), BookInline]

        assert SCRIPT not in media(NoButtonAdmin)
        assert STYLE not in media(NoButtonAdmin)
        # Without a layout at all, the regular change form: none either.
        assert SCRIPT not in media(PlainBookAdmin, model=Book)

    def test_a_layout_per_request_may_have_buttons(self):
        assert SCRIPT in media(DynamicAuthorAdmin)

    def test_the_layout_alone(self):
        class LayoutAdmin(FieldsetsLayoutMixin, admin.ModelAdmin):
            fieldsets_with_inlines = [(None, {"fields": ["name"]}), BookInline]

        model_admin = LayoutAdmin(Author, admin.site)
        assert model_admin.inlines == [BookInline]
        assert SCRIPT not in str(model_admin.media)
