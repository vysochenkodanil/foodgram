from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthorOrReadOnly
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from user.models import CustomUser
from user.serializers import CustomUserWithRecipesSerializer

from .models import (Favorite, Ingredient, Recipe, ShoppingCart, Subscription,
                     Tag)
from .serializers import (FavoriteSerializer, IngredientSerializer,
                          RecipeReadSerializer, RecipeWriteSerializer,
                          ShoppingCartSerializer, TagPublicSerializer,
                          TagReadSerializer)
from .utils.base62 import decode_base62, encode_base62


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by("-pub_date")
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        IsAuthorOrReadOnly,
    ]
    filter_backends = [DjangoFilterBackend]
    search_fields = ("^name","name")
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RecipeWriteSerializer
        return RecipeReadSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = RecipeReadSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        read_serializer = RecipeReadSerializer(
            instance, context=self.get_serializer_context()
        )
        return Response(read_serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if Favorite.objects.filter(user=user, recipe=recipe).exists():
            return Response(
                {"errors": "Рецепт уже в избранном."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        Favorite.objects.create(user=user, recipe=recipe)
        serializer = FavoriteSerializer(recipe, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        deleted, _ = Favorite.objects.filter(user=user, recipe=recipe).delete()
        if not deleted:
            return Response(
                {"errors": "Рецепта не было в избранном."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="shopping_cart",
        permission_classes=[permissions.IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        user = request.user
        try:
            recipe = Recipe.objects.get(pk=pk)
        except Recipe.DoesNotExist:
            return Response(
                {"errors": "Рецепт не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "POST":
            if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {"errors": "Рецепт уже в списке покупок."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ShoppingCart.objects.create(user=user, recipe=recipe)
            serializer = ShoppingCartSerializer(
                recipe, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            cart_item = ShoppingCart.objects.filter(user=user, recipe=recipe)
            if cart_item.exists():
                cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"errors": "Рецепт не найден в списке покупок."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"], url_path="get-link")
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_code = encode_base62(recipe.id)
        short_link = f"http://short.link/{short_code}"
        return Response({"short-link": short_link})


def redirect_to_recipe(request, short_code):
    recipe_id = decode_base62(short_code)
    recipe = get_object_or_404(Recipe, id=recipe_id)
    return redirect(f"/recipes/{recipe.id}/")


class FavoriteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recipe.objects.filter(favorited_by__user=self.request.user)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_serializer_class(self):
        if self.request.user.is_authenticated:
            return TagReadSerializer  # Авторизованные видят цвет
        return TagPublicSerializer


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = IngredientFilter


class ShoppingCartViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShoppingCartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recipe.objects.filter(
            in_shopping_carts__user=self.request.user
        ).order_by("-in_shopping_carts__id")


class SubscriptionViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
):
    serializer_class = CustomUserWithRecipesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomUser.objects.filter(subscribers__user=self.request.user)

    def perform_create(self, serializer):
        author = get_object_or_404(CustomUser, pk=self.request.data["author"])
        serializer.save(user=self.request.user, author=author)

    def destroy(self, request, *args, **kwargs):
        author_id = self.kwargs.get("pk")
        author = get_object_or_404(CustomUser, pk=author_id)
        subscription = Subscription.objects.filter(
            user=request.user, author=author
        ).first()
        if not subscription:
            return Response(
                {"errors": "Вы не подписаны на этого пользователя."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DownloadShoppingCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Возвращает файл .txt со сводным списком ингредиентов.
        """
        from recipes.models import IngredientInRecipe

        qs = IngredientInRecipe.objects.filter(
            recipe__in_shopping_carts__user=request.user
        )
        aggregated = qs.values(
            name=F("ingredient__name"), unit=F("ingredient__measurement_unit")
        ).annotate(total=Sum("amount"))

        lines = [
            f"{item['name']} ({item['unit']}) — {item['total']}"
            for item in aggregated
        ]
        content = "\n".join(lines)
        response = HttpResponse(
            content, content_type="text/plain; charset=utf-8"
        )
        response["Content-Disposition"] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response
