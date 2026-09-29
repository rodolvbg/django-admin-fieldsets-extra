from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class Article(models.Model):
    author = models.ForeignKey(
        Author, on_delete=models.CASCADE, related_name="articles"
    )
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title
