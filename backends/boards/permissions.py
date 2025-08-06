# boards/permissions.py
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from .models import BoardMembership, Board

class IsBoardOwner(permissions.BasePermission):
    """
    Cho phép truy cập chỉ khi người dùng là người tạo ra board.
    Dùng cho các hành động nguy hiểm nhất như xóa board.
    """
    message = "Chỉ người tạo board mới có quyền thực hiện hành động này."

    def has_object_permission(self, request, view, obj):
        # 'obj' ở đây có thể là Board, List, Card, v.v...
        # Chúng ta cần tìm ra board gốc.
        board = None
        if obj.__class__.__name__ == 'Board':
            board = obj
        elif hasattr(obj, 'board'): # List, Label, BoardMembership
            board = obj.board
        elif hasattr(obj, 'list') and obj.list is not None: # Card
            board = obj.list.board
        
        if not board:
            # Trường hợp đặc biệt như card inbox không có board trực tiếp
            return obj.created_by == request.user if hasattr(obj, 'created_by') else False
            
        return board.created_by == request.user

class IsBoardEditor(permissions.BasePermission):
    """
    Cho phép truy cập nếu người dùng là owner hoặc có vai trò 'editor'.
    """
    message = "Bạn không có quyền chỉnh sửa trên board này."

    def has_permission(self, request, view):
        # Kiểm tra quyền ở cấp độ View, trước khi có object
        # Rất hữu ích cho action 'create' trong ViewSet lồng nhau
        board_pk = view.kwargs.get('board_pk')
        if not board_pk:
            return True # Không có board_pk, bỏ qua check ở đây

        board = get_object_or_404(Board, pk=board_pk)
        return self.has_object_permission(request, view, board)
    
    def has_object_permission(self, request, view, obj):
        board = None
        if obj.__class__.__name__ == 'Board':
            board = obj
        elif hasattr(obj, 'board'):
            board = obj.board
        elif hasattr(obj, 'list') and obj.list is not None:
            board = obj.list.board
        
        if not board:
             return obj.created_by == request.user if hasattr(obj, 'created_by') else False

        if board.created_by == request.user:
            return True
            
        try:
            membership = BoardMembership.objects.get(board=board, user=request.user)
            return membership.role == 'editor'
        except BoardMembership.DoesNotExist:
            return False

class IsBoardMember(permissions.BasePermission):
    """
    Cho phép truy cập nếu người dùng là owner hoặc là thành viên của board (bất kỳ vai trò nào).
    Thường dùng cho các hành động chỉ cần quyền xem.
    """
    message = "Bạn không phải là thành viên của board này."

    def has_object_permission(self, request, view, obj):
        board = None
        if obj.__class__.__name__ == 'Board':
            board = obj
        elif hasattr(obj, 'board'):
            board = obj.board
        elif hasattr(obj, 'list') and obj.list is not None:
            board = obj.list.board

        if not board:
            # Cho phép xem card inbox nếu là người tạo
            return obj.created_by == request.user if hasattr(obj, 'created_by') else False
        
        if board.created_by == request.user:
            return True
        
        return board.members.filter(pk=request.user.pk).exists()
    
class CanAccessBoardFromURL(permissions.BasePermission):
    """
    Kiểm tra xem user có quyền truy cập vào Board
    được chỉ định bởi 'board_pk' trong URL hay không.
    """
    def __init__(self, required_permission):
        self.required_permission = required_permission

    def has_permission(self, request, view):
        board_pk = view.kwargs.get('board_pk')
        if not board_pk:
            return True # Bỏ qua nếu không có board_pk trong URL

        board = get_object_or_404(Board, pk=board_pk)
        
        # Dùng lại logic của permission được yêu cầu (IsBoardMember, IsBoardEditor...)
        permission_instance = self.required_permission()
        return permission_instance.has_object_permission(request, view, board)    