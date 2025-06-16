from rest_framework import status
from rest_framework.response import Response


class RecipeActionMixin:
    model = None
    serializer_class = None
    error_message = ""
    success_status = status.HTTP_201_CREATED

    def perform_action(
        self, request, pk, model, serializer_class, error_message
    ):
        recipe = self.get_object()
        user = request.user
        queryset = model.objects.filter(user=user, recipe=recipe)
        exists = queryset.exists()

        if (request.method == "POST" and exists) or (
            request.method == "DELETE" and not exists
        ):
            msg = (
                error_message
                if request.method == "POST"
                else f"Рецепт не найден в {model._meta.verbose_name}."
            )
            return Response(
                {"errors": msg},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.method == "POST":
            model.objects.create(user=user, recipe=recipe)
            serializer = serializer_class(
                recipe,
                context={"request": request}
            )
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        queryset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
