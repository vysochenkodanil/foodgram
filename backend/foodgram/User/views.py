from djoser.views import UserViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from recipes.models import Subscription
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404

User = get_user_model()

class CustomUserViewSet(UserViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'], url_path='subscribe')
    def subscribe(self, request, id=None):
        author = get_object_or_404(User, pk=id)
        current_user = request.user

        if current_user.id == author.id:
            return Response(
                {'errors': 'Нельзя подписаться на самого себя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if Subscription.objects.filter(user=current_user, author=author).exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Subscription.objects.create(user=current_user, author=author)

        from recipes.serializers import FollowSerializer
        serializer = FollowSerializer(author, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=['get'])
    def subscriptions(self, request):
        # Получаем подписки текущего пользователя
        subscriptions = request.user.subscriptions.all()
        # Получаем пользователей из подписок
        subscribed_users = [sub.author for sub in subscriptions]
        
        # Применяем пагинацию
        page = self.paginate_queryset(subscribed_users)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    
    @action(detail=False, methods=['put', 'delete'], url_path='me/avatar')
    def avatar(self, request):
        user = request.user

        if request.method == 'PUT':
            avatar_data = request.data.get('avatar')

            if not avatar_data:
                return Response({'error': 'Не передано изображение'}, status=status.HTTP_400_BAD_REQUEST)

            user.avatar = avatar_data
            user.save()
            return Response({'avatar': user.avatar.url if user.avatar else None}, status=status.HTTP_200_OK)

        elif request.method == 'DELETE':
            user.avatar.delete(save=True)
            return Response(status=status.HTTP_204_NO_CONTENT)