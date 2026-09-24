from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import login_view, register_view, me_view, AdminUserListCreateView

urlpatterns = [
    path('login/', login_view, name='auth_login'),
    path('register/', register_view, name='auth_register'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', me_view, name='auth_me'),
    path('admin/users/', AdminUserListCreateView.as_view(), name='admin_users'),
]
