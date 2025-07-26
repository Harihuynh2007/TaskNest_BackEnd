from django.urls import path
from .views import BoardListCreateView
from .views import WorkspaceListCreateView
from .views import ListsCreateView
from .views import CardListCreateView

urlpatterns = [
    path('workspaces/', WorkspaceListCreateView.as_view()),
    path('workspaces/<int:workspace_id>/boards/', BoardListCreateView.as_view()),
    path('workspaces/<int:workspace_id>/boards/lists', ListsCreateView.as_view()),
    path('workspaces/<int:workspace_id>/boards/lists/cards', CardListCreateView.as_view()),

]
