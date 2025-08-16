# auth_app/models.py
from django.db import models
from django.conf import settings
import uuid

def avatar_upload_to(instance, filename):
    return f'avatars/user_{instance.user.id}/{filename}'

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_to,
        blank=True,
        null=True
    )
    display_name = models.CharField(max_length=50, blank=True)  # tên hiển thị
    bio = models.TextField(blank=True, default="")
    def __str__(self):
        return f"Profile<{self.user_id}:{self.display_name or self.user}>"
