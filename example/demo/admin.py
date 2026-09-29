from django.contrib import admin

from django_admin_fieldsets_with_inlines.mixins import FieldsetsWithInlinesMixin

from .models import Article, Author, Book


class BookInline(admin.TabularInline):
    model = Book
    extra = 1


class ArticleInline(admin.StackedInline):
    model = Article
    extra = 0


@admin.register(Author)
class AuthorAdmin(FieldsetsWithInlinesMixin, admin.ModelAdmin):
    list_display = ["name"]
    fieldsets_with_inlines = [
        (None, {"fields": ["name"]}),
        BookInline,
        ("Contact", {"fields": ["email", "phone"], "save_button": True}),
        ArticleInline,
        (
            "Biography",
            {"fields": ["bio"], "classes": ["collapse"], "save_button": True},
        ),
    ]
