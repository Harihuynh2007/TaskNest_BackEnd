# boards/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import models

from .models import Workspace, Board, List, Card, Label, BoardMembership
from .serializers import (
    WorkspaceSerializer, BoardSerializer, ListSerializer, CardSerializer,
    LabelSerializer, BoardMembershipSerializer
)
from .permissions import IsBoardOwner, IsBoardEditor, IsBoardMember

# ===================================================================
# ViewSets cho các tài nguyên chính (Workspace, Board, List, Card, ...)
# ===================================================================

class WorkspaceViewSet(viewsets.ModelViewSet):
    """
    Quản lý Workspaces: /api/workspaces/
    """
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Workspace.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BoardViewSet(viewsets.ModelViewSet):
    """
    Quản lý Boards trong một Workspace: /api/workspaces/{workspace_pk}/boards/
    """
    serializer_class = BoardSerializer

    def get_queryset(self):
        workspace_pk = self.kwargs['workspace_pk']
        workspace = get_object_or_404(Workspace, pk=workspace_pk, owner=self.request.user)
        user = self.request.user
        return Board.objects.filter(
            models.Q(workspace=workspace) & (models.Q(created_by=user) | models.Q(members=user))
        ).distinct()

    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        elif self.action == 'destroy':
            self.permission_classes = [permissions.IsAuthenticated, IsBoardOwner]
        else: # list, retrieve, create
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    def perform_create(self, serializer):
        workspace = get_object_or_404(Workspace, pk=self.kwargs['workspace_pk'], owner=self.request.user)
        board = serializer.save(workspace=workspace, created_by=self.request.user)
        # Logic tạo label mặc định có thể để ở đây hoặc chuyển vào signal
        DEFAULT_LABEL_COLORS = ['#61bd4f', '#f2d600', '#ff9f1a', '#eb5a46', '#c377e0', '#0079bf']
        for color in DEFAULT_LABEL_COLORS:
            Label.objects.create(name='', color=color, board=board)


class ListViewSet(viewsets.ModelViewSet):
    """
    Quản lý Lists trong một Board: /api/boards/{board_pk}/lists/
    """
    serializer_class = ListSerializer

    def get_queryset(self):
        return List.objects.filter(board_id=self.kwargs['board_pk']).order_by('position')

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        else:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardMember]
        return super().get_permissions()

    def perform_create(self, serializer):
        board = get_object_or_404(Board, pk=self.kwargs['board_pk'])
        # DRF đã kiểm tra quyền Editor trên Board thông qua has_permission
        serializer.save(board=board)


class ListCardViewSet(viewsets.ModelViewSet):
    """
    Quản lý Cards trong một List: /api/lists/{list_pk}/cards/
    """
    serializer_class = CardSerializer

    def get_queryset(self):
        return Card.objects.filter(list_id=self.kwargs['list_pk']).order_by('position')

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        else:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardMember]
        return super().get_permissions()

    def perform_create(self, serializer):
        board = get_object_or_404(Board, pk=self.kwargs['board_pk'])
        list_obj = get_object_or_404(List, pk=self.kwargs['list_pk'])
        # DRF đã kiểm tra quyền Editor trên Board của List
        serializer.save(list=list_obj, board=list_obj.board, created_by=self.request.user)
        serializer.save(board=board)

class CardViewSet(viewsets.ModelViewSet):
    """
    Quản lý Cards không lồng nhau (Inbox cards và các thao tác update/delete bằng card_id)
    /api/cards/
    """
    serializer_class = CardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Chỉ trả về card do user tạo và không thuộc list nào (inbox)
        return Card.objects.filter(created_by=self.request.user, list__isnull=True)

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        else: # list, create, retrieve
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        board_id = self.request.data.get('board')

        if not board_id:
            raise ValidationError("Phải cung cấp 'board_id' để tạo inbox card.")
        
        board = get_object_or_404(Board, pk=board_id)

        # Vì board_id đến từ payload, phải kiểm tra quyền thủ công
        if not IsBoardEditor().has_object_permission(self.request, self, board):
            raise PermissionDenied("Bạn không có quyền tạo thẻ trong board này.")
            
        serializer.save(board=board, list=None, created_by=self.request.user)

class LabelViewSet(viewsets.ModelViewSet):
    """
    Quản lý các thao tác trên một Label cụ thể bằng ID của nó.
    /api/labels/{id}/
    """
    serializer_class = LabelSerializer
    # Chỉ cho phép các hành động trên một object, không cho list hay create ở đây
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        # User chỉ có thể truy cập label của các board họ là thành viên
        user_boards = Board.objects.filter(
            models.Q(created_by=self.request.user) | models.Q(members=self.request.user)
        ).distinct()
        return Label.objects.filter(board__in=user_boards)

    def get_permissions(self):
        # Khi sửa/xóa, cần quyền editor trên board của label
        if self.action in ['partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        else: # retrieve
            self.permission_classes = [permissions.IsAuthenticated, IsBoardMember]
        return super().get_permissions()

class BoardLabelViewSet(viewsets.ModelViewSet):
    serializer_class = LabelSerializer

    def get_queryset(self):
        return Label.objects.filter(board_id=self.kwargs['board_pk'])

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        else:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardMember]
        return super().get_permissions()

    def perform_create(self, serializer):
        board = get_object_or_404(Board, pk=self.kwargs['board_pk'])
        # DRF đã kiểm tra quyền
        serializer.save(board=board)



class BoardMemberViewSet(viewsets.ModelViewSet):
    """
    Quản lý Members trong một Board: /api/boards/{board_pk}/members/
    """
    serializer_class = BoardMembershipSerializer

    def get_queryset(self):
        return BoardMembership.objects.filter(board_id=self.kwargs['board_pk'])

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardOwner]
        else:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardMember]
        return super().get_permissions()

    def perform_create(self, serializer):
        board = get_object_or_404(Board, pk=self.kwargs['board_pk'])
        # DRF đã kiểm tra quyền Owner
        serializer.save(board=board)

# ===================================================================
# APIViews cho các hành động đặc biệt
# ===================================================================

class CardBatchUpdateView(APIView):
    """
    Endpoint để cập nhật hàng loạt vị trí của cards: /api/cards/batch-update/
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        updates = request.data
        if not isinstance(updates, list):
            return Response({'error': 'Request body phải là một danh sách.'}, status=400)
        
        updated_cards_data = []
        for card_data in updates:
            card_id = card_data.get('id')
            try:
                card = Card.objects.select_related('list__board').get(pk=card_id)
                # Dùng permission class để kiểm tra quyền một cách nhất quán
                if IsBoardEditor().has_object_permission(request, self, card):
                    serializer = CardSerializer(card, data=card_data, partial=True)
                    if serializer.is_valid(raise_exception=True):
                        serializer.save()
                        updated_cards_data.append(serializer.data)
            except Card.DoesNotExist:
                continue # Bỏ qua nếu card không tồn tại

        return Response(updated_cards_data, status=200)
    
class JoinBoardByLinkView(APIView):
    """
    Endpoint để tham gia board qua link mời: /api/join/{token}/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, token, *args, **kwargs):
        # Giả sử model Board có trường `join_link_token` và `is_join_link_enabled`
        board = get_object_or_404(Board, join_link_token=token, is_join_link_enabled=True)
        
        membership, created = BoardMembership.objects.get_or_create(
            board=board,
            user=request.user,
            defaults={'role': board.join_link_role}
        )

        if not created:
            return Response({"message": "Bạn đã là thành viên của board này."}, status=200)
        
        return Response({"message": "Bạn đã tham gia board thành công."}, status=201)
