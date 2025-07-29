# boards/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Board, Workspace, List, Card
from .serializers import BoardSerializer
from .serializers import WorkspaceSerializer, ListSerializer, CardSerializer

class BoardListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        try:
            workspace = Workspace.objects.get(id=workspace_id, owner=request.user)
        except Workspace.DoesNotExist:
            return Response({'error': 'Workspace not found'}, status=404)

        boards = Board.objects.filter(workspace=workspace)
        serializer = BoardSerializer(boards, many=True)
        return Response(serializer.data)

    def post(self, request, workspace_id):
        try:
            workspace = Workspace.objects.get(id=workspace_id, owner=request.user)
        except Workspace.DoesNotExist:
            return Response({'error': 'Workspace not found'}, status=404)

        serializer = BoardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace=workspace, created_by=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class WorkspaceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workspaces = Workspace.objects.filter(owner=request.user)
        serializer = WorkspaceSerializer(workspaces, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WorkspaceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(owner=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    
class ListsCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id):
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        lists = List.objects.filter(board=board).order_by('position')
        serializer = ListSerializer(lists, many=True)
        return Response(serializer.data)

    def post(self, request, board_id):
        print("📥 Payload:", request.data)  # Debug nếu cần
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        serializer = ListSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(board=board)  # 👈 Gắn đúng foreign key
            return Response(serializer.data, status=201)

        return Response(serializer.errors, status=400)


class CardListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, list_id): 
        try:
            list_obj = List.objects.get(id=list_id)
        except List.DoesNotExist:
            return Response({'error': 'List not found'}, status=404)

        cards = Card.objects.filter(list=list_obj)
        serializer = CardSerializer(cards, many=True)
        return Response(serializer.data)

    def post(self, request, list_id):  
        try:
            list_obj = List.objects.get(id=list_id)
        except List.DoesNotExist:
            return Response({'error': 'List not found'}, status=404)

        serializer = CardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(list=list_obj)
            return Response(serializer.data, status=201)
        
        print("❌ Validation errors:", serializer.errors)
        return Response(serializer.errors, status=400)

class InboxCardCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        cards = Card.objects.filter(list__isnull=True, created_by=request.user).order_by('position')
        serializer = CardSerializer(cards, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = CardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class BoardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, board_id):
        try:
            board = Board.objects.get(id=board_id, workspace_id=workspace_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        serializer = BoardSerializer(board)
        return Response(serializer.data)

class CardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, card_id):
        try:
            card = Card.objects.get(id=card_id)
        except Card.DoesNotExist:
            return Response({'error': 'Card not found'}, status=404)

        print("🛠 PATCH data:", request.data)

        serializer = CardSerializer(card, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        print("❌ Validation error:", serializer.errors)
        return Response(serializer.errors, status=400)

class ListDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, list_id):
        try:
            list_obj = List.objects.get(id=list_id)
            
        except List.DoesNotExist:
            return Response({'error': 'List not found'}, status=404)

        serializer = ListSerializer(list_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
