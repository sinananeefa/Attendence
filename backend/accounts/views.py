from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import User, Role
from .serializers import UserSerializer
from .permissions import IsAdminUserRole


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Authenticate user with username and password, returning JWT access & refresh tokens
    along with sanitized user profile and permission scopes.
    """
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response(
            {'detail': 'Please provide both username and password.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Allow login with either username or email
    user = authenticate(request, username=username, password=password)
    if not user:
        # Check if email was provided instead of username
        try:
            matched_user = User.objects.get(email__iexact=username)
            user = authenticate(request, username=matched_user.username, password=password)
        except User.DoesNotExist:
            user = None

    if not user:
        return Response(
            {'detail': 'Invalid credentials. Please verify your username and password.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {'detail': 'This account has been deactivated. Please contact the administrator.'},
            status=status.HTTP_403_FORBIDDEN
        )

    return Response(_authentication_response(user))


def _authentication_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        'user': UserSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'permissions': {
            'is_admin': user.is_admin_role,
            'is_hod': user.is_hod_role,
            'is_faculty': user.is_faculty_role,
            'is_mentor': user.is_mentor_role,
            'is_student': user.is_student_role,
        }
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """Create a student account and return an authenticated JWT session."""
    username = request.data.get('username', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    password_confirm = request.data.get('password_confirm', '')

    if not username or not email or not password or not password_confirm:
        return Response({'detail': 'Username, email, password, and password confirmation are required.'}, status=status.HTTP_400_BAD_REQUEST)
    if password != password_confirm:
        return Response({'detail': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_email(email)
    except ValidationError:
        return Response({'detail': 'Enter a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username__iexact=username).exists():
        return Response({'detail': 'That username is already in use.'}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email__iexact=email).exists():
        return Response({'detail': 'That email is already registered.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        password_validation.validate_password(password)
    except ValidationError as exc:
        return Response({'detail': ' '.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=request.data.get('first_name', '').strip(),
        last_name=request.data.get('last_name', '').strip(),
        role=Role.STUDENT,
    )
    return Response(_authentication_response(user), status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Returns current authenticated user details and active role permissions.
    """
    user = request.user
    return Response({
        'user': UserSerializer(user).data,
        'permissions': {
            'is_admin': user.is_admin_role,
            'is_hod': user.is_hod_role,
            'is_faculty': user.is_faculty_role,
            'is_mentor': user.is_mentor_role,
            'is_student': user.is_student_role,
        }
    })


class AdminUserListCreateView(generics.ListCreateAPIView):
    """
    ADMIN-ONLY ENDPOINT:
    Lists all users or creates new user accounts across the institution.
    Strictly forbidden for Students and Faculty.
    """
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUserRole]

    def create(self, request, *args, **kwargs):
        role = request.data.get('role', Role.STUDENT)
        username = request.data.get('username')
        password = request.data.get('password', 'Student@123')
        email = request.data.get('email', f"{username}@edumerge.ac.in")

        if User.objects.filter(username=username).exists():
            return Response({'detail': f"Username '{username}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=request.data.get('first_name', ''),
            last_name=request.data.get('last_name', ''),
            role=role,
            department_id=request.data.get('department')
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
