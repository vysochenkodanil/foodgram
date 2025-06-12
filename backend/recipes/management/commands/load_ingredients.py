import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from recipes.models import Ingredient


class Command(BaseCommand):
    help = "Загружает ингредиенты из CSV-файла"

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.BASE_DIR, 'data', 'ingredients.csv')
        with open(
            "data/ingredients.csv",
            encoding="utf-8",
        ) as file:
            reader = csv.reader(file)
            next(reader)
            count = 0
            for row in reader:
                name, unit = row
                obj, created = Ingredient.objects.get_or_create(
                    name=name.strip(), measurement_unit=unit.strip()
                )
                if created:
                    count += 1
        self.stdout.write(
            self.style.SUCCESS(f"Успешно загружено {count} ингредиентов.")
        )
