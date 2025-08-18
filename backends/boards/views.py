# boards/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db import transaction

from rest_framework import permissions


from .models import Board, Workspace, List, Card, Label, BoardMembership, BoardInviteLink,Comment
from .serializers import (
    BoardSerializer, WorkspaceSerializer, ListSerializer, CardSerializer, 
    LabelSerializer,
    UserShortSerializer, BoardMembershipSerializer, BoardInviteLinkSerializer,
    CommentSerializer,CardActivitySerializer,CardActivity,
    CardMembership,CardMembershipSerializer
)
from .decorators import require_board_admin, require_board_editor, require_card_editor, require_board_viewer
from .permissions import check_board_admin_permission,check_card_edit_permission, check_board_view_permission, IsBoardMember # Import hàm permission mới

User = get_user_model()


# ===================================================================
# Views cho Workspace và Board chính
# ===================================================================

class WorkspaceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workspaces = Workspace.objects.filter(Q(owner=request.user) | Q(board__members=request.user)).distinct()
        serializer = WorkspaceSerializer(workspaces, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BoardListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        boards = (Board.objects
                .filter(is_closed=False)
                .filter(Q(created_by=request.user) | Q(members=request.user))
                .distinct()
                .select_related('workspace'))  # ✅ thêm

        serializer = BoardSerializer(boards, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, workspace_id):
        DEFAULT_LABEL_COLORS = ['#61bd4f', '#f2d600', '#ff9f1a', '#eb5a46', '#c377e0', '#0079bf']
        try:
            workspace = Workspace.objects.get(id=workspace_id, owner=request.user)
        except Workspace.DoesNotExist:
            return Response({'error': 'You do not have permission to create a board in this workspace.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = BoardSerializer(data=request.data, context={'request': request, 'workspace': workspace})
        if serializer.is_valid():
            board = serializer.save()
            for color in DEFAULT_LABEL_COLORS:
                Label.objects.create(name='', color=color, board=board)
            return Response(BoardSerializer(board, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=400)


class BoardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @require_board_viewer(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def get(self, request, workspace_id, board_id):
        board = Board.objects.get(id=board_id, workspace_id=workspace_id)
        serializer = BoardSerializer(board, context={'request': request})
        return Response(serializer.data)

    @require_board_admin(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def patch(self, request, workspace_id, board_id):
        board = Board.objects.get(id=board_id, workspace_id=workspace_id)
        if 'is_closed' in request.data:
            board.is_closed = request.data['is_closed']
            board.save(update_fields=['is_closed'])
        serializer = BoardSerializer(board, context={'request': request})
        return Response(serializer.data)
        
    def delete(self, request, workspace_id, board_id):
        board = Board.objects.get(id=board_id, workspace_id=workspace_id)
        if board.created_by != request.user:
            return Response({'error': 'Only the board creator can permanently delete the board.'}, status=status.HTTP_403_FORBIDDEN)
        board.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ClosedBoardsListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        # views.py
        user_boards = (Board.objects
            .filter(Q(created_by=request.user) | Q(members=request.user), is_closed=True)
            .distinct()
            .select_related('workspace'))  # ✅ thay vì prefetch_related

        serializer = BoardSerializer(user_boards, many=True, context={'request': request})
        return Response(serializer.data)
    
# ===================================================================
# Views cho List và Card
# ===================================================================

class ListsCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @require_board_viewer(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def get(self, request, board_id):
        lists = List.objects.filter(board_id=board_id).order_by('position')
        serializer = ListSerializer(lists, many=True)
        return Response(serializer.data)

    @require_board_editor(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def post(self, request, board_id):
        serializer = ListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(board_id=board_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ListDetailView(APIView):
    permission_classes = [IsAuthenticated]
    @require_board_editor(lambda s, r, **k: List.objects.get(id=k['list_id']).board)
    def patch(self, request, list_id):
        list_obj = List.objects.get(id=list_id)
        serializer = ListSerializer(list_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @require_board_admin(lambda s, r, **k: List.objects.get(id=k['list_id']).board)
    def delete(self, request, list_id):
        list_obj = List.objects.get(id=list_id)
        Card.objects.filter(list=list_obj).update(list=None)
        list_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class CardListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @require_board_viewer(lambda s, r, **k: List.objects.get(id=k['list_id']).board)
    def get(self, request, list_id):
        # Tối ưu query ở đây
        cards = Card.objects.filter(list_id=list_id).prefetch_related('members').order_by('position')
        serializer = CardSerializer(cards, many=True)
        return Response(serializer.data)

    @require_board_editor(lambda s, r, **k: List.objects.get(id=k['list_id']).board)
    def post(self, request, list_id):
        serializer = CardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(list_id=list_id, created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class CardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @require_card_editor(lambda s, r, **k: Card.objects.get(id=k['card_id']))
    def patch(self, request, card_id):
        card = Card.objects.get(id=card_id)
        serializer = CardSerializer(card, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        serializer.save()
        return Response(serializer.data)
    
    @require_card_editor(lambda s, r, **k: Card.objects.get(id=k['card_id']))
    def delete(self, request, card_id):
        card = Card.objects.get(id=card_id)
        card.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class InboxCardCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user_accessible_boards = Board.objects.filter(Q(created_by=request.user) | Q(members=request.user)).distinct()
        all_related_user_ids = set()
        for board in user_accessible_boards:
            if board.created_by: all_related_user_ids.add(board.created_by.id)
            all_related_user_ids.update(board.members.values_list('id', flat=True))

        inbox_cards = (Card.objects
            .filter(list__isnull=True, created_by_id__in=all_related_user_ids)
            .prefetch_related('members')        # ✅ thêm
            .order_by('-created_at'))

        serializer = CardSerializer(inbox_cards, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = CardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CardBatchUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        updates = request.data
        if not isinstance(updates, list) or not updates:
            return Response({"error": "Request body must be a non-empty list"}, status=400)

        first_card = get_object_or_404(Card, id=updates[0].get("id"))
        if not first_card.list:
            return Response({"error": "Inbox cards cannot be batch-updated here"}, status=400)
        board = first_card.list.board
        check_board_admin_permission(board, request.user)  # ✅ kiểm tra admin/owner

        with transaction.atomic():
            for upd in updates:
                card = get_object_or_404(Card, id=upd.get("id"))
                if not card.list or card.list.board_id != board.id:
                    return Response({"error": "All cards must belong to the same board"}, status=400)
                ser = CardSerializer(card, data=upd, partial=True)
                ser.is_valid(raise_exception=True)
                ser.save()

        return Response({"message": "Cards updated successfully"}, status=200)
        
# ===================================================================
# View cho Members, Labels, và Share Link 
# ===================================================================

class BoardMembersView(APIView):
    permission_classes = [IsAuthenticated]

    @require_board_viewer(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def get(self, request, board_id):
        memberships = BoardMembership.objects.filter(board_id=board_id).select_related('user')
        serializer = BoardMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @require_board_admin(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def post(self, request, board_id):
        board = Board.objects.get(id=board_id)
        user_id_to_invite = request.data.get('user_id')
        role = request.data.get('role', 'viewer')
        if not user_id_to_invite: return Response({'error': 'user_id is required'}, status=400)
        if role not in ['admin', 'editor', 'viewer']: return Response({'error': 'Invalid role'}, status=400)
        try:
            user_to_invite = User.objects.get(id=user_id_to_invite)
        except User.DoesNotExist:
            return Response({'error': 'User to invite not found'}, status=404)
        if BoardMembership.objects.filter(board=board, user=user_to_invite).exists() or board.created_by == user_to_invite:
            return Response({'message': 'User is already a member.'}, status=400)
        membership = BoardMembership.objects.create(board=board, user=user_to_invite, role=role)
        print(f"[INVITE] Invited {user_to_invite.email} as {role}")
        serializer = BoardMembershipSerializer(membership)
        return Response(serializer.data, status=201)

    @require_board_admin(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def patch(self, request, board_id):
        board = Board.objects.get(id=board_id)
        user_id_to_update = request.data.get('user_id')
        new_role = request.data.get('role')
        if not user_id_to_update or not new_role: return Response({'error': 'user_id and role are required'}, status=400)
        if new_role not in ['admin', 'editor', 'viewer']: return Response({'error': 'Invalid role'}, status=400)
        try:
            membership = BoardMembership.objects.get(board_id=board_id, user_id=user_id_to_update)
            if membership.user == board.created_by: return Response({'error': 'Cannot change the role of the board owner.'}, status=400)
            membership.role = new_role
            membership.save()

            print(f"[ROLE CHANGE] {membership.user.email} → {new_role}")
            return Response(BoardMembershipSerializer(membership).data)
        except BoardMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=404)

    @require_board_admin(lambda s, r, **k: Board.objects.get(id=k['board_id']))
    def delete(self, request, board_id):
        board = Board.objects.get(id=board_id)
        user_id_to_remove = request.data.get('user_id')
        if not user_id_to_remove: return Response({'error': 'user_id is required'}, status=400)
        try:
            membership = BoardMembership.objects.get(board_id=board_id, user_id=user_id_to_remove)
            if membership.user == board.created_by: return Response({'error': 'Cannot remove the board creator.'}, status=400)
            membership.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BoardMembership.DoesNotExist:
            return Response({'error': 'Membership not found'}, status=404)
        

class BoardLabelListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @require_board_viewer(lambda self, request, board_id: Board.objects.get(id=board_id))
    def get(self, request, board_id):
        """Lấy danh sách tất cả labels của một board."""
        labels = Label.objects.filter(board_id=board_id)
        serializer = LabelSerializer(labels, many=True)
        return Response(serializer.data)

    @require_board_admin(lambda self, request, board_id: Board.objects.get(id=board_id))
    def post(self, request, board_id):
        """Tạo một label mới cho board."""
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

    @require_board_admin(lambda self, request, label_id: Label.objects.get(id=label_id).board)
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

    @require_board_admin(lambda self, request, label_id: Label.objects.get(id=label_id).board)
    def delete(self, request, label_id):
        try:
            label = Label.objects.get(id=label_id)
            label.delete()
            return Response(status=204)
        except Label.DoesNotExist:
            return Response({"error": "Label not found"}, status=404)


class BoardShareLinkView(APIView):
    permission_classes = [IsAuthenticated]

    @require_board_admin(lambda self, request, board_id: Board.objects.get(id=board_id))
    def get(self, request, board_id):
        # lấy link đang hoạt động (nếu có)
        invite = BoardInviteLink.objects.filter(board_id=board_id, is_active=True).first()
        if not invite:
            return Response({
                "has_active": False,
                "invite_link": None,
                "expires_at": None
            }, status=status.HTTP_200_OK)

        serializer = BoardInviteLinkSerializer(invite)
        return Response({
            "has_active": True,
            "token": serializer.data["token"],
            "expires_at": serializer.data.get("expires_at"),
        })

        

    @require_board_admin(lambda self, request, board_id: Board.objects.get(id=board_id))
    def post(self, request, board_id):
        role = request.data.get('role', 'member')
        # tạo mới hoặc update role cho link hiện có
        invite, _ = BoardInviteLink.objects.update_or_create(
            board_id=board_id,
            defaults={'role': role, 'is_active': True, 'created_by': request.user}
        )
        serializer = BoardInviteLinkSerializer(invite)
        return Response(serializer.data)

    @require_board_admin(lambda self, request, board_id: Board.objects.get(id=board_id))
    def delete(self, request, board_id):
        BoardInviteLink.objects.filter(board_id=board_id, is_active=True).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class BoardJoinByLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        # Lấy link mời đang active
        invite = get_object_or_404(BoardInviteLink, token=token, is_active=True)

        # Hết hạn?
        if invite.is_expired():
            return Response({'detail': 'Invite link has expired'}, status=status.HTTP_410_GONE)

        board = invite.board
        user = request.user

        # Đã là thành viên?
        if BoardMembership.objects.filter(board=board, user=user).exists():
            return Response({'detail': 'Already a member'}, status=status.HTTP_200_OK)

        # Map role của link → role trong BoardMembership
        # member -> editor, admin -> admin, observer -> viewer
        role_map = {
            'member':   'editor',
            'admin':    'admin',
            'observer': 'viewer',
        }
        membership_role = role_map.get(invite.role, 'viewer')

        BoardMembership.objects.create(board=board, user=user, role=membership_role)

        # (Tuỳ chọn) chỉ dùng link một lần:
        # invite.is_active = False
        # invite.save(update_fields=['is_active'])

        return Response(
            {'detail': 'Joined board successfully', 'role': membership_role},
            status=status.HTTP_201_CREATED
        )

       
class CardCommentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, card_id):
        card = Card.objects.select_related('list__board', 'created_by').get(id=card_id)
        # Quyền xem: nếu có list => dùng quyền xem board; nếu inbox => tác giả hoặc cùng board
        if card.list:
            check_board_view_permission(card.list.board, request.user)
        else:
            if card.created_by != request.user:
                # người dùng phải có ít nhất 1 board chung với tác giả
                from django.db.models import Q
                has_common = Board.objects.filter(
                    Q(created_by=request.user) | Q(members=request.user)
                ).filter(
                    Q(created_by=card.created_by) | Q(members=card.created_by)
                ).exists()
                if not has_common:
                    return Response({'detail': 'Forbidden'}, status=403)

        qs = Comment.objects.filter(card=card).order_by('-created_at')
        return Response(CommentSerializer(qs, many=True).data)

    def post(self, request, card_id):
        card = Card.objects.select_related('list__board').get(id=card_id)
        # Quyền tạo: dùng quyền sửa card (editor trở lên hoặc quy tắc inbox)
        check_card_edit_permission(card, request.user)

        ser = CommentSerializer(data={'content': request.data.get('content', ''), 'card': card.id})
        ser.is_valid(raise_exception=True)
        comment = Comment.objects.create(
            card=card,
            author=request.user,
            content=ser.validated_data['content']
        )
        return Response(CommentSerializer(comment).data, status=201)

class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, comment_id):
        cmt = Comment.objects.select_related('card__list__board').get(id=comment_id)
        # Cho sửa nếu là tác giả; hoặc có quyền editor trên board của card
        if cmt.author != request.user:
            check_card_edit_permission(cmt.card, request.user)

        ser = CommentSerializer(cmt, data={'content': request.data.get('content', '')}, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, comment_id):
        cmt = Comment.objects.select_related('card__list__board').get(id=comment_id)
        if cmt.author != request.user:
            check_card_edit_permission(cmt.card, request.user)
        cmt.delete()
        return Response(status=204)
    

class CardMembershipListCreateView(APIView):
    """
    Xử lý việc lấy danh sách và thêm thành viên vào một card.
    URL: /api/cards/<card_id>/memberships/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, card_id):
        """Lấy danh sách tất cả thành viên của card."""
        card = Card.objects.get(id=card_id)
        # Bất kỳ ai có quyền xem board đều có thể xem thành viên của card
        if card.list:
            check_board_view_permission(card.list.board, request.user)
        # (Bạn có thể thêm logic cho inbox card ở đây nếu cần)

        memberships = CardMembership.objects.filter(card=card).select_related('user', 'assigned_by')
        serializer = CardMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    def post(self, request, card_id):
        """Thêm một thành viên mới vào card với vai trò cụ thể."""
        card = Card.objects.get(id=card_id)
        # Cần quyền editor để thêm thành viên
        check_card_edit_permission(card, request.user)

        user_id_to_add = request.data.get('user_id')
        role = request.data.get('role', 'assignee')

        if not user_id_to_add:
            return Response({'detail': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate user is board member
        if not card.list:
            return Response({'detail': 'Cannot assign members to inbox cards'}, status=status.HTTP_400_BAD_REQUEST)
            
        board = card.list.board
        try:
            user_to_add = User.objects.get(id=user_id_to_add)
            if not BoardMembership.objects.filter(board=board, user=user_to_add).exists():
                return Response({'detail': 'User is not a board member'}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Tạo hoặc kích hoạt lại membership
        membership, created = CardMembership.objects.update_or_create(
            card=card,
            user=user_to_add,
            defaults={
                'assigned_by': request.user,
                'role': role,
                'is_active': True
            }
        )
        
        # Log activity chỉ khi thực sự tạo mới hoặc gán lại vai trò
        if created:
            description = f'assigned {user_to_add.username} as {role}'
        else:
            description = f'updated {user_to_add.username}\'s role to {role}'

        CardActivity.objects.create(
            card=card,
            user=request.user,
            activity_type='member_added',
            description=description,
            target_user=user_to_add
        )
        
        serializer = CardMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CardMembershipDetailView(APIView):
    """
    Xử lý việc cập nhật và xóa một thành viên cụ thể khỏi card.
    URL: /api/cards/<card_id>/memberships/<user_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, card_id, user_id):
        """Cập nhật vai trò của một thành viên trên card."""
        card = Card.objects.get(id=card_id)
        # Cần quyền editor để thay đổi vai trò
        check_card_edit_permission(card, request.user)

        new_role = request.data.get('role')
        if not new_role:
            return Response({'detail': 'role is required for update'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            membership = CardMembership.objects.get(card_id=card_id, user_id=user_id)
            old_role = membership.role
            membership.role = new_role
            membership.save()

            # Log activity
            CardActivity.objects.create(
                card=card,
                user=request.user,
                activity_type='card_updated',
                description=f'changed role for {membership.user.username} from {old_role} to {new_role}',
                target_user=membership.user
            )
            
            return Response(CardMembershipSerializer(membership).data)
        except CardMembership.DoesNotExist:
            return Response({'detail': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, card_id, user_id):
        """Xóa một thành viên khỏi card."""
        card = Card.objects.get(id=card_id)
        # Cần quyền editor để xóa thành viên
        check_card_edit_permission(card, request.user)
        
        try:
            membership = CardMembership.objects.get(card=card, user_id=user_id)
            target_user = membership.user
            membership.delete()
            
            # Log activity
            CardActivity.objects.create(
                card=card,
                user=request.user,
                activity_type='member_removed',
                description=f'removed {target_user.username} from the card',
                target_user=target_user
            )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except CardMembership.DoesNotExist:
            return Response({'detail': 'Membership not found'}, status=status.HTTP_404_NOT_FOUND)
        
class CardWatchersView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, card_id):
        """Get card watchers"""
        card = Card.objects.get(id=card_id)
        if card.list:
            check_board_view_permission(card.list.board, request.user)
        
        watchers = card.watchers.all()
        return Response(UserShortSerializer(watchers, many=True).data)
    
    def post(self, request, card_id):
        """Add/remove watcher"""
        card = Card.objects.get(id=card_id)
        if card.list:
            check_board_view_permission(card.list.board, request.user)
        
        action = request.data.get('action')  # 'add' or 'remove'
        
        if action == 'add':
            card.watchers.add(request.user)
            message = 'Added to watchers'
        else:
            card.watchers.remove(request.user)
            message = 'Removed from watchers'
            
        return Response({'message': message})

class CardActivityView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, card_id):
        """Get card activity history"""
        card = Card.objects.get(id=card_id)
        if card.list:
            check_board_view_permission(card.list.board, request.user)
        
        activities = card.activities.all()[:50]  # Latest 50 activities
        return Response(CardActivitySerializer(activities, many=True).data)