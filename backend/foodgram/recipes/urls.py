from rest_framework.routers import DefaultRouter
from .views import RecipeViewSet

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet, basename='recipes')

urlpatterns = router.urls
