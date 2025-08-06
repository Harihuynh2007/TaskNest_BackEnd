from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Board, BoardMembership

@receiver(post_save, sender=Board)
def create_owner_as_editor_membership(sender, instance, created, **kwargs):
    if created:
        BoardMembership.objects.get_or_create(
            board=instance,
            user=instance.created_by,
            defaults={'role': 'editor'} # Cấp quyền EDITOR cho người tạo
        )