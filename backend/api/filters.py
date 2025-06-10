from django_filters.rest_framework import FilterSet, filters
from recipes.models import Tag, Recipe, Ingredient


from django_filters.rest_framework import FilterSet, filters
from recipes.models import Tag, Recipe, Ingredient

class RecipeFilter(FilterSet):
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all()
    )
    author = filters.NumberFilter(field_name='author__id')
    is_in_shopping_cart = filters.BooleanFilter(method='filter_is_in_shopping_cart')
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')

    def filter_is_in_shopping_cart(self, queryset, name, value):
        user = self.request.user
        if user.is_anonymous:
            return queryset.none() if value else queryset
        if value:
            return queryset.filter(in_shopping_carts__user=user)
        return queryset.exclude(in_shopping_carts__user=user)

    def filter_is_favorited(self, queryset, name, value):
        user = self.request.user
        if user.is_anonymous:
            return queryset.none() if value else queryset
        if value:
            return queryset.filter(favorited_by__user=user)
        return queryset.exclude(favorited_by__user=user)

    class Meta:
        model = Recipe
        fields = ['tags', 'author', 'is_in_shopping_cart', 'is_favorited']



class IngredientFilter(FilterSet):
    name = filters.CharFilter(field_name="name", lookup_expr="istartswith")

    class Meta:
        model = Ingredient
        fields = ['name']


# class ShoppingCartRecipeFilter(FilterSet):
#     is_in_shopping_cart = filters.BooleanFilter(method='filter_is_in_shopping_cart')

#     def filter_is_in_shopping_cart(self, queryset, name, value):
#         user = self.request.user
#         if user.is_anonymous:
#             return queryset.none() if value else queryset
#         if value:
#             return queryset.filter(shopping_cart__user=user)
#         return queryset.exclude(shopping_cart__user=user)

#     class Meta:
#         model = Recipe
#         fields = ['is_in_shopping_cart']