from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class CustomUser(AbstractUser):
    email = models.EmailField(
        verbose_name='Email',
        unique=True,
        blank=False,
        null=False,
    )
    logo = models.ImageField(
        upload_to='images/logo',
        verbose_name='Лого',
        null=True,
        blank=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    objects = UserManager()

    def __str__(self):
        return self.email
    
