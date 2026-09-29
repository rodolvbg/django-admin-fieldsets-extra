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
