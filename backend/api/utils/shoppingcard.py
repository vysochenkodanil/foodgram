from django.db.models import F, Sum
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from recipes.models import IngredientInRecipe


class DownloadShoppingCartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Возвращает файл .txt со сводным списком ингредиентов."""

        qs = IngredientInRecipe.objects.filter(
            recipe__in_shopping_carts__user=request.user,
        )
        aggregated = qs.values(
            name=F("ingredient__name"),
            unit=F("ingredient__measurement_unit"),
        ).annotate(total=Sum("amount"))

        lines = [
            f"{item['name']} ({item['unit']}) — {item['total']}"
            for item in aggregated
        ]
        content = "\n".join(lines)
        response = HttpResponse(
            content,
            content_type="text/plain; charset=utf-8",
        )
        response["Content-Disposition"] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response
