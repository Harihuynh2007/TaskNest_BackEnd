from django.urls import path
from .views import RegisterView, LoginView, LogoutView, MeView, GoogleLoginView  # 👈 thêm GoogleLoginView

urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('me/', MeView.as_view()),
    path('google-login/', GoogleLoginView.as_view()),  # 👈 thêm dòng này
]
