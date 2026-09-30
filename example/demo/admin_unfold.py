"""The demo's admin on an Unfold site (see ``example.settings_unfold``)."""

from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.sites import UnfoldAdminSite

from django_admin_fieldsets_extra.contrib.unfold import UnfoldFieldsetsExtraMixin

from . import admin as demo
from .models import Author

site = UnfoldAdminSite(name="admin")


class BookInline(TabularInline):
    model = demo.BookInline.model
    extra = demo.BookInline.extra


class ArticleInline(StackedInline):
    model = demo.ArticleInline.model
    extra = demo.ArticleInline.extra


class AuthorAdmin(UnfoldFieldsetsExtraMixin, ModelAdmin):
    list_display = ["name"]
    fieldsets_with_inlines = [
        (None, {"fields": ["name"]}),
        BookInline,
        ("Contact", {"fields": ["email"], "save_button": True}),
        ArticleInline,
        # Unfold's tabs: rendered together, here.
        ("Phone", {"fields": ["phone"], "classes": ["tab"]}),
        ("Biography", {"fields": ["bio"], "classes": ["tab"]}),
    ]


site.register(Author, AuthorAdmin)
