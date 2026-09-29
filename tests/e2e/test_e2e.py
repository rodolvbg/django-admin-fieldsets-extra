"""Real end-to-end tests: an actual Chromium against pytest-django's
``live_server``, on the demo ``AuthorAdmin`` layout (name, books inline,
contact fieldset, articles inline, collapsible biography)."""

import pytest
from demo.models import Author, Book
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def change_page(live_server, page: Page, admin_user, author):
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(
        f"{live_server.url}/admin/login/?next=/admin/demo/author/{author.pk}/change/"
    )
    page.fill("#id_username", "admin")
    page.fill("#id_password", "password")
    page.click("input[type=submit]")
    expect(page.locator("#books-group")).to_be_visible()
    yield page
    page.wait_for_load_state("networkidle")
    page.close()
    assert errors == []


def top(page: Page, selector: str) -> float:
    return page.locator(selector).first.bounding_box()["y"]


def test_layout_order_on_screen(change_page: Page):
    page = change_page
    positions = [
        top(page, "#id_name"),
        top(page, "#books-group"),
        top(page, "#id_email"),
        top(page, "#articles-group"),
        top(page, "#fieldset-0-2-heading"),
    ]

    assert positions == sorted(positions)


def test_inline_js_works_between_fieldsets(change_page: Page, author):
    page = change_page
    page.click("#books-group .add-row a")
    page.fill("input[name='books-2-title']", "Added between fieldsets")
    page.fill("#id_email", "a@example.com")
    page.click("input[name=_continue]")

    expect(page.locator(".messagelist")).to_contain_text("was changed successfully")
    assert Book.objects.filter(author=author, title="Added between fieldsets").exists()
    assert Author.objects.get(pk=author.pk).email == "a@example.com"


def test_collapsible_fieldset_after_an_inline(change_page: Page):
    page = change_page
    bio = page.locator("#id_bio")
    expect(bio).to_be_hidden()
    page.click("#fieldset-0-2-heading")
    expect(bio).to_be_visible()


def test_save_only_a_fieldset(change_page: Page, author):
    page = change_page
    page.evaluate("window.__noReload = true")
    contact = page.locator("#fieldset-1-container")
    expect(contact.locator("[data-fieldset-save]")).to_have_text("Save Contact")

    page.fill("#id_name", "Parent not saved")
    page.fill("input[name='books-0-title']", "Inline not saved")
    page.fill("#id_email", "nope")
    contact.locator("[data-fieldset-save]").click()
    status = page.locator("#fieldset-1-container .fieldset-save-status")
    expect(status).to_have_text("Please correct the errors below.")
    expect(page.locator("#fieldset-1-container .errorlist")).to_have_text(
        "Enter a valid email address."
    )

    page.fill("#id_email", "a@example.com")
    page.locator("#fieldset-1-container [data-fieldset-save]").click()
    expect(status).to_have_text("Saved.")
    assert page.evaluate("window.__noReload") is True
    assert page.input_value("#id_name") == "Parent not saved"
    assert page.input_value("input[name='books-0-title']") == "Inline not saved"
    author.refresh_from_db()
    assert (author.name, author.email) == ("Author", "a@example.com")


def test_collapsed_fieldset_hides_its_save_button(change_page: Page):
    page = change_page
    button = page.locator("#fieldset-2-container [data-fieldset-save]")
    expect(button).to_be_hidden()
    page.click("#fieldset-0-2-heading")
    expect(button).to_be_visible()
