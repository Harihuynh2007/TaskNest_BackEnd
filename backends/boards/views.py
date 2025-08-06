from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from django.db import models

from .models import Workspace, Board, List, Card, Label, BoardMembership
from .serializers import (
    WorkspaceSerializer, BoardSerializer, ListSerializer, CardSerializer,
    LabelSerializer, BoardMembershipSerializer
)
from .permissions import IsBoardOwner, IsBoardEditor, IsBoardMember, CanAccessBoardFromURL
from rest_framework.views import APIView

class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Workspace.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BoardViewSet(viewsets.ModelViewSet):
    serializer_class = BoardSerializer


    def get_queryset(self):
        """
        Lấy các board thuộc về workspace được chỉ định trong URL
        VÀ user hiện tại phải có quyền truy cập (là owner hoặc member).
        """
        # 1. Lấy tất cả các board mà user có quyền truy cập
        user = self.request.user
        user_accessible_boards = Board.objects.filter(
            models.Q(created_by=user) | models.Q(members=user)
        ).distinct()

        workspace_pk = self.kwargs.get('workspace_pk')
        if not workspace_pk:
            # Trả về rỗng nếu không có workspace_pk để tránh lỗi
            return Board.objects.none() 
        
        return user_accessible_boards.filter(workspace_id=workspace_pk)

    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        elif self.action == 'destroy':
            self.permission_classes = [permissions.IsAuthenticated, IsBoardOwner]
        else: # list, retrieve, create
            self.permission_classes = [permissions.IsAuthenticated] # Cho phép tạo nếu đã đăng nhập, logic kiểm tra owner workspace ở perform_create
        
        # Gọi hàm get_permissions của cha để nó khởi tạo các instance từ self.permission_classes
        return super().get_permissions()

    def perform_create(self, serializer):
        workspace = get_object_or_404(Workspace, pk=self.kwargs['workspace_pk'])
        if workspace.owner != self.request.user:
            raise PermissionDenied("Bạn không có quyền tạo board trong workspace này.")

        board = serializer.save(workspace=workspace, created_by=self.request.user)

        # Gợi ý: chuyển phần này vào signal nếu dùng lại nhiều
        DEFAULT_LABEL_COLORS = ['#61bd4f', '#f2d600', '#ff9f1a']
        for color in DEFAULT_LABEL_COLORS:
            Label.objects.create(name='', color=color, board=board)

