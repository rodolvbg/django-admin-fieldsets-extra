from demo.models import Article, Author, Book
from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import path, reverse
from unittest_parametrize import ParametrizedTestCase, parametrize

from django_admin_fieldsets_extra.mixins import (
    FieldsetsExtraMixin,
    django_fieldset,
)


def change_url(author):
    return reverse("admin:demo_author_change", args=[author.pk])


def save_url(author, index, site="admin"):
    return reverse(f"{site}:demo_author_fieldset_save", args=[author.pk, index])


class CheckedForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("phone") == "000":
            raise forms.ValidationError("No zeros.")
        return cleaned


custom_site = admin.AdminSite(name="fieldset_site")


@admin.register(Author, site=custom_site)
class CustomAuthorAdmin(FieldsetsExtraMixin, admin.ModelAdmin):
    form = CheckedForm
    readonly_fields = ["bio"]
    fieldsets_with_inlines = [
        ("Contact", {"fields": ["phone", "bio"], "save_button": True}),
        ("Read only", {"fields": ["bio"], "save_button": True}),
        (None, {"fields": ["name"], "save_button": True}),
    ]


# A throwaway admin site mounted at /fs-admin/.
custom_urls = type("urls", (), {"urlpatterns": [path("fs-admin/", custom_site.urls)]})


class TestDjangoFieldset(SimpleTestCase):
    """django_fieldset(): the layout minus our own options."""

    def test_save_button_option_is_hidden_from_django(self):
        from demo.admin import AuthorAdmin

        assert AuthorAdmin.fieldsets[1] == ("Contact", {"fields": ["email", "phone"]})
        assert django_fieldset(("x", {"fields": ["a"]})) == ("x", {"fields": ["a"]})
        assert django_fieldset(("x",)) == ("x",)


class TestSaveButtons(TestCase):
    """The per-fieldset buttons in the change form."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.author = Author.objects.create(name="Author")
        Book.objects.create(author=cls.author, title="A book")
        Article.objects.create(author=cls.author, title="An article")

    def setUp(self):
        self.client.force_login(self.user)

    def test_buttons_are_rendered(self):
        html = self.client.get(change_url(self.author)).content.decode()

        assert html.count("data-fieldset-save ") == 2
        assert f'data-fieldset-save-url="{save_url(self.author, 1)}"' in html
        assert ">Save Contact</button>" in html
        assert 'id="fieldset-0-container"' not in html  # no save_button

    def test_add_view_has_no_buttons(self):
        html = self.client.get(reverse("admin:demo_author_add")).content.decode()

        assert "data-fieldset-save " not in html


class TestSaveFieldsetView(ParametrizedTestCase, TestCase):
    """The endpoint that saves a single fieldset."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.author = Author.objects.create(name="Author")
        Book.objects.create(author=cls.author, title="A book")
        Article.objects.create(author=cls.author, title="An article")

    def setUp(self):
        self.client.force_login(self.user)

    def test_save_only_the_fieldset(self):
        response = self.client.post(
            save_url(self.author, 1),
            {"email": "a@example.com", "phone": "123", "name": "Ignored", "bio": "x"},
        )

        assert response.status_code == 200
        html = response.content.decode()
        assert 'id="fieldset-1-container"' in html
        assert "fieldset-save-status-saved" in html
        assert ">Saved.</span>" in html
        self.author.refresh_from_db()
        assert (self.author.email, self.author.phone) == ("a@example.com", "123")
        assert (self.author.name, self.author.bio) == ("Author", "")
        assert LogEntry.objects.get().get_change_message() == "Changed Email and Phone."

    def test_unchanged_fieldset_logs_nothing(self):
        self.client.post(save_url(self.author, 1), {"email": "", "phone": ""})

        assert not LogEntry.objects.exists()

    def test_invalid_fieldset(self):
        response = self.client.post(
            save_url(self.author, 1), {"email": "nope", "phone": "1"}
        )

        html = response.content.decode()
        assert "fieldset-save-status-invalid" in html
        assert "Enter a valid email address." in html
        self.author.refresh_from_db()
        assert self.author.phone == ""

    @parametrize("index", [0, 9])
    def test_fieldset_without_button_or_out_of_range_is_404(self, index):
        assert self.client.post(save_url(self.author, index), {}).status_code == 404

    def test_unknown_object_is_404(self):
        url = reverse("admin:demo_author_fieldset_save", args=[999, 1])

        assert self.client.post(url, {}).status_code == 404

    def test_get_is_not_allowed(self):
        assert self.client.get(save_url(self.author, 1)).status_code == 405

    def test_change_permission_required(self):
        user = User.objects.create_user("staff", password="x", is_staff=True)
        user.user_permissions.set(Permission.objects.filter(codename="view_author"))
        self.client.force_login(user)

        html = self.client.get(change_url(self.author)).content.decode()
        assert "data-fieldset-save " not in html
        assert self.client.post(save_url(self.author, 1), {}).status_code == 403


@override_settings(ROOT_URLCONF=custom_urls)
class TestCustomSiteSaveFieldset(TestCase):
    """The save endpoint on a site with a custom form and read-only fields."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.author = Author.objects.create(name="Author")
        Book.objects.create(author=cls.author, title="A book")
        Article.objects.create(author=cls.author, title="An article")

    def setUp(self):
        self.client.force_login(self.user)

    def test_non_field_errors_are_returned(self):
        response = self.client.post(
            save_url(self.author, 0, "fieldset_site"), {"phone": "000"}
        )

        html = response.content.decode()
        assert "fieldset-save-status-invalid" in html
        assert 'class="fieldset-save-errors"' in html
        assert "No zeros." in html

    def test_readonly_fields_are_not_saved(self):
        response = self.client.post(
            save_url(self.author, 0, "fieldset_site"), {"phone": "5", "bio": "hacked"}
        )

        assert b"fieldset-save-status-saved" in response.content
        self.author.refresh_from_db()
        assert (self.author.phone, self.author.bio) == ("5", "")

    def test_fieldset_with_only_readonly_fields_is_404(self):
        assert (
            self.client.post(save_url(self.author, 1, "fieldset_site"), {}).status_code
            == 404
        )

    def test_unnamed_fieldset_label(self):
        url = reverse("fieldset_site:demo_author_change", args=[self.author.pk])
        html = self.client.get(url).content.decode()

        assert ">Save</button>" in html
        assert ">Save Contact</button>" in html


class TestSaveButtonCheck(SimpleTestCase):
    """System check E004."""

    def test_check_save_button_type(self):
        admin_class = type(
            "Admin",
            (FieldsetsExtraMixin, admin.ModelAdmin),
            {
                "__module__": __name__,
                "fieldsets_with_inlines": [
                    (None, {"fields": ["name"], "save_button": 1})
                ],
            },
        )
        ids = [e.id for e in admin_class(Author, admin.AdminSite()).check()]

        assert "admin_fieldsets_extra.E004" in ids
