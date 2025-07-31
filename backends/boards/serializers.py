# boards/serializers.py
from rest_framework import serializers
from .models import Board
from .models import Workspace
from .models import List
from .models import Card
from .models import Label
from .models import BoardMembership
class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ['id', 'name', 'workspace', 'created_by', 'background', 'visibility']
        read_only_fields = ['created_by', 'workspace']

class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ['id', 'name']

class ListSerializer(serializers.ModelSerializer):
    class Meta:
        model = List
        fields = ['id', 'name', 'background', 'board', 'visibility', 'position']

class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'status', 'background', 'visibility',
            'list', 'description', 'due_date', 'completed', 'position', 
            'created_at','labels']
        read_only_fields = ['created_by']
        extra_kwargs = {
            'list': {'required': False}
        }
        
class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'name', 'color']

from django.contrib.auth import get_user_model
User = get_user_model()

class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class BoardMembershipSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)

    class Meta:
        model = BoardMembership
        fields = ['id', 'user', 'role', 'joined_at']