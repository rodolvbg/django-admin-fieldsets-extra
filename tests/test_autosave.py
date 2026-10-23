"""Fieldsets that save themselves as their fields change ("autosave")."""

from demo.models import Author
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import path, reverse

from django_admin_fieldsets_extra.mixins import FieldsetsExtraMixin


def save_url(author, index, site="admin"):
    return reverse(f"{site}:demo_author_fieldset_save", args=[author.pk, index])


# The demo's AuthorAdmin: its "Status" (active, notes) saves itself.
STATUS = 3

all_site = admin.AdminSite(name="autosave_site")


@admin.register(Author, site=all_site)
class EverythingSavesItself(FieldsetsExtraMixin, admin.ModelAdmin):
    readonly_fields = ["bio"]
    fieldsets_with_inlines = [
        ("Status", {"fields": ["active", "notes"], "autosave": True}),
        ("About", {"fields": ["name", "email", "phone"], "autosave": True}),
        ("Read only", {"fields": ["bio"]}),
    ]


all_urls = type("urls", (), {"urlpatterns": [path("all/", all_site.urls)]})


class TestAutosave(TestCase):
    user: User
    author: Author

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        cls.author = Author.objects.create(name="Ana", notes="First")

    def setUp(self):
        self.client.force_login(self.user)

    def post(self, data, previous=None, index=STATUS):
        body = dict(data)
        if previous is not None:
            body["check"] = "1"
            body.update({f"previous-{k}": v for k, v in previous.items()})
        return self.client.post(save_url(self.author, index), body)

    def test_it_has_no_button(self):
        url = reverse("admin:demo_author_change", args=[self.author.pk])
        html = self.client.get(url).content.decode()
        container = html[html.index(f'id="fieldset-{STATUS}-container"') - 60 :]
        container = container[: container.index("</fieldset>") + 400]
        assert 'class="fieldset-with-save fieldset-autosave"' in container
        assert "data-fieldset-autosave" in container
        assert 'data-fieldset-saving="Saving…"' in container
        assert "data-fieldset-save " not in container
        # The page's own buttons stay: other fieldsets, and inlines.
        assert 'name="_save"' in html

    def test_it_saves_and_says_so(self):
        response = self.post(
            {"active": "on", "notes": "Second"},
            previous={"active": "on", "notes": "First"},
        )
        assert response.status_code == 200
        html = response.content.decode()
        assert ">Saved</span>" in html
        assert "data-fieldset-save " not in html
        self.author.refresh_from_db()
        assert self.author.notes == "Second"
        assert LogEntry.objects.get().get_change_message() == "Changed Notes."

    def test_an_unchecked_checkbox_isnt_a_conflict(self):
        response = self.post(
            {"notes": "First"}, previous={"active": "on", "notes": "First"}
        )
        assert response.status_code == 200
        self.author.refresh_from_db()
        assert self.author.active is False
        # Unchecked before, and now: nothing sent for it.
        response = self.post(
            {"active": "on", "notes": "First"}, previous={"notes": "First"}
        )
        assert response.status_code == 200
        self.author.refresh_from_db()
        assert self.author.active is True

    def test_what_someone_else_changed_isnt_overwritten(self):
        Author.objects.filter(pk=self.author.pk).update(notes="Theirs")
        response = self.post(
            {"active": "on", "notes": "Mine"},
            previous={"active": "on", "notes": "First"},
        )
        assert response.status_code == 409
        html = response.content.decode()
        assert "fieldset-save-status-conflict" in html
        assert "Someone else changed this section meanwhile" in html
        assert 'value="Theirs"' in html  # What's saved now.
        self.author.refresh_from_db()
        assert self.author.notes == "Theirs"

    def test_not_valid(self):
        response = self.post(
            {"active": "on", "notes": "x" * 201},
            previous={"active": "on", "notes": "First"},
        )
        assert response.status_code == 200
        html = response.content.decode()
        assert "fieldset-save-status-invalid" in html
        assert "errorlist" in html

    def test_without_a_check_it_saves_as_the_button_does(self):
        Author.objects.filter(pk=self.author.pk).update(notes="Theirs")
        self.post({"notes": "Mine"})
        self.author.refresh_from_db()
        assert self.author.notes == "Mine"


class TestEverythingSavesItself(TestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        cls.author = Author.objects.create(name="Ana")

    def setUp(self):
        self.client.force_login(self.user)

    def test_no_save_buttons_but_delete(self):
        from django.test import override_settings

        with override_settings(ROOT_URLCONF=all_urls):
            url = reverse("autosave_site:demo_author_change", args=[self.author.pk])
            html = self.client.get(url).content.decode()
            add = self.client.get(reverse("autosave_site:demo_author_add")).content
        assert 'name="_save"' not in html
        assert 'name="_continue"' not in html
        assert 'name="_addanother"' not in html
        assert "deletelink" in html
        # Adding: nothing to save itself yet.
        assert b'name="_save"' in add


class TestChecks(SimpleTestCase):
    def test_autosave_must_be_a_bool(self):
        admin_class = type(
            "Admin",
            (FieldsetsExtraMixin, admin.ModelAdmin),
            {
                "__module__": __name__,
                "fieldsets_with_inlines": [(None, {"fields": ["name"], "autosave": 1})],
            },
        )
        ids = [e.id for e in admin_class(Author, admin.AdminSite()).check()]
        assert "admin_fieldsets_extra.E005" in ids

    def test_the_script_where_a_fieldset_saves_itself(self):
        admin_class = type(
            "Admin",
            (FieldsetsExtraMixin, admin.ModelAdmin),
            {
                "__module__": __name__,
                "fieldsets_with_inlines": [
                    (None, {"fields": ["name"], "autosave": True})
                ],
            },
        )
        assert "fieldsets_extra/js/fieldsets_extra.js" in str(
            admin_class(Author, admin.site).media
        )