class ListViewSet(viewsets.ModelViewSet):
    serializer_class = ListSerializer

    def get_queryset(self):
        # ✅ Queryset đã được lọc an toàn
        board_pk = self.kwargs.get('board_pk')
        board = get_object_or_404(Board, pk=board_pk)
        
        # Kiểm tra quyền xem board trước khi trả về list
        if not IsBoardMember().has_object_permission(self.request, self, board):
            raise PermissionDenied("Bạn không có quyền xem danh sách của board này.")
            
        return List.objects.filter(board=board).order_by('position')

    def get_permissions(self):
        """Khai báo các lớp permission cần dùng cho từng action."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAuthenticated, IsBoardEditor]
        else: # list, retrieve
            self.permission_classes = [permissions.IsAuthenticated, IsBoardMember]
        
        return super().get_permissions() # Để DRF tự xử lý

    def perform_create(self, serializer):
        """
        DRF đã kiểm tra quyền Editor trên Board trước khi gọi hàm này.
        Chúng ta chỉ cần lấy board và gán nó.
        """
        board = get_object_or_404(Board, pk=self.kwargs['board_pk'])
        serializer.save(board=board)


class ListCardViewSet(viewsets.ModelViewSet):
    serializer_class = CardSerializer

    def get_queryset(self):
        return Card.objects.filter(list_id=self.kwargs['list_pk']).order_by('position')

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsBoardEditor()]
        return [permissions.IsAuthenticated(), IsBoardMember()]

    def perform_create(self, serializer):
        list_obj = get_object_or_404(List, pk=self.kwargs['list_pk'])
        board = list_obj.board

         # ✅ KIỂM TRA QUYỀN TRỰC TIẾP TRÊN BOARD
        if not IsBoardEditor().has_object_permission(self.request, self, board):
            raise PermissionDenied("Bạn không có quyền tạo thẻ trong board này.")
            
        
        serializer.save(list=list_obj, created_by=self.request.user)


class CardViewSet(viewsets.ModelViewSet):
    serializer_class = CardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        # ✅ LUÔN LUÔN lọc theo user hiện tại để đảm bảo an toàn
        # Chỉ lấy card inbox do chính user này tạo
        queryset = Card.objects.filter(created_by=self.request.user, list__isnull=True)

        board_id = self.request.query_params.get("board")
        if board_id:
            queryset = queryset.filter(board_id=board_id)
        return queryset

    def perform_create(self, serializer):
        board_id = self.request.data.get('board')
        if not board_id:
            raise PermissionDenied("Thiếu board_id để tạo inbox card.")
        board = get_object_or_404(Board, pk=board_id)

        # Chỉ editor mới được tạo
        if not IsBoardEditor().has_object_permission(self.request, self, board):
            raise PermissionDenied("Bạn không có quyền tạo thẻ vào board này.")

        serializer.save(board=board, list=None, created_by=self.request.user)


class LabelViewSet(viewsets.ModelViewSet):
    serializer_class = LabelSerializer
    permission_classes = [permissions.IsAuthenticated, IsBoardEditor]

    def get_queryset(self):
        # ✅ Chỉ trả về các label thuộc các board mà user là thành viên
        user_boards = self.request.user.boards.all()
        return Label.objects.filter(board__in=user_boards)


class BoardLabelViewSet(viewsets.ModelViewSet):
    serializer_class = LabelSerializer

    def get_queryset(self):
        return Label.objects.filter(board_id=self.kwargs['board_pk'])

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsBoardEditor()]
        return [permissions.IsAuthenticated(), IsBoardMember()]

    def perform_create(self, serializer):
        board = get_object_or_404(Board, pk=self.kwargs['board_pk'])

         # ✅ KIỂM TRA QUYỀN TRỰC TIẾP TRÊN BOARD
        if not IsBoardEditor().has_object_permission(self.request, self, board):
            raise PermissionDenied("Bạn không có quyền tạo label trong board này.")
        
        serializer.save(board=board)


class BoardMemberViewSet(viewsets.ModelViewSet):
    serializer_class = BoardMembershipSerializer

    def get_queryset(self):
        return BoardMembership.objects.filter(board_id=self.kwargs['board_pk'])

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsBoardOwner()]
        return [permissions.IsAuthenticated(), IsBoardMember()]

    def perform_create(self, serializer):
        board = get_object_or_404(Board, pk=self.kwargs['board_pk'])

        if not IsBoardOwner().has_object_permission(self.request, self, board):
            raise PermissionDenied("Chỉ người tạo board mới có quyền thêm thành viên.")
        
        # TODO: Cần lấy user_id từ request.data và kiểm tra
        user_id_to_add = self.request.data.get('user_id') 

        serializer.save(board=board, user_id=user_id_to_add) # sửa serializer để nhận user_id


class CardBatchUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        updates = request.data
        if not isinstance(updates, list):
            return Response({'error': 'Expected a list of card updates.'}, status=400)
        
        updated_cards = []
        for card_data in updates:
            card_id = card_data.get('id')
            if not card_id:
                continue
            
            try:
                card = Card.objects.get(pk=card_id)
            except Card.DoesNotExist:
                continue

            # ✅ Chỉ cho phép sửa nếu user là editor của board
            board = card.board or (card.list.board if card.list else None)
            if not board or not IsBoardEditor().has_object_permission(request, self, board):
                continue

            serializer = CardSerializer(card, data=card_data, partial=True)
            if serializer.is_valid():
                serializer.save()
                updated_cards.append(serializer.data)

        return Response(updated_cards, status=200)
    
class JoinBoardByLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token, *args, **kwargs):
        try:
            board = Board.objects.get(invite_token=token)
        except Board.DoesNotExist:
            return Response({"error": "Invalid or expired invite link."}, status=404)
        
        # Nếu user đã là thành viên → bỏ qua
        if board.members.filter(pk=request.user.pk).exists():
            return Response({"message": "You are already a member of this board."}, status=200)
        
        # Thêm vào board với vai trò mặc định
        BoardMembership.objects.create(
            board=board,
            user=request.user,
            role='member'
        )
        return Response({"message": "You have successfully joined the board."}, status=200)    