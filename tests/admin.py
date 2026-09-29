"""Test-only admin sites for options the demo doesn't use."""

from demo.models import Article, Author, Book
from django.contrib import admin

from django_admin_fieldsets_extra.mixins import FieldsetsExtraMixin

site = admin.AdminSite(name="test_admin")


class BookInline(admin.TabularInline):
    model = Book
    extra = 0


class ArticleInline(admin.TabularInline):
    model = Article
    extra = 0


class NoPermissionArticleInline(ArticleInline):
    def has_view_permission(self, request, obj=None):
        return False

    has_add_permission = has_change_permission = has_delete_permission = (
        has_view_permission
    )


@admin.register(Author, site=site)
class DynamicAuthorAdmin(FieldsetsExtraMixin, admin.ModelAdmin):
    """Layout chosen per request; an inline the user can't see."""

    def get_fieldsets_with_inlines(self, request, obj=None):
        if request.GET.get("compact"):
            return [(None, {"fields": ["name", "email"]}), BookInline]
        return [
            ("Contact", {"fields": ["email"]}),
            NoPermissionArticleInline,
            (None, {"fields": ["name"]}),
            BookInline,
        ]


try:
    from django_admin_inline_controls.mixins import (
        InlineControlsAdminMixin,
        InlineControlsMixin,
    )
except ImportError:  # django-admin-inline-controls is not installed
    controls_site = None
else:
    controls_site = admin.AdminSite(name="controls_admin")

    class ControlledBookInline(InlineControlsMixin, admin.TabularInline):
        model = Book
        extra = 0
        inline_per_page = 2
        inline_save_button = True

    @admin.register(Author, site=controls_site)
    class ControlledAuthorAdmin(
        InlineControlsAdminMixin, FieldsetsExtraMixin, admin.ModelAdmin
    ):
        fieldsets_with_inlines = [
            (None, {"fields": ["name"]}),
            ControlledBookInline,
            ("Contact", {"fields": ["email", "phone"], "save_button": True}),
            ("Biography", {"fields": ["bio"], "save_button": True}),
        ]


@admin.register(Book, site=site)
class PlainBookAdmin(FieldsetsExtraMixin, admin.ModelAdmin):
    """The mixin without a layout: the regular change form."""
