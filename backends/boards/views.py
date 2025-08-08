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
from .models import BoardMembership,BoardInviteLink
from .serializers import BoardMembershipSerializer,BoardInviteLinkSerializer
from .decorators import require_board_editor, require_board_viewer,require_card_editor

from django.db.models import Q
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

        boards = Board.objects.filter(Q(workspace=workspace) | Q(memberships__user=request.user), is_closed=False)
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
        # 1. Tìm tất cả các board mà user hiện tại là thành viên hoặc là owner
        user_accessible_boards = Board.objects.filter(
            Q(created_by=request.user) | Q(members=request.user)
        ).distinct()

        #2. Tìm tất cả các card không có list (list__isnull=True)
        # VÀ được tạo bởi một người nào đó trong các board mà user này có quyền truy cập.
        # Điều này ngăn inbox của user A hiển thị card rác từ board Z mà họ không liên quan.
        
        # Lấy tất cả các thành viên (bao gồm cả owner) của các board này
        all_board_members_ids = set()
        for board in user_accessible_boards:
            all_board_members_ids.add(board.created_by_id)
            for member in board.members.all():
                all_board_members_ids.add(member.id)

        # 3. Lấy card không có list và được tạo bởi bất kỳ ai trong nhóm thành viên đó.
        inbox_cards = Card.objects.filter(
            list__isnull=True, 
            created_by_id__in=all_board_members_ids
        ).order_by('position')
        
        serializer = CardSerializer(inbox_cards, many=True)
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

    @require_board_editor(lambda self, request, workspace_id, board_id: Board.objects.get(id=board_id))
    def patch(self, request, workspace_id, board_id):
        try:
            board = Board.objects.get(id=board_id, workspace_id=workspace_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=4.404)
        
        # Chỉ cho phép cập nhật một số trường nhất định, ví dụ `is_closed`
        # Điều này an toàn hơn là dùng serializer đầy đủ
        if 'is_closed' in request.data:
            board.is_closed = request.data['is_closed']
            board.save(update_fields=['is_closed'])
        
        serializer = BoardSerializer(board)
        return Response(serializer.data)
    
    # Chỉ chủ sở hữu (creator) mới được xóa vĩnh viễn
    def delete(self, request, workspace_id, board_id):
        try:
            board = Board.objects.get(id=board_id, workspace_id=workspace_id)
            # Kiểm tra quyền hạn nghiêm ngặt
            if board.created_by != request.user:
                return Response({'error': 'Only the board creator can permanently delete the board.'}, status=status.HTTP_403_FORBIDDEN)
            
            board.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=status.HTTP_404_NOT_FOUND)
        
class ClosedBoardsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lấy tất cả các board mà user là owner HOẶC là member, VÀ board đó đã đóng
        user_boards = Board.objects.filter(
            Q(created_by=request.user) | Q(members=request.user),
            is_closed=True
        ).distinct() # Dùng distinct() để tránh trả về board trùng lặp nếu user vừa là owner vừa là member

        # Chúng ta cần thông tin workspace của mỗi board, nên dùng prefetch_related
        user_boards = user_boards.prefetch_related('workspace')

        # Dùng BoardSerializer hiện tại là đủ, vì nó đã có các trường cần thiết
        serializer = BoardSerializer(user_boards, many=True)
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
        
    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))  
    def post(self, request, board_id):

        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=404)

        # 1. Kiểm tra quyền của người mời (decorator đã làm, nhưng kiểm tra lại cho chắc)
        # Trello cho phép editor mời, nhưng chúng ta có thể giới hạn cho creator
        if request.user != board.created_by:
            return Response({'error': 'Only the board creator can invite new members.'}, status=status.HTTP_403_FORBIDDEN)
        
        user_id_to_invite = request.data.get('user_id')

        # 2. Validate input
        if not user_id_to_invite:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Kiểm tra user được mời có tồn tại không
        try:
            user_to_invite = User.objects.get(id=user_id_to_invite)
        except User.DoesNotExist:
            return Response({'error': 'User to invite not found'}, status=status.HTTP_404_NOT_FOUND)

         # 4. Kiểm tra user đã là thành viên hay creator chưa
        if BoardMembership.objects.filter(board=board, user=user_to_invite).exists() or board.created_by == user_to_invite:
            return Response({'message': 'User is already a member of this board.'}, status=status.HTTP_400_BAD_REQUEST)

        # 5. Tất cả đã hợp lệ -> Tạo membership
        role = request.data.get('role', 'viewer') # Lấy role từ request, mặc định là viewer
        if role not in ['viewer', 'editor']:
            role = 'viewer' # Đảm bảo role hợp lệ

        membership = BoardMembership.objects.create(board=board, user=user_to_invite, role=role)
        
        serializer = BoardMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
    def patch(self, request, board_id): # Cập nhật vai trò
        user_id_to_update = request.data.get('user_id')
        new_role = request.data.get('role')

        if not user_id_to_update or not new_role:
            return Response({'error': 'user_id and role are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if new_role not in ['editor', 'viewer']:
            return Response({'error': 'Invalid role'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            membership = BoardMembership.objects.get(board_id=board_id, user_id=user_id_to_update)
            
            # Chỉ creator mới được thay đổi vai trò
            if request.user != membership.board.created_by:
                return Response({'error': 'Only the board creator can change roles'}, status=status.HTTP_403_FORBIDDEN)
            
            membership.role = new_role
            membership.save()
            
            # Trả về thông tin member đã được cập nhật
            serializer = BoardMembershipSerializer(membership)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except BoardMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
    def delete(self, request, board_id): # Xóa thành viên
        user_id_to_remove = request.data.get('user_id')
        
        if not user_id_to_remove:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            membership = BoardMembership.objects.get(board_id=board_id, user_id=user_id_to_remove)
            
            # Creator không thể bị xóa khỏi board
            if membership.user == membership.board.created_by:
                return Response({'error': 'Cannot remove the board creator'}, status=status.HTTP_400_BAD_REQUEST)

            # Chỉ creator hoặc chính user đó mới được quyền xóa
            if not (request.user == membership.board.created_by or request.user.id == int(user_id_to_remove)):
                 return Response({'error': 'You do not have permission to remove this member'}, status=status.HTTP_403_FORBIDDEN)
            
            membership.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BoardMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)    
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

    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
    def post(self, request, board_id): # Mời thành viên mới
        try:
            board = Board.objects.get(id=board_id)
        except Board.DoesNotExist:
            return Response({'error': 'Board not found'}, status=status.HTTP_404_NOT_FOUND)

        # 1. Kiểm tra quyền của người mời (có thể chỉ cho creator)
        if request.user != board.created_by:
            return Response({'error': 'Only the board creator can invite new members.'}, status=status.HTTP_403_FORBIDDEN)
        
        user_id_to_invite = request.data.get('user_id')
        
        # 2. Validate input: Đảm bảo user_id được gửi lên
        if not user_id_to_invite:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Kiểm tra user được mời có tồn tại không
        try:
            user_to_invite = User.objects.get(id=user_id_to_invite)
        except User.DoesNotExist:
            return Response({'error': 'User to invite not found'}, status=status.HTTP_404_NOT_FOUND)

        # 4. Kiểm tra xem user đã là thành viên hay chưa
        if BoardMembership.objects.filter(board=board, user=user_to_invite).exists():
            return Response({'message': 'User is already a member of this board.'}, status=status.HTTP_400_BAD_REQUEST)

        # 5. Tất cả đã hợp lệ -> Tạo membership
        # Lấy vai trò từ request, mặc định là 'viewer'
        role = request.data.get('role', 'viewer')
        if role not in ['editor', 'viewer']:
            role = 'viewer'

        membership = BoardMembership.objects.create(board=board, user=user_to_invite, role=role)
        
        serializer = BoardMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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

    # ✅ THÊM TOÀN BỘ METHOD NÀY VÀO
    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
    def delete(self, request, board_id): # Xóa thành viên
        user_id_to_remove = request.data.get('user_id')
        
        if not user_id_to_remove:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            membership = BoardMembership.objects.get(board_id=board_id, user_id=user_id_to_remove)
            
            # Người tạo board không thể bị xóa
            if membership.user == membership.board.created_by:
                return Response({'error': 'Cannot remove the board creator'}, status=status.HTTP_400_BAD_REQUEST)

            # Chỉ người tạo hoặc chính user đó mới có quyền tự xóa mình
            if not (request.user == membership.board.created_by or request.user.id == int(user_id_to_remove)):
                 return Response({'error': 'You do not have permission to remove this member'}, status=status.HTTP_403_FORBIDDEN)
            
            membership.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BoardMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)

class BoardShareLinkView(APIView):
    permission_classes = [IsAuthenticated]

    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
    def get(self, request, board_id):
        # lấy link đang hoạt động (nếu có)
        invite = BoardInviteLink.objects.filter(board_id=board_id, is_active=True).first()
        if not invite:
            return Response({'detail': 'No active invite link'}, status=404)
        serializer = BoardInviteLinkSerializer(invite)
        return Response(serializer.data)

    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
    def post(self, request, board_id):
        role = request.data.get('role', 'member')
        # tạo mới hoặc update role cho link hiện có
        invite, _ = BoardInviteLink.objects.update_or_create(
            board_id=board_id,
            defaults={'role': role, 'is_active': True, 'created_by': request.user}
        )
        serializer = BoardInviteLinkSerializer(invite)
        return Response(serializer.data)

    @require_board_editor(lambda self, request, board_id: Board.objects.get(id=board_id))
    def delete(self, request, board_id):
        BoardInviteLink.objects.filter(board_id=board_id, is_active=True).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class BoardJoinByLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        try:
            invite = BoardInviteLink.objects.get(token=token, is_active=True)
        except BoardInviteLink.DoesNotExist:
            return Response({'detail': 'Invalid or expired link'}, status=404)

        board = invite.board
        user = request.user

        # Nếu đã là thành viên thì không cần thêm nữa
        if BoardMembership.objects.filter(board=board, user=user).exists():
            return Response({'detail': 'Already a member'}, status=400)

        # map role của link thành role trong BoardMembership
        membership_role = 'editor' if invite.role == 'member' else 'viewer'
        BoardMembership.objects.create(board=board, user=user, role=membership_role)
        return Response({'detail': 'Joined board successfully'})
