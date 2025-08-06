# boards/permissions.py
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from .models import Board, BoardMembership, List, Card

def get_board_from_view(view):
    """Helper để lấy board từ các kwargs khác nhau trong URL."""
    if 'board_pk' in view.kwargs:
        return get_object_or_404(Board, pk=view.kwargs['board_pk'])
    if 'list_pk' in view.kwargs:
        return get_object_or_404(List, pk=view.kwargs['list_pk']).board
    if 'card_pk' in view.kwargs: # Giả sử router có card_pk
        return get_object_or_404(Card, pk=view.kwargs['card_pk']).board
    return None

def get_board_from_object(obj):
    """Helper để lấy board từ một object bất kỳ."""
    if isinstance(obj, Board): return obj
    if hasattr(obj, 'board'): return obj.board
    if hasattr(obj, 'list') and obj.list: return obj.list.board
    return None

class IsBoardMember(permissions.BasePermission):
    message = "Bạn không phải là thành viên của board này."

    def has_permission(self, request, view):
        board = get_board_from_view(view)
        return board is None or self.has_object_permission(request, view, board)

    def has_object_permission(self, request, view, obj):
        board = get_board_from_object(obj)
        if not board: return False
        if board.created_by == request.user: return True
        return board.members.filter(pk=request.user.pk).exists()

class IsBoardEditor(permissions.BasePermission):
    message = "Bạn không có quyền chỉnh sửa trên board này."

    def has_permission(self, request, view):
        board = get_board_from_view(view)
        return board is None or self.has_object_permission(request, view, board)

    def has_object_permission(self, request, view, obj):
        board = get_board_from_object(obj)
        if not board: return False
        if board.created_by == request.user: return True
        try:
            return BoardMembership.objects.get(board=board, user=request.user).role == 'editor'
        except BoardMembership.DoesNotExist:
            return False

class IsBoardOwner(permissions.BasePermission):
    message = "Chỉ người tạo board mới có quyền thực hiện hành động này."

    def has_permission(self, request, view):
        board = get_board_from_view(view)
        return board is None or self.has_object_permission(request, view, board)
        
    def has_object_permission(self, request, view, obj):
        board = get_board_from_object(obj)
        if not board: return False
        return board.created_by == request.user