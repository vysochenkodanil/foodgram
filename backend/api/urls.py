from django.urls import path
from rest_framework.routers import DefaultRouter
from recipes import views

from recipes.views import (
    RecipeViewSet,
    ShoppingCartViewSet,
    DownloadShoppingCartView,
    FavoriteViewSet,
    SubscriptionViewSet,
    TagViewSet,
    IngredientViewSet,
)

router = DefaultRouter()
router.register(r"recipes", RecipeViewSet, basename="recipe")
router.register(r"shopping_cart", ShoppingCartViewSet, basename="shopping_cart")
router.register(r"favorites", FavoriteViewSet, basename="favorite")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"ingredients", IngredientViewSet, basename="ingredient")

urlpatterns = [
    *router.urls,
    path(
        "recipes/download_shopping_cart/",
        DownloadShoppingCartView.as_view(),
        name="download_shopping_cart",
    ),
    path("r/<str:short_code>/", views.redirect_to_recipe, name="redirect_to_recipe"),
]
