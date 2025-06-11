from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from djoser.views import UserViewSet
from recipes.models import Subscription

from .serializers import (CustomUserBaseSerializer,
                          CustomUserWithRecipesSerializer)

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["me", "retrieve"]:
            return CustomUserBaseSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=["post"], url_path="subscribe")
    def subscribe(self, request, id=None):
        """Подписаться на пользователя (POST /users/{id}/subscribe/)"""
        author = get_object_or_404(User, pk=id)
        current_user = request.user

        if current_user.id == author.id:
            return Response(
                {"errors": "Нельзя подписаться на самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Subscription.objects.filter(
            user=current_user, author=author
        ).exists():
            return Response(
                {"errors": "Вы уже подписаны на этого пользователя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Subscription.objects.create(user=current_user, author=author)
        serializer = CustomUserWithRecipesSerializer(
            author, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def unsubscribe(self, request, id=None):
        """Отписаться от пользователя (DELETE /users/{id}/subscribe/)."""
        try:
            author = User.objects.get(pk=id)
        except User.DoesNotExist:
            return Response(
                {"error": "Пользователь не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        current_user = request.user
        subscription = Subscription.objects.filter(
            user=current_user, author=author
        ).first()

        if not subscription:
            return Response(
                {
                    "error": "Вы не подписаны на этого пользователя.",
                    "details": (
                        f"User {current_user.id} is not subscribed to "
                        f"author {author.id}"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["put", "delete"], url_path="me/avatar")
    def avatar(self, request):
        user = request.user
        if request.method == "PUT":
            serializer = CustomUserBaseSerializer(
                user,
                data={"avatar": request.data.get("avatar")},
                partial=True,
                context={"request": request},
            )
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"avatar": user.avatar.url}, status=status.HTTP_200_OK
                )
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        elif request.method == "DELETE":
            user.avatar.delete(save=True)
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["get"], detail=False)
    def me(self, request):
        serializer = self.get_serializer(
            request.user, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
