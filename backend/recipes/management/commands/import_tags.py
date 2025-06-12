import csv 

from django.core.management.base import BaseCommand
from recipes.models import Tag


class Command(BaseCommand):
    help = "Загружаем тэги из csv."

    def handle(self, *args, **options):
        with open(
            "data/tags.csv", encoding="utf-8"
            ) as file:
            reader = csv.reader(file)
            for row in reader:
                name, slug = row
                obj, created = Tag.objects.get_or_create(
                    name=name.strip(), slug=slug.strip()
                )
        self.stdout.write(self.style.SUCCESS(
            f"Теги загружены, мой господин."))
