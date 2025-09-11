# boards/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics,status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django.http import FileResponse
from django.utils.encoding import smart_str

from urllib.parse import urlparse

from rest_framework import permissions


from .models import Board, Workspace, List, Card, Label, BoardMembership, BoardInviteLink,Comment,Checklist, ChecklistItem,Attachment
from .serializers import (
    BoardSerializer, WorkspaceSerializer, ListSerializer, CardSerializer, 
    LabelSerializer,
    UserShortSerializer, BoardMembershipSerializer, BoardInviteLinkSerializer,
    CommentSerializer,CardActivitySerializer,CardActivity,
    CardMembership,CardMembershipSerializer,ChecklistSerializer, ChecklistItemSerializer,
    AttachmentSerializer
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
        old_data = {
            'list': card.list,
            'due_date': card.due_date,
            'description': card.description,
            'name': card.name,
            'labels': set(card.labels.all())
        }
        
        serializer = CardSerializer(card, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Save changes
        updated_card = serializer.save()
        
        # Log specific changes
        self._log_card_changes(card, old_data, request.user, request.data)
        
        return Response(serializer.data)
    
    def _log_card_changes(self, card, old_data, user, new_data):
        """Log specific changes made to card"""
        
        # Card moved between lists
        if 'list' in new_data and old_data['list'] != card.list:
            if old_data['list'] and card.list:
                description = f'moved card from "{old_data["list"].name}" to "{card.list.name}"'
            elif card.list:
                description = f'moved card to "{card.list.name}"'
            else:
                description = f'moved card from "{old_data["list"].name}" to Inbox'
                
            CardActivity.objects.create(
                card=card,
                user=user,
                activity_type='card_moved',
                description=description
            )

        if 'due_date' in new_data and old_data['due_date'] != card.due_date:
                if card.due_date:
                    description = f'set due date to {card.due_date.strftime("%b %d at %I:%M %p")}'
                else:
                    description = 'removed due date'
                    
                CardActivity.objects.create(
                    card=card,
                    user=user,
                    activity_type='due_date_changed',
                    description=description
                )

        if 'description' in new_data and old_data['description'] != card.description:
            if card.description and card.description.strip():
                description = 'updated card description'
            else:
                description = 'removed card description'
                
            CardActivity.objects.create(
                card=card,
                user=user,
                activity_type='card_updated',
                description=description
            )     

        if 'name' in new_data and old_data['name'] != card.name:
            CardActivity.objects.create(
                card=card,
                user=user,
                activity_type='card_updated',
                description=f'renamed card to "{card.name}"'
            )    

        # Labels changed (if labels are updated via card endpoint)
        if 'labels' in new_data:
            current_labels = set(card.labels.values_list("id", flat=True))
            old_labels = {l.id for l in old_data['labels']}
            added_labels = current_labels - old_data['labels']
            removed_labels = old_data['labels'] - current_labels
            
            for label in added_labels:
                CardActivity.objects.create(
                    card=card,
                    user=user,
                    activity_type='card_updated',
                    description=f'added label "{label.name}"'
                )
            
            for label in removed_labels:
                CardActivity.objects.create(
                    card=card,
                    user=user,
                    activity_type='card_updated',
                    description=f'removed label "{label.name}"'
                )       
                    

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

class ActivityLogger:
    @staticmethod
    def log_card_creation(card, user):
        CardActivity.objects.create(
            card=card,
            user=user,
            activity_type='card_updated',
            description='created card'
        )
    
    @staticmethod
    def log_card_archive(card, user):
        CardActivity.objects.create(
            card=card,
            user=user,
            activity_type='card_updated',
            description='archived card'
        )
    
    @staticmethod
    def log_card_unarchive(card, user):
        CardActivity.objects.create(
            card=card,
            user=user,
            activity_type='card_updated',
            description='restored card from archive'
        )    

# -------------------
# Checklist CRUD
# -------------------
class CardChecklistListView(generics.ListCreateAPIView):
    """
    GET: lấy toàn bộ checklist trong card
    POST: tạo checklist mới trong card
    """
    serializer_class = ChecklistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        card_id = self.kwargs['card_id']
        return Checklist.objects.filter(card_id=card_id)

    def perform_create(self, serializer):
        card_id = self.kwargs['card_id']
        card = get_object_or_404(Card, pk=card_id)
        serializer.save(card=card, created_by=self.request.user)


class ChecklistDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: lấy chi tiết checklist
    PATCH/PUT: update checklist
    DELETE: xoá checklist
    """
    queryset = Checklist.objects.all()
    serializer_class = ChecklistSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        checklist = serializer.save()
        # Log checklist title change
        if 'title' in self.request.data:
            CardActivity.objects.create(
                card=checklist.card,
                user=self.request.user,
                activity_type='card_updated',
                description=f'renamed checklist to "{checklist.title}"'
            )

    def perform_destroy(self, instance):
        CardActivity.objects.create(
            card=instance.card,
            user=self.request.user,
            activity_type='card_updated',
            description=f'deleted checklist "{instance.title}"'
        )
        super().perform_destroy(instance)        


# -------------------
# Checklist Item CRUD
# -------------------
class ChecklistItemListView(generics.ListCreateAPIView):
    """
    GET: lấy toàn bộ item trong 1 checklist
    POST: tạo item mới
    """
    
    serializer_class = ChecklistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        checklist_id = self.kwargs['checklist_id']
        return ChecklistItem.objects.filter(checklist_id=checklist_id)

    def perform_create(self, serializer):
        checklist_id = self.kwargs['checklist_id']
        checklist = get_object_or_404(Checklist, pk=checklist_id)
        serializer.save(checklist=checklist)


class ChecklistItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: chi tiết 1 item
    PATCH/PUT: update item (text, completed, due_date, assigned_to,…)
    DELETE: xoá item
    """
    queryset = ChecklistItem.objects.all()
    serializer_class = ChecklistItemSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        old_completed = serializer.instance.completed
        item = serializer.save()
        
        # Log completion status change
        if 'completed' in self.request.data and old_completed != item.completed:
            action = 'completed' if item.completed else 'marked incomplete'
            CardActivity.objects.create(
                card=item.checklist.card,
                user=self.request.user,
                activity_type='card_updated',
                description=f'{action} "{item.text}" on {item.checklist.title}'
            )

# -------------------
# Special actions
# -------------------
from rest_framework.views import APIView

class ReorderItemsView(APIView):
    """
    PATCH: nhận danh sách item_id theo thứ tự mới → update position
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        checklist = get_object_or_404(Checklist, pk=pk)
        item_ids = request.data.get("item_ids", [])
        for index, item_id in enumerate(item_ids):
            ChecklistItem.objects.filter(pk=item_id, checklist=checklist).update(position=index)
        return Response({"detail": "Items reordered"}, status=status.HTTP_200_OK)


class ConvertItemToCardView(APIView):
    """
    POST: chuyển 1 checklist item thành 1 Card
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        item = get_object_or_404(ChecklistItem, pk=pk)
        # Tạo Card mới trong cùng Board/List với card gốc
        parent_card = item.checklist.card
        new_card = Card.objects.create(
            name=item.text,
            list=parent_card.list,   # giữ nguyên list
            created_by=request.user
        )
        # Option: xoá item hoặc giữ lại
        item.delete()
        return Response({"detail": "Item converted to card", "card_id": new_card.id}, status=status.HTTP_201_CREATED)    
    

# ====== Helpers ======
def _to_bool(val):
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "on"}

def _is_http_url(url: str) -> bool:
    try:
        p = urlparse(url or "")
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False    
    
ALLOWED_MIME_PREFIXES = (
    "image/", "video/", "audio/", "application/pdf", "text/"
)    

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

class CardAttachmentsView(APIView):
    """Quản lý attachments của card"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _ensure_can_view_card(self, card, user):
        # Card thuộc board
        if card.list:
            check_board_view_permission(card.list.board, user)
            return
        
        if card.created_by == user:
            return
        
        has_common = Board.objects.filter(
            Q(created_by=user) | Q(members=user)
        ).filter(
            Q(created_by=card.created_by) | Q(members=card.created_by)
        ).exists()
        if not has_common:
            # raise PermissionDenied cũng được; ở đây trả Response thống nhất ở caller
            raise PermissionError("Forbidden")
        
    def get(self, request, card_id):
        """Lấy danh sách attachments của card (kèm phân trang nhẹ)"""
        card = get_object_or_404(Card.objects.select_related("list__board", "created_by"), id=card_id)

        try:
            self._ensure_can_view_card(card, request.user)
        except PermissionError:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        qs = card.attachments.select_related("uploaded_by").all()

        # Optional: phân trang đơn giản qua ?limit= & ?offset=
        try:
            limit = int(request.query_params.get("limit", 50))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            limit, offset = 50, 0

        total = qs.count()
        items = qs[offset:offset + limit]

        serializer = AttachmentSerializer(items, many=True, context={'request': request})
        return Response({
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": serializer.data
        })    
    
    def post(self, request, card_id):
        """Tạo attachment mới"""
        card = get_object_or_404(Card.objects.select_related("list__board"), id=card_id)
        check_card_edit_permission(card, request.user)

        attachment_type = request.data.get('attachment_type', 'file').strip().lower()

        if attachment_type == 'file':
            file_obj = request.FILES.get('file')
            if not file_obj:
                return Response({'detail': 'File is required for file upload'},
                                status=status.HTTP_400_BAD_REQUEST)
            
            # Size limit
            if getattr(file_obj, "size", 0) > MAX_UPLOAD_BYTES:
                return Response({'detail': f'File size must be less than {MAX_UPLOAD_BYTES // (1024*1024)}MB'},
                                status=status.HTTP_400_BAD_REQUEST)
            
            # MIME basic allow (optional)
            content_type = getattr(file_obj, "content_type", "") or ""
            if not any(content_type.startswith(pfx) for pfx in ALLOWED_MIME_PREFIXES):
                # Có thể nới lỏng/điều chỉnh theo nhu cầu
                return Response({'detail': f'File type "{content_type}" not allowed.'},
                                status=status.HTTP_400_BAD_REQUEST)
            
            data = {
                'name': request.data.get('name') or getattr(file_obj, 'name', 'Attachment'),
                'attachment_type': 'file',
                'file': file_obj
            }

        elif attachment_type == 'link':
            url = request.data.get('url')
            if not url or not _is_http_url(url):
                return Response({'detail' : 'A valid http/https URL is required for link attachment'},
                                status = status.HTTP_400_BAD_REQUEST)

            data = {
                'name': request.data.get('name') or url,
                'attachment_type': 'link',
                'url': url
            }  

        else :
            return Response({'detail': 'Invalid attachment type'},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = AttachmentSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save(card=card, uploaded_by=request.user)

        # Log activity
        CardActivity.objects.create(
            card=card,
            user=request.user,
            activity_type='card_updated',
            description=f'added attachment "{attachment.name}"'
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)



class AttachmentDetailView(APIView):
    """Quản lý attachment cụ thể"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, attachment_id):
        """
        Download file attachment:
        - Nếu type = file: stream FileResponse (storage‑agnostic)
        - Nếu type = link: redirect 302 tới URL
        """
        attachment = get_object_or_404(
            Attachment.objects.select_related("card__list__board"),
            id=attachment_id
        )

        # Quyền xem
        card = attachment.card
        if card.list:
            check_board_view_permission(card.list.board, request.user)
        else:
            if card.created_by != request.user:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        if attachment.attachment_type == 'file' and attachment.file:
            try:
                file_handle = attachment.file.storage.open(attachment.file.name, 'rb')
            except FileNotFoundError:
                return Response({'detail': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
            
            filename = smart_str(attachment.name or attachment.file.name)
            content_type = attachment.mime_type or 'application/octet-stream'
            resp = FileResponse(file_handle, as_attachment=True, filename=filename, content_type=content_type)
            return resp
        
        elif attachment.attachment_type == 'link':
            if not _is_http_url(attachment.url):
                return Response({'detail': 'Invalid URL'}, status=status.HTTP_400_BAD_REQUEST)
            return redirect(attachment.url)
        
        return Response({'detail': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, attachment_id):
        """Cập nhật attachment (tên, cover, etc.)"""
        attachment = get_object_or_404(
            Attachment.objects.select_related("card__list__board"),
            id=attachment_id
        )
        check_card_edit_permission(attachment.card, request.user)

        is_cover_in = request.data.get('is_cover', None)
        will_set_cover = _to_bool(is_cover_in)

        with transaction.atomic():
            # Nếu set cover = True: unset các cover khác cùng card
            if is_cover_in is not None and will_set_cover:
                Attachment.objects.filter(card=attachment.card, is_cover=True).exclude(id=attachment.id).update(is_cover=False)

            serializer = AttachmentSerializer(attachment, data=request.data, partial=True, context={'request': request})
            serializer.is_valid(raise_exception=True)
            obj = serializer.save()

    # Log activity (tuỳ chọn: chỉ khi đổi cover hoặc đổi tên)
        if 'name' in request.data:
            CardActivity.objects.create(
                card=attachment.card, user=request.user,
                activity_type='card_updated',
                description=f'renamed attachment to "{obj.name}"'
            )
        if is_cover_in is not None:
            CardActivity.objects.create(
                card=attachment.card, user=request.user,
                activity_type='card_updated',
                description='set card cover from attachment' if will_set_cover else 'unset card cover'
            )

        return Response(serializer.data)

    def delete(self, request, attachment_id):
        """Xóa attachment (và file ở storage nếu có)"""
        attachment = get_object_or_404(
            Attachment.objects.select_related("card__list__board"),
            id=attachment_id
        )
        check_card_edit_permission(attachment.card, request.user)

        # Log trước khi xóa
        CardActivity.objects.create(
            card=attachment.card,
            user=request.user,
            activity_type='card_updated',
            description=f'removed attachment "{attachment.name}"'
        )

        # Xóa file ở storage (S3/FS) nếu có
        if attachment.file:
            try:
                attachment.file.storage.delete(attachment.file.name)
            except Exception:
                # Không chặn xoá DB nếu lỗi xóa file vật lý
                pass

        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
  