from api.utils.Base64ImageField import Base64ImageField
from djoser.serializers import UserCreateSerializer
from recipes.models import (
    Favorite,
    Ingredient,
    IngredientInRecipe,
    Recipe,
    ShoppingCart,
    Subscription,
    Tag,
)
from rest_framework import serializers
from user.models import CustomUser


class CustomUserBaseSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_subscribed",
            "avatar",
        )

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(user=request.user, author=obj).exists()
        return False


class CustomUserWithRecipesSerializer(CustomUserBaseSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(CustomUserBaseSerializer.Meta):
        fields = CustomUserBaseSerializer.Meta.fields + (
            "recipes",
            "recipes_count",
        )

    def get_recipes(self, obj):
        request = self.context.get("request")
        recipes = obj.recipes.all()
        limit = request.query_params.get("recipes_limit")
        if limit and limit.isdigit():
            recipes = recipes[: int(limit)]
        return RecipeMiniSerializer(recipes, many=True).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class CustomUserCreateSerializer(UserCreateSerializer):
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "password",
        )


class TagReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "color", "slug")


class TagPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug")


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class SubscriptionSerializer(serializers.ModelSerializer):
    author = CustomUserWithRecipesSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ("author",)


class IngredientInRecipeReadSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source="ingredient.id")
    name = serializers.ReadOnlyField(source="ingredient.name")
    measurement_unit = serializers.ReadOnlyField(source="ingredient.measurement_unit")

    class Meta:
        model = IngredientInRecipe
        fields = ("id", "name", "measurement_unit", "amount")


class IngredientInRecipeWriteSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = IngredientInRecipe
        fields = ("id", "amount")


class RecipeReadSerializer(serializers.ModelSerializer):
    tags = TagPublicSerializer(many=True, read_only=True)
    author = CustomUserBaseSerializer(read_only=True)
    ingredients = IngredientInRecipeReadSerializer(
        many=True, source="recipe_ingredients", read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            "id",
            "tags",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        )

    def get_is_favorited(self, obj):
        user = self.context.get("request").user
        if user.is_anonymous:
            return False
        return obj.favorited_by.filter(user=user).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return ShoppingCart.objects.filter(user=request.user, recipe=obj).exists()


class WriteIngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = IngredientInRecipe
        fields = ("id", "amount")


class RecipeWriteSerializer(serializers.ModelSerializer):
    ingredients = WriteIngredientInRecipeSerializer(many=True, write_only=True)
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            "id",
            "ingredients",
            "tags",
            "image",
            "name",
            "text",
            "cooking_time",
        )

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError("Добавьте хотя бы один ингредиент.")
        unique_ingredients = set()
        for item in value:
            if item["id"] in unique_ingredients:
                raise serializers.ValidationError("Ингредиенты не должны повторяться.")
            unique_ingredients.add(item["id"])
        return value

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError("Нужно указать хотя бы один тег.")
        tag_ids = [tag.id for tag in value]
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError("Теги не должны повторяться.")
        return value

    def create_ingredients(self, ingredients_data, recipe):
        objs = []
        for item in ingredients_data:
            try:
                ingredient = Ingredient.objects.get(id=item["id"])
            except Ingredient.DoesNotExist:
                raise serializers.ValidationError(
                    f"Ингредиент с id {item['id']} не существует."
                )
            objs.append(
                IngredientInRecipe(
                    recipe=recipe,
                    ingredient=ingredient,
                    amount=item["amount"],
                )
            )
        IngredientInRecipe.objects.bulk_create(objs)

    def validate_cooking_time(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Время приготовления должно быть не меньше 1 минуты."
            )
        return value

    def create(self, validated_data):
        ingredients_data = validated_data.pop("ingredients")
        tags_data = validated_data.pop("tags")
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)
        self.create_ingredients(ingredients_data, recipe)
        return recipe

    def update(self, instance, validated_data):
        if "ingredients" not in self.initial_data:
            raise serializers.ValidationError(
                {
                    "ingredients": (
                        'Поле "ingredients" обязательно для обновления рецепта'
                    )
                }
            )
        if "tags" not in self.initial_data:
            raise serializers.ValidationError(
                {"tags": 'Поле "tags" обязательно для обновления рецепта.'}
            )

        ingredients_data = validated_data.pop("ingredients")
        tags_data = validated_data.pop("tags")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.tags.set(tags_data)
        instance.recipe_ingredients.all().delete()
        self.create_ingredients(ingredients_data, instance)

        instance.save()
        return instance


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ()
        read_only_fields = ()

    def to_representation(self, instance):
        recipe = instance.recipe
        return {
            "id": recipe.id,
            "name": recipe.name,
            "image": recipe.image.url if recipe.image else None,
            "cooking_time": recipe.cooking_time,
        }

    def validate(self, data):
        user = self.context["request"].user
        recipe = self.context["recipe"]
        if Favorite.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError("Рецепт уже в избранном.")
        return data


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "name": instance.name,
            "image": instance.image.url if instance.image else "",
            "cooking_time": instance.cooking_time,
        }

    def validate(self, data):
        user = self.context["request"].user
        recipe = self.context["recipe"]
        if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError("Рецепт уже в списке покупок.")
        return data


class RecipeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")
