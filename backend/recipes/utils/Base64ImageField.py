import base64
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers


# Кастомный сериализатор для поля с картинками
class Base64ImageField(serializers.ImageField):

    def to_internal_value(self, data):
        if not data:
            return None
        if isinstance(data, str) and data.startswith("data:image"):
            if isinstance(data, str) and data.startswith("data:image"):
                format, imgstr = data.split(";base64,")
                ext = format.split("/")[-1]
                file_name = f"{uuid.uuid4()}.{ext}"
                data = ContentFile(base64.b64decode(imgstr), name=file_name)

        return super().to_internal_value(data)
