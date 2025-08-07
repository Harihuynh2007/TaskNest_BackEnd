# boards/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Board, Workspace, List, Card, Label
from .serializers import BoardSerializer
from .serializers import WorkspaceSerializer, ListSerializer, CardSerializer,LabelSerializer
from boards.serializers import UserShortSerializer
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import BoardMembership
from .serializers import BoardMembershipSerializer
from .decorators import require_board_editor, require_board_viewer,require_card_editor
# Tạm tắt WebSocket để tránh lỗi Redis
# channel_layer = get_channel_layer()

User = get_user_model()

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
    @require_board_viewer(lambda self, request, board_id: Board.objects.get(id=board_id))
    def get(self, request, board_id):
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        lists = List.objects.filter(board=board).order_by('position')
        serializer = ListSerializer(lists, many=True)
        return Response(serializer.data)

    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))   
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
    @require_board_viewer(lambda self, request, list_id: List.objects.get(id=list_id).board)
    def get(self, request, list_id): 
        try:
            list_obj = List.objects.get(id=list_id)
        except List.DoesNotExist:
            return Response({'error': 'List not found'}, status=404)

        cards = Card.objects.filter(list=list_obj).order_by('position')
        serializer = CardSerializer(cards, many=True)
        return Response(serializer.data)

    @require_board_editor(lambda self, request, list_id: List.objects.get(id=list_id).board)
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

    @require_board_viewer(lambda self, request, workspace_id, board_id: Board.objects.get(id=board_id, workspace_id=workspace_id))
    def get(self, request, workspace_id, board_id):
        try:
            board = Board.objects.get(id=board_id, workspace_id=workspace_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        serializer = BoardSerializer(board)
        return Response(serializer.data)

class CardDetailView(APIView):
    permission_classes = [IsAuthenticated]
    @require_card_editor(lambda self, request, card_id: Card.objects.get(id=card_id))
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
    
    @require_card_editor(lambda self, request, card_id: Card.objects.get(id=card_id))
    def delete(self, request, card_id):
        try:
            card = Card.objects.get(id=card_id)
            card.delete()
            # Trả về 204 No Content là chuẩn RESTful cho hành động xóa thành công
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Card.DoesNotExist:
            return Response({'error': 'Card not found'}, status=status.HTTP_404_NOT_FOUND)
        

class ListDetailView(APIView):
    permission_classes = [IsAuthenticated]
    @require_board_editor(lambda self, request, list_id: List.objects.get(id=list_id).board)
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
    
    @require_board_editor(lambda self, request, list_id: List.objects.get(id=list_id).board)
    def delete(self, request, list_id):
        try:
            list_obj = List.objects.get(id=list_id)

            # Logic mới: Chuyển tất cả card trong list này về trạng thái "inbox"
            # bằng cách gán `list` của chúng thành None.
            Card.objects.filter(list=list_obj).update(list=None)

            # Sau khi đã "giải phóng" các card, tiến hành xóa list rỗng
            list_obj.delete()
            
            # Trả về thành công
            return Response(status=status.HTTP_204_NO_CONTENT)
        except List.DoesNotExist:
            return Response({'error': 'List not found'}, status=status.HTTP_404_NOT_FOUND)

class BoardMembersView(APIView):
    permission_classes = [IsAuthenticated]

    @require_board_viewer(lambda self, request, board_id: Board.objects.get(id=board_id))
    def get(self, request, board_id):
        try:
            board = Board.objects.get(id=board_id)
            members = board.members.all()
            serializer = UserShortSerializer(members, many=True)
            return Response(serializer.data)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)
        
    def post(self, request, board_id):
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        # ✅ Chỉ người tạo mới được mời
        if request.user != board.created_by:
            return Response({'error': 'Only board creator can invite members'}, status=403)
        
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required'}, status=400)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        if user in board.members.all():
            return Response({'message': 'User already in board'}, status=200)

        board.members.add(user)
        return Response({'message': 'User added successfully'}, status=200)
class BoardLabelsView(APIView):
    @require_board_viewer(lambda self, request, board_id: Board.objects.get(id=board_id))
    def get(self, request, board_id):
        labels = Label.objects.filter(board_id=board_id)
        serializer = LabelSerializer(labels, many=True)
        return Response(serializer.data)

class LabelCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
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

    @require_board_editor(lambda self, request, label_id: Label.objects.get(id=label_id).board)
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

    @require_board_editor(lambda self, request, label_id: Label.objects.get(id=label_id).board)
    def delete(self, request, label_id):
        try:
            label = Label.objects.get(id=label_id)
            label.delete()
            return Response(status=204)
        except Label.DoesNotExist:
            return Response({"error": "Label not found"}, status=404)



class CardBatchUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @require_board_editor(lambda self, request: Board.objects.get(id=request.data[0]['board_id']))
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
            #channel_layer = get_channel_layer()
            #async_to_sync(channel_layer.group_send)(
            #    f'board_{board_id}',
            #    {'type': 'card_update'}
            #)
            return Response({"message": "Cards updated successfully"}, status=status.HTTP_200_OK)
        except Card.DoesNotExist:
            return Response({"error": "One or more cards not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class BoardMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id):   # Get members list of a board
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        memberships = BoardMembership.objects.filter(board_id=board_id)
        serializer = BoardMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    def post(self, request, board_id):  # Invite member
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        if request.user != board.created_by:
            return Response({'error': 'Only creator can invite'}, status=403)

        user_id = request.data.get('user_id')
        if BoardMembership.objects.filter(board=board, user_id=user_id).exists():
            return Response({'message': 'User already in board'}, status=200)

        BoardMembership.objects.create(board=board, user_id=user_id, role='viewer')
        return Response({'message': 'User added'}, status=201)

    def patch(self, request, board_id):  # Update member role
        user_id = request.data.get('user_id')
        new_role = request.data.get('role')
        if new_role not in ['viewer', 'editor']:
            return Response({'error': 'Invalid role'}, status=400)

        try:
            membership = BoardMembership.objects.get(board_id=board_id, user_id=user_id)
        except BoardMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=404)

        if request.user != membership.board.created_by:
            return Response({'error': 'Only creator can change roles'}, status=403)

        membership.role = new_role
        membership.save()
        return Response({'message': 'Role updated'}, status=200)
