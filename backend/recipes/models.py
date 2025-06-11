from django.db import models
from django.contrib.auth import get_user_model
from user.models import CustomUser

User = get_user_model()


class Tag(models.Model):
    name = models.CharField(max_length=32, unique=True, verbose_name="Название")
    slug = models.SlugField(max_length=32, unique=True, verbose_name="Slug")
    color = models.CharField(max_length=7, verbose_name="Цвет в HEX", default="#FFFFFF")

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recipes")
    name = models.CharField(max_length=256)
    image = models.ImageField(upload_to="recipes/images/")
    text = models.TextField()
    cooking_time = models.PositiveIntegerField()
    tags = models.ManyToManyField(Tag, related_name="recipes")
    pub_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Дата публикации", null=True, blank=True
    )

    def __str__(self):
        return self.name


class ShoppingCart(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="shopping_cart"
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="in_shopping_carts"
    )

    class Meta:
        unique_together = ("user", "recipe")


class Ingredient(models.Model):
    name = models.CharField(max_length=128, unique=True)
    measurement_unit = models.CharField(max_length=32)

    def __str__(self):
        return f"{self.name} ({self.measurement_unit})"


class IngredientInRecipe(models.Model):
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="recipe_ingredients"
    )
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField()

    class Meta:
        unique_together = ("recipe", "ingredient")


class Subscription(models.Model):
    user = models.ForeignKey(
        CustomUser, related_name="subscriptions", on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        CustomUser, related_name="followers", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("user", "author")


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="favorited_by"
    )

    class Meta:
        unique_together = ("user", "recipe")
