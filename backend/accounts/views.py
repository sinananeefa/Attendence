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


from django.db import transaction

class AdminUserListCreateView(generics.ListCreateAPIView):
    """
    ADMIN-ONLY ENDPOINT:
    Lists all users or creates new user accounts across the institution.
    Strictly forbidden for Students and Faculty.
    Supports atomic creation of User + Student / Faculty profile in one step.
    """
    queryset = User.objects.all().select_related('department', 'student_profile', 'faculty_profile').order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUserRole]

    def create(self, request, *args, **kwargs):
        role = request.data.get('role', Role.STUDENT)
        username = request.data.get('username', '').strip()
        if not username:
            return Response({'username': 'Username is required.'}, status=status.HTTP_400_BAD_REQUEST)

        default_pwd = 'Student@123' if role == Role.STUDENT else ('Faculty@123' if role in (Role.FACULTY, Role.HOD, Role.MENTOR) else 'Admin@123')
        password = request.data.get('password') or default_pwd
        email = request.data.get('email', '').strip() or f"{username.lower()}@edumerge.ac.in"

        if User.objects.filter(username=username).exists():
            return Response({'username': f"Username '{username}' already exists. Please choose a different username."}, status=status.HTTP_400_BAD_REQUEST)

        first_name = request.data.get('first_name', '').strip()
        last_name = request.data.get('last_name', '').strip()
        dept_id = request.data.get('department')
        if dept_id == '':
            dept_id = None

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                department_id=dept_id
            )

            # If student profile fields provided
            if role == Role.STUDENT and (request.data.get('roll_number') or request.data.get('section')):
                from academic.models import Student, Section
                from datetime import date
                roll_number = request.data.get('roll_number', '').strip()
                registration_number = request.data.get('registration_number', '').strip() or f"REG-{roll_number}"
                section_id = request.data.get('section')
                if not roll_number:
                    transaction.set_rollback(True)
                    return Response({'roll_number': 'Roll number is required for students.'}, status=status.HTTP_400_BAD_REQUEST)
                if not section_id:
                    transaction.set_rollback(True)
                    return Response({'section': 'Section is required for students.'}, status=status.HTTP_400_BAD_REQUEST)
                
                if Student.objects.filter(roll_number=roll_number).exists():
                    transaction.set_rollback(True)
                    return Response({'roll_number': f"Student with roll number '{roll_number}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

                try:
                    section = Section.objects.get(pk=section_id)
                except Section.DoesNotExist:
                    transaction.set_rollback(True)
                    return Response({'section': 'Selected section does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

                admission_date = request.data.get('admission_date') or str(date.today())
                current_sem = request.data.get('current_semester') or section.semester or 1

                Student.objects.create(
                    user=user,
                    roll_number=roll_number,
                    registration_number=registration_number,
                    section=section,
                    current_semester=int(current_sem),
                    admission_date=admission_date,
                    guardian_name=request.data.get('guardian_name', '').strip(),
                    guardian_phone=request.data.get('guardian_phone', '').strip(),
                )

            # If faculty profile fields provided
            elif role in (Role.FACULTY, Role.HOD, Role.MENTOR) and (request.data.get('employee_id') or dept_id):
                from academic.models import Faculty, Department
                emp_id = request.data.get('employee_id', '').strip() or f"FAC-{user.id}"
                if Faculty.objects.filter(employee_id=emp_id).exists():
                    transaction.set_rollback(True)
                    return Response({'employee_id': f"Faculty with employee ID '{emp_id}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

                if not dept_id:
                    first_dept = Department.objects.first()
                    dept_id = first_dept.id if first_dept else None

                if dept_id:
                    dept = Department.objects.get(pk=dept_id)
                    Faculty.objects.create(
                        user=user,
                        employee_id=emp_id,
                        designation=request.data.get('designation', 'Assistant Professor').strip(),
                        department=dept,
                        qualification=request.data.get('qualification', 'M.Tech').strip(),
                    )

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
