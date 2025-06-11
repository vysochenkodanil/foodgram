import json

from django.core.management.base import BaseCommand

from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загрузка ингредиентов из JSON'

    def handle(self, *args, **options):
        file_path = 'backend/data/ingredients.json'

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                Ingredient.objects.get_or_create(
                    name=item['name'],
                    measurement_unit=item['measurement_unit']
                )

        self.stdout.write('Данные успешно загружены')
