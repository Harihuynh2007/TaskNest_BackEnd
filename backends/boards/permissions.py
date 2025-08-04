# boards/permissions.py
from rest_framework.exceptions import PermissionDenied
from .models import BoardMembership

def check_board_edit_permission(board, user):
    """
    Kiểm tra xem user có quyền 'editor' trên board không.
    Nếu không đủ quyền, raise PermissionDenied.
    """
    if board.created_by == user:
        return  # full quyền

    try:
        membership = BoardMembership.objects.get(board=board, user=user)
        if membership.role != 'editor':
            raise PermissionDenied("You don't have permission to modify this board.")
    except BoardMembership.DoesNotExist:
        raise PermissionDenied("You are not a member of this board.")
    
def check_board_view_permission(board, user):
    """
    Raise lỗi nếu user không có quyền xem board (creator hoặc bất kỳ thành viên nào)
    """
    if board.created_by == user:
        return

    if not BoardMembership.objects.filter(board=board, user=user).exists():
        raise PermissionDenied("You do not have permission to view this board.")
    
def check_card_edit_permission(card, user):
    """
    Cho phép chỉnh sửa card nếu:
    - Card có list → kiểm tra board như thường
    - Card không có list (inbox) → chỉ người tạo được chỉnh sửa
    """
    if card.list:
        check_board_edit_permission(card.list.board, user)
    else:
        if card.created_by != user:
            raise PermissionDenied("You don't have permission to modify this inbox card.")