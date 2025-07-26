from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('auth_app.urls')),    # ✅ Auth
    path('api/', include('boards.urls')),  
             path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),    
]
