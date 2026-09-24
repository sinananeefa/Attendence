from rest_framework.permissions import BasePermission
from .models import Role


class IsAdminUserRole(BasePermission):
    """
    Grants access only to institutional administrators / deans.
    """
    message = "Administrative privilege required. Students and Faculty are strictly forbidden."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role == Role.ADMIN or request.user.is_superuser)
        )


class IsHODUserRole(BasePermission):
    """
    Grants access to Department Heads and Institutional Admins.
    """
    message = "Head of Department (HOD) access required."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in [Role.HOD, Role.ADMIN] or request.user.is_superuser)
        )


class IsFacultyUserRole(BasePermission):
    """
    Grants access to teaching staff (Faculty, Mentors, HODs, Admins).
    Students are strictly forbidden.
    """
    message = "Faculty access required. Students cannot access teaching staff resources."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in [Role.FACULTY, Role.HOD, Role.MENTOR, Role.ADMIN] or request.user.is_superuser)
        )


class IsMentorUserRole(BasePermission):
    """
    Grants access to section mentors / class advisors.
    """
    message = "Class Mentor access required."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in [Role.MENTOR, Role.HOD, Role.ADMIN] or request.user.is_superuser)
        )


class IsStudentUserRole(BasePermission):
    """
    Grants access to student-specific resources.
    """
    message = "Student account required."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == Role.STUDENT
        )


class IsSelfOrAdmin(BasePermission):
    """
    Allows a user to access their own resource or an Admin to access any resource.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == Role.ADMIN or request.user.is_superuser:
            return True
        # Check if obj is user or has user attribute
        user = getattr(obj, 'user', obj)
        return user == request.user
