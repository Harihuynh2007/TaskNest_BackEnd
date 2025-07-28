from django.urls import path
from .views import (
    WorkspaceListCreateView,
    BoardListCreateView,
    ListsCreateView,
    CardListCreateView,
    BoardDetailView,
    CardDetailView
)

urlpatterns = [
    # Workspace
    path('workspaces/', WorkspaceListCreateView.as_view(), name='workspace-list-create'),
    path('workspaces/<int:workspace_id>/boards/', BoardListCreateView.as_view(), name='board-list-create'),

    # List (theo board)
    path('boards/<int:board_id>/lists/', ListsCreateView.as_view(), name='list-list-create'),

    # Card (theo list)
    path('lists/<int:list_id>/cards/', CardListCreateView.as_view(), name='card-list-create'),
    path('workspaces/<int:workspace_id>/boards/<int:board_id>/', BoardDetailView.as_view(), name='board-detail'),

    path('cards/<int:card_id>/', CardDetailView.as_view(), name='card-detail'),
]
