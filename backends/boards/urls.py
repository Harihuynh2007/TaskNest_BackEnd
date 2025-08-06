
from django.urls import path, include
from rest_framework_nested import routers
from . import views # Import views

# Router cấp 1: /workspaces/
router = routers.SimpleRouter()
router.register(r'workspaces', views.WorkspaceViewSet, basename='workspace')
router.register(r'labels', views.LabelViewSet, basename='label') # Cho labels không lồng nhau
router.register(r'cards', views.CardViewSet, basename='card') # Cho cards không lồng nhau

# Router cấp 2 (lồng): /workspaces/{workspace_pk}/boards/
boards_router = routers.NestedSimpleRouter(router, r'workspaces', lookup='workspace')
boards_router.register(r'boards', views.BoardViewSet, basename='workspace-board')

# Router cấp 3 (lồng): /boards/{board_pk}/lists/
lists_router = routers.NestedSimpleRouter(boards_router, r'boards', lookup='board')
lists_router.register(r'lists', views.ListViewSet, basename='board-list')
lists_router.register(r'labels', views.BoardLabelViewSet, basename='board-label') # labels của board
lists_router.register(r'members', views.BoardMemberViewSet, basename='board-member') # members của board

# Router cấp 4 (lồng): /lists/{list_pk}/cards/
cards_router = routers.NestedSimpleRouter(lists_router, r'lists', lookup='list')
cards_router.register(r'cards', views.ListCardViewSet, basename='list-card')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(boards_router.urls)),
    path('', include(lists_router.urls)),
    path('', include(cards_router.urls)),
    # URL đặc biệt có thể giữ lại
    path('cards/batch-update/', views.CardBatchUpdateView.as_view(), name='card-batch-update'),
    path('join/<uuid:token>/', views.JoinBoardByLinkView.as_view(), name='join-board-by-link'),
]