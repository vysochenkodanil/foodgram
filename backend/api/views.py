from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import mixins, permissions, status, viewsets
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
from api.utils.base62 import decode_base62, encode_base62
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
            error_message="Рецепт уже в списке покупок."
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="get-link",
    )
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_code = encode_base62(recipe.id)
        base = settings.SHORT_LINK_BASE_URL.rstrip("/")
        short_link = f"{base}/{short_code}"
        return Response({"short-link": short_link})


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


class SubscriptionViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
):
    serializer_class = CustomUserWithRecipesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CustomUser.objects.filter(
            subscribers__user=self.request.user,
        )

    def perform_create(self, serializer):
        author = get_object_or_404(
            CustomUser,
            pk=self.request.data["author"],
        )
        serializer.save(
            user=self.request.user,
            author=author,
        )

    def destroy(self, request, *args, **kwargs):
        author_id = self.kwargs.get("pk")
        author = get_object_or_404(CustomUser, pk=author_id)
        subscription = Subscription.objects.filter(
            user=request.user,
            author=author,
        ).first()
        if not subscription:
            return Response(
                {"errors": "Вы не подписаны на этого пользователя."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomUserViewSet(UserViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["me", "retrieve"]:
            return CustomUserBaseSerializer
        return super().get_serializer_class()

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
