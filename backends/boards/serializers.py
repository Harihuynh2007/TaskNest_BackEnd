# boards/serializers.py
from rest_framework import serializers
from .models import Board
from .models import Workspace
from .models import List
from .models import Card
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
        fields = ['id', 'name', 'background', 'board', 'visibility']

class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'status', 'background', 'list']
        
