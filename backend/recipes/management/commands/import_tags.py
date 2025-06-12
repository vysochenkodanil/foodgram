import csv
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from recipes.models import Tag


class Command(BaseCommand):
    help = "Загружаем тэги из csv."

    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, 'data', 'ingredients.csv')
        with open("data/tags.csv", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                name, slug = row
                Tag.objects.get_or_create(
                    name=name.strip(),
                    slug=slug.strip()
                )
        self.stdout.write(
            self.style.SUCCESS("Теги загружены, мой господин.")
        )
