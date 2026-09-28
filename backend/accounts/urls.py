from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import login_view, register_view, me_view, AdminUserListCreateView
from .admin_views import (
    admin_user_detail_view,
    admin_assign_student_profile_view,
    admin_assign_faculty_profile_view,
    admin_users_without_profile_view,
)

urlpatterns = [
    # Public authentication
    path('login/', login_view, name='auth_login'),
    path('register/', register_view, name='auth_register'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', me_view, name='auth_me'),

    # Admin — user list & create
    path('admin/users/', AdminUserListCreateView.as_view(), name='admin_users'),

    # Admin — onboarding workflows
    path('admin/users/<int:user_id>/', admin_user_detail_view, name='admin_user_detail'),
    path('admin/users/<int:user_id>/assign-student-profile/', admin_assign_student_profile_view, name='admin_assign_student_profile'),
    path('admin/users/<int:user_id>/assign-faculty-profile/', admin_assign_faculty_profile_view, name='admin_assign_faculty_profile'),
    path('admin/users/pending-profiles/', admin_users_without_profile_view, name='admin_pending_profiles'),
]
