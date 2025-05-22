from rest_framework import viewsets
from .models import Recipe
from .serializers import RecipeReadSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by('-pub_date')
    serializer_class = RecipeReadSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
