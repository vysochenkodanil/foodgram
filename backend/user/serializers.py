from rest_framework import serializers
from djoser.serializers import UserCreateSerializer

from .models import CustomUser
from recipes.models import Subscription, Recipe
from recipes.utils.Base64ImageField import Base64ImageField

class CustomUserBaseSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'first_name', 'last_name',
            'email', 'is_subscribed', 'avatar'
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(
                user=request.user,
                author=obj
            ).exists()
        return False

class CustomUserWithRecipesSerializer(CustomUserBaseSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(CustomUserBaseSerializer.Meta):
        fields = CustomUserBaseSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes = obj.recipes.all()
        limit = request.query_params.get('recipes_limit')
        if limit and limit.isdigit():
            recipes = recipes[:int(limit)]
        return RecipeMiniSerializer(recipes, many=True).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()

class CustomUserCreateSerializer(UserCreateSerializer):
    
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta:
        model = CustomUser
        fields = (
            'id', 'email', 'username',
            'first_name', 'last_name',
            'password',
        )
        
class RecipeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')