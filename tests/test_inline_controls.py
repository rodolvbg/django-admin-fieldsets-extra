"""Together with django-admin-inline-controls (skipped if not installed)."""

import pytest
from django.urls import reverse

pytest.importorskip("django_admin_inline_controls")


def test_controls_render_inside_the_layout(admin_client, author):
    url = reverse("controls_admin:demo_author_change", args=[author.pk])
    html = admin_client.get(url).content.decode()

    books = html.index('id="books-inline-controls"')
    contact = html.index(">Contact</h2>")
    assert (
        html.index('id="fieldset-0-0-heading"' if False else "<fieldset")
        < books
        < contact
    )
    # Fieldset save buttons sit next to the inline's controls.
    assert html.count("data-fieldset-save ") == 2
    assert 'id="fieldset-1-container"' in html


def test_fieldset_save_uses_the_layout_positions(admin_client, author):
    url = reverse("controls_admin:demo_author_fieldset_save", args=[author.pk, 1])
    response = admin_client.post(url, {"email": "a@example.com", "phone": "1"})

    assert b"fieldset-save-status-saved" in response.content
    author.refresh_from_db()
    assert (author.email, author.name) == ("a@example.com", "Author")


def test_inline_save_inside_the_layout(admin_client, author):
    book = author.books.get()
    url = reverse(
        "controls_admin:demo_author_inline_controls_save", args=[author.pk, "books"]
    )
    response = admin_client.post(
        url,
        {
            "books-TOTAL_FORMS": "1",
            "books-INITIAL_FORMS": "1",
            "books-MIN_NUM_FORMS": "0",
            "books-MAX_NUM_FORMS": "1000",
            "books-0-id": str(book.pk),
            "books-0-author": str(author.pk),
            "books-0-title": "Saved alone",
        },
    )

    assert b'data-status="saved"' in response.content
    book.refresh_from_db()
    assert book.title == "Saved alone"
