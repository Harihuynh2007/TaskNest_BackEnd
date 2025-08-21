# boards/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
import uuid
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()

class Workspace(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    
class Board(models.Model):
    name = models.CharField(max_length=255)
    background = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, default='private')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
    User,
    related_name='boards',
    through='BoardMembership',
    blank=True    
    )

    is_closed = models.BooleanField(default=False)


class List(models.Model):
    name = models.CharField(max_length=128)
    position = models.IntegerField(default=0)
    background = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, default='private')
    created_at = models.DateTimeField(auto_now_add=True)
    board = models.ForeignKey(Board, on_delete=models.CASCADE)  # ✅ rename từ boardid → board

class Card(models.Model):
    name = models.CharField(max_length=255)
    background = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, default='private')
    description = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    list = models.ForeignKey(List, on_delete=models.SET_NULL, null=True, blank=True)  # ✅ rename từ listid → list
    STATUS_CHOICES = [
        ('doing', 'Doing'),
        ('done', 'Done'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='doing')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    labels = models.ManyToManyField("Label", blank=True, related_name='cards')
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='CardMembership',
        through_fields=('card', 'user'),
        related_name='card_memberships',
        blank=True,
    )
    
    # Watchers - những người theo dõi card nhưng không được assign
    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='watched_cards',
        blank=True,
    )
    position = models.IntegerField(default=0, db_index=True)  # ✅ index
class CardMembership(models.Model):
    """Intermediate model để lưu thêm thông tin về card membership"""
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='card_assignments_made'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(
        max_length=20,
        choices=[
            ('assignee', 'Assignee'),
            ('reviewer', 'Reviewer'),
            ('observer', 'Observer')
        ],
        default='assignee'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('card', 'user')

# Activity tracking
class CardActivity(models.Model):
    ACTIVITY_TYPES = [
        ('member_added', 'Member Added'),
        ('member_removed', 'Member Removed'),
        ('card_moved', 'Card Moved'),
        ('card_updated', 'Card Updated'),
        ('comment_added', 'Comment Added'),
        ('due_date_changed', 'Due Date Changed'),
    ]
    
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    target_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='card_activities_received'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

class Label(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='labels')

class BoardMembership(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_memberships')
    role = models.CharField(
        max_length=10,
        choices=[('admin', 'Admin'), ('editor', 'Editor'), ('viewer', 'Viewer')],
        default='viewer'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('board', 'user')


class BoardInviteLink(models.Model):
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('admin', 'Admin'),
        ('observer', 'Observer'),
    ]
    
    board = models.OneToOneField('Board', on_delete=models.CASCADE, related_name='invite_link')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'boards_boardinvitelink'
        verbose_name = 'Board Invite Link'
        verbose_name_plural = 'Board Invite Links'
    
    def __str__(self):
        return f"Invite link for {self.board.name}"
    
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    

class Comment(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']    

# Add to your models.py
class Checklist(models.Model):
    card = models.ForeignKey('Card', on_delete=models.CASCADE, related_name='checklists')
    title = models.CharField(max_length=255, default='Checklist')
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['position', 'created_at']

    @property
    def completion_percentage(self):
        total_items = self.items.count()
        if total_items == 0:
            return 0
        completed_items = self.items.filter(completed=True).count()
        return round((completed_items / total_items) * 100)

class ChecklistItem(models.Model):
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='items')
    text = models.TextField()
    completed = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    due_date = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_checklist_items')

    class Meta:
        ordering = ['position', 'created_at']        