from djoser.views import UserViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

class CustomUserViewSet(UserViewSet):
    permission_classes = [IsAuthenticated]

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
