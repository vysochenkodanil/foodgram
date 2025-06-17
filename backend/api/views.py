from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Prefetch, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from api.filters import IngredientFilter, RecipeFilter
from api.mixins import RecipeActionMixin
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (
    CustomUserBaseSerializer,
    CustomUserWithRecipesSerializer,
    FavoriteSerializer,
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    ShoppingCartSerializer,
    TagPublicSerializer,
)
from api.utils.base62 import decode_base62
from recipes.models import (
    Favorite,
    Ingredient,
    IngredientInRecipe,
    Recipe,
    ShoppingCart,
    Subscription,
    Tag,
)
from user.models import CustomUser

User = get_user_model()


class RecipeViewSet(RecipeActionMixin, viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by("-pub_date")
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    search_fields = ("^name", "name")
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RecipeWriteSerializer
        return RecipeReadSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        return self.perform_action(
            request=request,
            pk=pk,
            model=Favorite,
            serializer_class=FavoriteSerializer,
            error_message="Рецепт уже в избранном.",
        )

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[permissions.IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        return self.perform_action(
            request=request,
            pk=pk,
            model=ShoppingCart,
            serializer_class=ShoppingCartSerializer,
            error_message="Рецепт уже в списке покупок.",
        )

    @action(
        detail=True,
        methods=["GET"],
        url_path="get-link",
        url_name="get-link",
    )
    def get_link(self, request, pk=None):
        if not Recipe.objects.filter(pk=pk).exists():
            raise Http404("Рецепт не найден")
        url = request.build_absolute_uri(f"/recipes/{pk}/")
        return Response({"short-link": url}, status=status.HTTP_200_OK)


def redirect_to_recipe(request, short_code):
    recipe_id = decode_base62(short_code)
    recipe = get_object_or_404(Recipe, id=recipe_id)
    return redirect(f"/recipes/{recipe.id}/")


class FavoriteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Recipe.objects.filter(
            favorited_by__user=self.request.user,
        )


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None
    serializer_class = TagPublicSerializer


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = IngredientFilter


class ShoppingCartViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShoppingCartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Recipe.objects.filter(
            in_shopping_carts__user=self.request.user,
        ).order_by("-in_shopping_carts__id")


class CustomUserViewSet(UserViewSet):
    queryset = CustomUser.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "id"
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action in ["me", "retrieve"]:
            return CustomUserBaseSerializer
        return super().get_serializer_class()

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
        url_path="subscribe",
        url_name="subscribe",
    )
    def subscribe(self, request, *args, **kwargs):
        """Подписаться/отписаться на пользователя"""
        author = self.get_object()
        user = request.user
        if user == author:
            return Response(
                {"error": "Нельзя подписаться на самого себя"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.method == "POST":
            if Subscription.objects.filter(user=user, author=author).exists():
                return Response(
                    {"error": "Вы уже подписаны на этого пользователя"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            Subscription.objects.create(user=user, author=author)
            serializer = CustomUserWithRecipesSerializer(
                author, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        deleted_count, _ = Subscription.objects.filter(
            user=user, author=author
        ).delete()
        if deleted_count == 0:
            return Response(
                {"error": "Вы не подписаны на этого пользователя"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="subscriptions",
        url_name="subscriptions",
    )
    def subscriptions(self, request):
        """Получить список моих подписок"""
        user = request.user
        authors = (
            CustomUser.objects.filter(followers__user=user)
            .prefetch_related(
                Prefetch(
                    "recipes",
                    queryset=Recipe.objects.order_by("-pub_date").only(
                        "id", "name", "image", "cooking_time"
                    ),
                )
            )
            .annotate(recipes_count=Count("recipes"))
        )
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = CustomUserWithRecipesSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)
        serializer = CustomUserWithRecipesSerializer(
            authors, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["put", "delete"], url_path="me/avatar")
    def avatar(self, request):
        user = request.user
        if request.method == "PUT":
            serializer = CustomUserBaseSerializer(
                user,
                data={"avatar": request.data.get("avatar")},
                partial=True,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {"avatar": user.avatar.url}, status=status.HTTP_200_OK
            )
        user.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["get"], detail=False)
    def me(self, request):
        serializer = self.get_serializer(
            request.user, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


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
