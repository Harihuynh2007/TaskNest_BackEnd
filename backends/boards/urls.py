from django.urls import path
from . import views
from .views import (
    WorkspaceListCreateView,
    BoardListCreateView,
    ListsCreateView,
    CardListCreateView,
    BoardDetailView,
    CardDetailView,
    ListDetailView,
    InboxCardCreateView,
    BoardMembersView,
    LabelDetailView,
    CardBatchUpdateView,
    ClosedBoardsListView,
    BoardShareLinkView,
    BoardJoinByLinkView,
    CardCommentsView,
    CommentDetailView,
    BoardLabelListCreateView,
    CardMembershipListCreateView,
    CardMembershipDetailView,
    CardWatchersView,
    CardActivityView,
    CardChecklistListView,
    CardAttachmentsView, 
    AttachmentDetailView

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
    # Card va List thay doi vi tri khi f5 va save card list
    path('cards/<int:card_id>/', CardDetailView.as_view(), name='card-detail'),
    path('lists/<int:list_id>/', ListDetailView.as_view(), name='list-detail'),

    path('cards/', InboxCardCreateView.as_view(), name='card-create-inbox'),

    path('boards/<int:board_id>/labels/', BoardLabelListCreateView.as_view(), name='board-label-list-create'),

    path('boards/<int:board_id>/members/', BoardMembersView.as_view(), name='board_members'),

    path('labels/<int:label_id>/', LabelDetailView.as_view(), name='label-detail'),

    path('cards/batch-update/', CardBatchUpdateView.as_view(), name='card-batch-update'),

    path('boards/closed/', ClosedBoardsListView.as_view(), name='closed-board-list'),

    path('boards/<int:board_id>/share-link/', BoardShareLinkView.as_view(), name='board-share-link'),
    path('boards/join/<uuid:token>/', BoardJoinByLinkView.as_view(), name='board-join-by-link'),

    path('cards/<int:card_id>/comments/', CardCommentsView.as_view()),
    path('comments/<int:comment_id>/', CommentDetailView.as_view()),


    # Enhanced card member management
    path(
        'cards/<int:card_id>/memberships/',
        CardMembershipListCreateView.as_view(),
        name='card-membership-list-create'
    ),
    path(
        'cards/<int:card_id>/memberships/<int:user_id>/',
        CardMembershipDetailView.as_view(),
        name='card-membership-detail'
    ),
    
    # Card watchers
    path('cards/<int:card_id>/watchers/', CardWatchersView.as_view()),
    
    # Card activity
    path('cards/<int:card_id>/activities/', CardActivityView.as_view()),


    

    # Checklist CRUD
    path('cards/<int:card_id>/checklists/', views.CardChecklistListView.as_view()),
    path('checklists/<int:pk>/', views.ChecklistDetailView.as_view()),
    
    # Checklist Item CRUD  
    path('checklists/<int:checklist_id>/items/', views.ChecklistItemListView.as_view()),
    path('checklist-items/<int:pk>/', views.ChecklistItemDetailView.as_view()),
    
    # Special actions
    path('checklists/<int:pk>/reorder-items/', views.ReorderItemsView.as_view()),
    path('checklist-items/<int:pk>/convert-to-card/', views.ConvertItemToCardView.as_view()),

    path('cards/<int:card_id>/attachments/', CardAttachmentsView.as_view(), name='card-attachments'),
    path('attachments/<int:attachment_id>/', AttachmentDetailView.as_view(), name='attachment-detail'),
]
