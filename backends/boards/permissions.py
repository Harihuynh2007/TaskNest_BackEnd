# backends/boards/permissions.py
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from .models import Board, BoardMembership

# ===================================================================
# HÀM HELPER - Lấy vai trò của user trên một board cụ thể
# ===================================================================
def get_user_role_on_board(board, user):
    """
    Trả về role code ('owner', 'admin', 'editor', 'viewer') hoặc None.
    """
    if board.created_by == user:
        return 'owner'
    try:
        membership = BoardMembership.objects.get(board=board, user=user)
        return membership.role
    except BoardMembership.DoesNotExist:
        return None

# ===================================================================
# CÁC HÀM KIỂM TRA QUYỀN
# ===================================================================

def check_board_view_permission(board, user):
    """
    KIỂM TRA QUYỀN XEM (Observer trở lên)
    User có thể xem nếu họ là owner, admin, editor, hoặc viewer.
    """
    role = get_user_role_on_board(board, user)
    if role in ['owner', 'admin', 'editor', 'viewer']:
        return
    raise PermissionDenied("You do not have permission to view this board.")

def check_card_edit_permission(card, user):
    """
    KIỂM TRA QUYỀN SỬA CARD (Member/Editor trở lên)
    User có thể sửa card nếu họ là owner, admin, hoặc editor.
    """
    # Cho card trong Inbox
    if not card.list:
         # Logic cũ đã tốt: kiểm tra board chung
        card_creator = card.created_by
        if card_creator == user: return
        user_boards = set(Board.objects.filter(Q(created_by=user) | Q(members=user)).values_list('id', flat=True))
        creator_boards = set(Board.objects.filter(Q(created_by=card_creator) | Q(members=card_creator)).values_list('id', flat=True))
        if user_boards.intersection(creator_boards): return
        raise PermissionDenied("You don't have permission to modify this inbox card.")
    
    # Cho card trong list
    role = get_user_role_on_board(card.list.board, user)
    if role in ['owner', 'admin', 'editor']:
        return
    raise PermissionDenied("You must be an editor, admin, or owner to modify cards.")


def check_board_admin_permission(board, user):
    """
    KIỂM TRA QUYỀN QUẢN TRỊ BOARD (Admin trở lên)
    Dùng cho các hành động như mời thành viên, đổi tên board, xóa cột...
    User có quyền nếu họ là owner hoặc admin.
    """
    role = get_user_role_on_board(board, user)
    if role in ['owner', 'admin']:
        return
    raise PermissionDenied("You must be an admin or the board creator to perform this action.")