from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from demo.models import Article, Author, Book


class Command(BaseCommand):
    help = "Create an admin/admin superuser and an author with books and articles."

    def handle(self, *args, **options):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin")
        author, _ = Author.objects.update_or_create(
            name="Demo Author",
            defaults={"email": "demo@example.com", "phone": "555-0100"},
        )
        author.books.all().delete()
        author.articles.all().delete()
        Book.objects.bulk_create(
            Book(author=author, title=title)
            for title in ["Iron Blue", "Paper Night", "Silent River"]
        )
        Article.objects.create(author=author, title="On interleaving forms")
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {author} (pk={author.pk}). Log in as admin/admin."
            )
        )
