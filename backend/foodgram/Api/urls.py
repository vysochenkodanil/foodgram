from django.urls import path
from rest_framework.routers import DefaultRouter

from recipes.views import (
    RecipeViewSet,
    ShoppingCartViewSet,
    DownloadShoppingCartView,
    FavoriteViewSet,
    SubscriptionViewSet
)

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipe')
router.register(r'shopping_cart', ShoppingCartViewSet, basename='shopping_cart')
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

urlpatterns = [
    *router.urls,
    path(
        'recipes/download_shopping_cart/',
        DownloadShoppingCartView.as_view(),
        name='download_shopping_cart'
    ),
]
