# boards/models.py
from django.db import models
from django.contrib.auth import get_user_model

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
    list = models.ForeignKey(List, on_delete=models.CASCADE, null=True, blank=True)  # ✅ rename từ listid → list
    STATUS_CHOICES = [
        ('doing', 'Doing'),
        ('done', 'Done'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='doing')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    position = models.IntegerField(default=0)