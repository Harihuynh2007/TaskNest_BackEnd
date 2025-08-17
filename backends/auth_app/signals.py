
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Profile
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=User, dispatch_uid="auth_app_create_profile_once")
def ensure_user_profile(sender, instance, created, **kwargs):
    """
    Tạo profile khi user được tạo.
    Đồng thời đảm bảo user cũ luôn có profile (phòng khi signals chưa chạy trước đó).
    """
    if created:
        Profile.objects.get_or_create(user=instance)
        logger.info("Profile created for user: %s", instance.email)
    else:
        # Nếu vì lý do nào đó user cũ chưa có profile, bổ sung
        Profile.objects.get_or_create(user=instance)
