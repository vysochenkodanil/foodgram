import base64, uuid

from rest_framework import serializers
from django.core.files.base import ContentFile

from User.models import CustomUser
from User.serializers import CustomUserSerializer
from recipes.models import Tag, Ingredient, IngredientInRecipe, Favorite, Recipe, ShoppingCart 


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id','name','measurement_unit')


class IngredientInRecipeReadSerializer(serializers.ModelSerializer): #сериализатор для чтения в связной модели рецепта и ингридиента
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class IngredientInRecipeWriteSerializer(serializers.ModelSerializer): #сериализатор для записи в связной модели рецепта и ингридиента
    id = serializers.PrimaryKeyRelatedField(queryset = Ingredient.objects.all()) #
    amount = serializers.IntegerField(min_value=1)
    class Meta:
        model = IngredientInRecipe
        field = ('id','amount')


class RecipeReadSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = IngredientInRecipeReadSerializer(
        many=True,
        source='recipe_ingredients',
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart',
            'name', 'image', 'text', 'cooking_time'
        )

def get_is_favorited(self, obj):
    request = self.context.get('request')
    if request is None or request.user.is_anonymous:
        return False
    return Favorite.objects.filter(user=request.user, recipe=obj).exists()

def get_is_in_shopping_cart(self, obj):
    request = self.context.get('request')
    if request is None or request.user.is_anonymous:
        return False
    return ShoppingCart.objects.filter(user=request.user, recipe=obj).exists()


class Base64ImageField(serializers.ImageField): #Кастомный сериализатор для поля с картинками
    
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # Пример строки:
            # data:image/png;base64,iVBORw0KGgoAAAANS...
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f'{uuid.uuid4()}.{ext}'
            data = ContentFile(base64.b64decode(imgstr), name=file_name)

        return super().to_internal_value(data)


class WriteIngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'amount')


class RecipeWriteSerializer(serializers.ModelSerializer):
    ingredients = WriteIngredientInRecipeSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'ingredients', 'tags', 'image',
            'name', 'text', 'cooking_time'
        )

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError('Добавьте хотя бы один ингредиент.')
        unique_ingredients = set()
        for item in value:
            if item['id'] in unique_ingredients:
                raise serializers.ValidationError('Ингредиенты не должны повторяться.')
            unique_ingredients.add(item['id'])
        return value

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError('Нужно указать хотя бы один тег.')
        return value

    def create_ingredients(self, ingredients_data, recipe):
        objs = []
        for item in ingredients_data:
            objs.append(
                IngredientInRecipe(
                    recipe=recipe,
                    ingredient=item['id'],
                    amount=item['amount']
                )
            )
        IngredientInRecipe.objects.bulk_create(objs)

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data, author=self.context['request'].user)
        recipe.tags.set(tags_data)
        self.create_ingredients(ingredients_data, recipe)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if tags_data is not None:
            instance.tags.set(tags_data)
        if ingredients_data is not None:
            instance.recipe_ingredients.all().delete()
            self.create_ingredients(ingredients_data, instance)

        instance.save()
        return instance


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = fields

    def to_representation(self, instance):
        return {
            'id': instance.recipe.id,
            'name': instance.recipe.name,
            'image': instance.recipe.image.url if instance.recipe.image else None,
            'cooking_time': instance.recipe.cooking_time,
        }

    def validate(self, data):
        user = self.context['request'].user
        recipe = self.context['recipe']
        if Favorite.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError('Рецепт уже в избранном.')
        return data
    
class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCart
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = fields

    def to_representation(self, instance):
        return {
            'id': instance.recipe.id,
            'name': instance.recipe.name,
            'image': instance.recipe.image.url if instance.recipe.image else None,
            'cooking_time': instance.recipe.cooking_time,
        }

    def validate(self, data):
        user = self.context['request'].user
        recipe = self.context['recipe']
        if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError('Рецепт уже в списке покупок.')
        return data

class FollowSerializer(serializers.ModelSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = (
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'recipes', 'recipes_count', 'logo'
        )

    def get_is_subscribed(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and user.follower.filter(author=obj).exists()

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[:int(limit)]
        serializer = RecipeReadSerializer(recipes, many=True, context=self.context)
        return serializer.data

    def get_recipes_count(self, obj):
        return obj.recipes.count()
