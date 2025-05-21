from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    logo = models.ImageField(
        upload_to='images/logo',
        verbose_name='Лого',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

