from rest_framework import viewsets, status, mixins
from .models import Recipe, Tag, Ingredient
from User.models import CustomUser
from .serializers import RecipeReadSerializer, RecipeWriteSerializer, ShoppingCartSerializer, FavoriteSerializer, FollowSerializer, TagSerializer, IngredientSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import APIView
from rest_framework import permissions
from Api.permissions import IsAuthorOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from Api.filters import RecipeFilter, IngredientFilter
from .utils.base62 import encode_base62, decode_base62
from django.shortcuts import get_object_or_404, redirect
 

class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by('-pub_date')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    search_fields = ('^name','name')
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return RecipeWriteSerializer
        return RecipeReadSerializer
    
    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = RecipeReadSerializer(
            serializer.instance,
            context=self.get_serializer_context()
        )
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        read_serializer = RecipeReadSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        if Favorite.objects.filter(user=user, recipe=recipe).exists():
            return Response({'errors': 'Рецепт уже в избранном.'}, status=status.HTTP_400_BAD_REQUEST)
        Favorite.objects.create(user=user, recipe=recipe)
        serializer = FavoriteSerializer(recipe, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        recipe = self.get_object()
        user = request.user
        deleted, _ = Favorite.objects.filter(user=user, recipe=recipe).delete()
        if not deleted:
            return Response({'errors': 'Рецепта не было в избранном.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        """
        Добавить рецепт в список покупок.
        """
        recipe = self.get_object()
        user   = request.user
        if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
            return Response(
                {'errors': 'Рецепт уже в списке покупок.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        ShoppingCart.objects.create(user=user, recipe=recipe)
        serializer = ShoppingCartSerializer(recipe, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        """
        Удалить рецепт из списка покупок.
        """
        recipe = self.get_object()
        user   = request.user
        deleted, _ = ShoppingCart.objects.filter(
            user=user, recipe=recipe
        ).delete()
        if not deleted:
            return Response(
                {'errors': 'Рецепта не было в списке покупок.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_code = encode_base62(recipe.id)
        short_link = f"http://short.link/{short_code}"
        return Response({"short-link": short_link})


def redirect_to_recipe(request, short_code):
    recipe_id = decode_base62(short_code)
    recipe = get_object_or_404(Recipe, id=recipe_id)
    return redirect(f'/recipes/{recipe.id}/')

class FavoriteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recipe.objects.filter(favorited_by__user=self.request.user)

class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = IngredientFilter


class ShoppingCartViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /shopping_cart/             — список всех рецептов в покупках
    GET /shopping_cart/?page=2      — постраничная навигация
    """
    serializer_class = ShoppingCartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Recipe.objects.filter(
            in_shopping_carts__user=self.request.user
        ).order_by('-in_shopping_carts__id')


class SubscriptionViewSet(viewsets.GenericViewSet,
                          mixins.ListModelMixin,
                          mixins.CreateModelMixin,
                          mixins.DestroyModelMixin):
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomUser.objects.filter(subscribers__user=self.request.user)

    def perform_create(self, serializer):
        author = CustomUser.objects.get(pk=self.request.data['author'])
        serializer.save(user=self.request.user, author=author)


class DownloadShoppingCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Возвращает файл .txt со сводным списком ингредиентов.
        """
        user = request.user
        # 1. Собираем все IngredientInRecipe по рецептам из корзины
        from recipes.models import IngredientInRecipe
        qs = IngredientInRecipe.objects.filter(
            recipe__in_shopping_carts__user=user
        )
        # 2. Агрегируем: группируем по ингредиенту и измер. единице, суммируем amount
        from django.db.models import Sum, F
        aggregated = qs.values(
            name=F('ingredient__name'),
            unit=F('ingredient__measurement_unit')
        ).annotate(total=Sum('amount'))
        # 3. Формируем текст
        lines = []
        for item in aggregated:
            lines.append(
                f"{item['name']} ({item['unit']}) — {item['total']}"
            )
        content = "\n".join(lines)
        # 4. Отдаём как attachment
        response = HttpResponse(
            content,
            content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename="shopping_list.txt"'
        return response
