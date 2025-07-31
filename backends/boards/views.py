# boards/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Board, Workspace, List, Card, Label
from .serializers import BoardSerializer
from .serializers import WorkspaceSerializer, ListSerializer, CardSerializer,LabelSerializer
from boards.serializers import UserShortSerializer
from rest_framework import status

# Tạm tắt WebSocket để tránh lỗi Redis
# channel_layer = get_channel_layer()


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
            board = serializer.save(workspace=workspace, created_by=request.user)

            DEFAULT_LABEL_COLORS = [
                '#61bd4f', '#f2d600', '#ff9f1a', '#eb5a46', '#c377e0',
                '#0079bf', '#00c2e0', '#51e898', '#ff78cb', '#344563',
            ]
            for color in DEFAULT_LABEL_COLORS:
                Label.objects.create(name='', color=color, board=board)

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

        cards = Card.objects.filter(list=list_obj).order_by('position')
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

            #channel_layer = get_channel_layer()
            #board_id = card.list.board_id if card.list else card.created_by.board_set.first().id
            #async_to_sync(channel_layer.group_send)(
            #    f'board_{board_id}',
            #    {'type': 'card_update'}
            #)
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

class BoardMembersView(APIView):
    def get(self, request, board_id):
        try:
            board = Board.objects.get(id=board_id)
            members = board.members.all()
            serializer = UserShortSerializer(members, many=True)
            return Response(serializer.data)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)
        
class BoardLabelsView(APIView):
    def get(self, request, board_id):
        labels = Label.objects.filter(board_id=board_id)
        serializer = LabelSerializer(labels, many=True)
        return Response(serializer.data)

class LabelCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, board_id):
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({"error": "Board not found"}, status=404)

        serializer = LabelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(board=board)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class LabelDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, label_id):
        try:
            label = Label.objects.get(id=label_id)
        except Label.DoesNotExist:
            return Response({"error": "Label not found"}, status=404)

        serializer = LabelSerializer(label, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, label_id):
        try:
            label = Label.objects.get(id=label_id)
            label.delete()
            return Response(status=204)
        except Label.DoesNotExist:
            return Response({"error": "Label not found"}, status=404)



class CardBatchUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        updates = request.data
        if not isinstance(updates, list):
            return Response({"error": "Request body must be a list of updates"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            board_id = None
            for update in updates:
                card_id = update.get("id")
                card = Card.objects.get(id=card_id, created_by=request.user)
                serializer = CardSerializer(card, data=update, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    if not board_id:
                        board_id = card.list.board_id if card.list else card.created_by.board_set.first().id
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Gửi thông báo WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'board_{board_id}',
                {'type': 'card_update'}
            )
            return Response({"message": "Cards updated successfully"}, status=status.HTTP_200_OK)
        except Card.DoesNotExist:
            return Response({"error": "One or more cards not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)