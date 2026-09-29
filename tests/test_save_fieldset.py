import pytest
from demo.models import Author
from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, User
from django.urls import clear_url_caches, path, reverse

from django_admin_fieldsets_extra.mixins import (
    FieldsetsExtraMixin,
    django_fieldset,
)


def change_url(author):
    return reverse("admin:demo_author_change", args=[author.pk])


def save_url(author, index, site="admin"):
    return reverse(f"{site}:demo_author_fieldset_save", args=[author.pk, index])


def test_save_button_option_is_hidden_from_django():
    from demo.admin import AuthorAdmin

    assert AuthorAdmin.fieldsets[1] == ("Contact", {"fields": ["email", "phone"]})
    assert django_fieldset(("x", {"fields": ["a"]})) == ("x", {"fields": ["a"]})
    assert django_fieldset(("x",)) == ("x",)


def test_buttons_are_rendered(admin_client, author):
    html = admin_client.get(change_url(author)).content.decode()

    assert html.count("data-fieldset-save ") == 2
    assert f'data-fieldset-save-url="{save_url(author, 1)}"' in html
    assert ">Save Contact</button>" in html
    assert 'id="fieldset-0-container"' not in html  # no save_button


def test_add_view_has_no_buttons(admin_client, db):
    html = admin_client.get(reverse("admin:demo_author_add")).content.decode()

    assert "data-fieldset-save " not in html


def test_save_only_the_fieldset(admin_client, author):
    response = admin_client.post(
        save_url(author, 1),
        {"email": "a@example.com", "phone": "123", "name": "Ignored", "bio": "x"},
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="fieldset-1-container"' in html
    assert "fieldset-save-status-saved" in html
    assert ">Saved.</span>" in html
    author.refresh_from_db()
    assert (author.email, author.phone) == ("a@example.com", "123")
    assert (author.name, author.bio) == ("Author", "")
    assert LogEntry.objects.get().get_change_message() == "Changed Email and Phone."


def test_unchanged_fieldset_logs_nothing(admin_client, author):
    admin_client.post(save_url(author, 1), {"email": "", "phone": ""})

    assert not LogEntry.objects.exists()


def test_invalid_fieldset(admin_client, author):
    response = admin_client.post(save_url(author, 1), {"email": "nope", "phone": "1"})

    html = response.content.decode()
    assert "fieldset-save-status-invalid" in html
    assert "Enter a valid email address." in html
    author.refresh_from_db()
    assert author.phone == ""


@pytest.mark.parametrize("index", [0, 9])
def test_fieldset_without_button_or_out_of_range_is_404(admin_client, author, index):
    assert admin_client.post(save_url(author, index), {}).status_code == 404


def test_unknown_object_is_404(admin_client, db):
    url = reverse("admin:demo_author_fieldset_save", args=[999, 1])

    assert admin_client.post(url, {}).status_code == 404


def test_get_is_not_allowed(admin_client, author):
    assert admin_client.get(save_url(author, 1)).status_code == 405


def test_change_permission_required(client, author):
    user = User.objects.create_user("staff", password="x", is_staff=True)
    user.user_permissions.set(Permission.objects.filter(codename="view_author"))
    client.force_login(user)

    html = client.get(change_url(author)).content.decode()
    assert "data-fieldset-save " not in html
    assert client.post(save_url(author, 1), {}).status_code == 403


class CheckedForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("phone") == "000":
            raise forms.ValidationError("No zeros.")
        return cleaned


@pytest.fixture
def custom_site(settings):
    """A throwaway admin site mounted at /fs-admin/."""
    site = admin.AdminSite(name="fieldset_site")

    @admin.register(Author, site=site)
    class AuthorAdmin(FieldsetsExtraMixin, admin.ModelAdmin):
        form = CheckedForm
        readonly_fields = ["bio"]
        fieldsets_with_inlines = [
            ("Contact", {"fields": ["phone", "bio"], "save_button": True}),
            ("Read only", {"fields": ["bio"], "save_button": True}),
            (None, {"fields": ["name"], "save_button": True}),
        ]

    module = type("urls", (), {"urlpatterns": [path("fs-admin/", site.urls)]})
    settings.ROOT_URLCONF = module
    clear_url_caches()
    yield site
    clear_url_caches()


def test_non_field_errors_are_returned(admin_client, author, custom_site):
    response = admin_client.post(save_url(author, 0, "fieldset_site"), {"phone": "000"})

    html = response.content.decode()
    assert "fieldset-save-status-invalid" in html
    assert 'class="fieldset-save-errors"' in html
    assert "No zeros." in html


def test_readonly_fields_are_not_saved(admin_client, author, custom_site):
    response = admin_client.post(
        save_url(author, 0, "fieldset_site"), {"phone": "5", "bio": "hacked"}
    )

    assert b"fieldset-save-status-saved" in response.content
    author.refresh_from_db()
    assert (author.phone, author.bio) == ("5", "")


def test_fieldset_with_only_readonly_fields_is_404(admin_client, author, custom_site):
    assert (
        admin_client.post(save_url(author, 1, "fieldset_site"), {}).status_code == 404
    )


def test_unnamed_fieldset_label(admin_client, author, custom_site):
    url = reverse("fieldset_site:demo_author_change", args=[author.pk])
    html = admin_client.get(url).content.decode()

    assert ">Save</button>" in html
    assert ">Save Contact</button>" in html


def test_check_save_button_type():
    admin_class = type(
        "Admin",
        (FieldsetsExtraMixin, admin.ModelAdmin),
        {
            "__module__": __name__,
            "fieldsets_with_inlines": [(None, {"fields": ["name"], "save_button": 1})],
        },
    )
    ids = [e.id for e in admin_class(Author, admin.AdminSite()).check()]

    assert "admin_fieldsets_extra.E004" in ids
