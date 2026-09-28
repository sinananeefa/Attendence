"""
Admin onboarding views for the accounts app.

These endpoints allow an institutional administrator to:
- List and detail individual user accounts
- Assign or update a user's role (FACULTY, HOD, MENTOR, STUDENT only — ADMIN role
  cannot be self-assigned via API, must be set via Django admin or superuser)
- Assign a user to a department
- Deactivate / reactivate accounts

All endpoints require IsAdminUserRole permission.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import User, Role
from .permissions import IsAdminUserRole
from .serializers import UserSerializer


ASSIGNABLE_ROLES = [Role.FACULTY, Role.HOD, Role.MENTOR, Role.STUDENT]


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUserRole])
def admin_user_detail_view(request, user_id):
    """
    GET  — Return full profile for a single user.
    PATCH — Update role, department, first_name, last_name, phone, is_active.

    Role assignment rules:
    - The ADMIN role can only be set on superusers; this endpoint disallows it
      to prevent privilege escalation through the API.
    - Changing a user's role from STUDENT/FACULTY/etc to another non-ADMIN role
      is always permitted by an administrator.
    """
    try:
        user = User.objects.select_related('department').get(pk=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(UserSerializer(user).data)

    # PATCH
    errors = {}

    new_role = request.data.get('role')
    if new_role is not None:
        if new_role == Role.ADMIN:
            errors['role'] = (
                "The Administrator role cannot be assigned through this form. "
                "Use the Django admin panel to grant administrator privileges."
            )
        elif new_role not in [r[0] for r in Role.choices]:
            errors['role'] = f"'{new_role}' is not a valid role. Choose from: {', '.join(ASSIGNABLE_ROLES)}."
        else:
            user.role = new_role

    department_id = request.data.get('department')
    if department_id is not None:
        if department_id == '':
            user.department = None
        else:
            try:
                from academic.models import Department
                user.department = Department.objects.get(pk=department_id)
            except (Department.DoesNotExist, ValueError, TypeError):
                errors['department'] = "Department not found. Select a valid department from the list."

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    for field in ('first_name', 'last_name', 'phone'):
        val = request.data.get(field)
        if val is not None:
            setattr(user, field, val.strip())

    is_active = request.data.get('is_active')
    if is_active is not None:
        user.is_active = bool(is_active)

    user.save()
    return Response(UserSerializer(user).data)


@api_view(['POST'])
@permission_classes([IsAdminUserRole])
def admin_assign_student_profile_view(request, user_id):
    """
    Create or update the academic Student profile for a user account.

    Required fields: roll_number, registration_number, section (id), admission_date.
    Optional: current_semester, guardian_name, guardian_phone.

    Plain-language validation errors are returned for all constraint failures.
    """
    from academic.models import Student, Section

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    if user.role != Role.STUDENT:
        return Response(
            {'detail': f"This user's role is '{user.get_role_display()}'. "
                       "Only accounts with the Student role can have a student academic profile. "
                       "Change the role to Student first."},
            status=status.HTTP_400_BAD_REQUEST
        )

    roll_number = request.data.get('roll_number', '').strip()
    registration_number = request.data.get('registration_number', '').strip()
    section_id = request.data.get('section')
    admission_date = request.data.get('admission_date')

    errors = {}

    if not roll_number:
        errors['roll_number'] = "Roll number is required (e.g. 24CSE001)."
    if not registration_number:
        errors['registration_number'] = "Registration number is required."
    if not section_id:
        errors['section'] = "A class section must be selected."
    if not admission_date:
        errors['admission_date'] = "Admission date is required."

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    # Validate section
    try:
        section = Section.objects.select_related('program', 'academic_year').get(pk=section_id)
    except Section.DoesNotExist:
        return Response({'section': 'Selected section does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

    # Check uniqueness
    roll_conflict = Student.objects.filter(roll_number__iexact=roll_number).exclude(user=user).first()
    if roll_conflict:
        return Response(
            {'roll_number': f"Roll number '{roll_number}' is already assigned to another student."},
            status=status.HTTP_400_BAD_REQUEST
        )

    reg_conflict = Student.objects.filter(registration_number__iexact=registration_number).exclude(user=user).first()
    if reg_conflict:
        return Response(
            {'registration_number': f"Registration number '{registration_number}' is already in use."},
            status=status.HTTP_400_BAD_REQUEST
        )

    current_semester = request.data.get('current_semester', section.semester)
    try:
        current_semester = int(current_semester)
    except (TypeError, ValueError):
        return Response({'current_semester': "Semester must be a whole number."}, status=status.HTTP_400_BAD_REQUEST)

    student, created = Student.objects.update_or_create(
        user=user,
        defaults={
            'roll_number': roll_number,
            'registration_number': registration_number,
            'section': section,
            'current_semester': current_semester,
            'admission_date': admission_date,
            'guardian_name': request.data.get('guardian_name', '').strip(),
            'guardian_phone': request.data.get('guardian_phone', '').strip(),
        }
    )

    # Keep User.department in sync with Section.program.department
    user.department = section.program.department
    user.save(update_fields=['department'])

    from academic.serializers import StudentSerializer
    return Response(
        {
            'detail': 'Student academic profile assigned successfully.' if created else 'Student academic profile updated.',
            'student': StudentSerializer(student).data,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAdminUserRole])
def admin_assign_faculty_profile_view(request, user_id):
    """
    Create or update the Faculty profile for a user account.

    Required fields: employee_id, department (id).
    Optional: designation, qualification.

    The user's role is automatically set to FACULTY if it is currently STUDENT.
    HOD and MENTOR roles are not changed — the admin sets those via the role
    assignment endpoint separately.
    """
    from academic.models import Faculty, Department

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    if user.role not in [Role.FACULTY, Role.HOD, Role.MENTOR]:
        return Response(
            {'detail': f"This user's current role is '{user.get_role_display()}'. "
                       "Assign a Faculty, HOD, or Mentor role before creating a faculty profile."},
            status=status.HTTP_400_BAD_REQUEST
        )

    employee_id = request.data.get('employee_id', '').strip()
    department_id = request.data.get('department')

    errors = {}

    if not employee_id:
        errors['employee_id'] = "Employee ID is required (e.g. FAC-CSE-001)."
    if not department_id:
        errors['department'] = "A department must be selected."

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        department = Department.objects.get(pk=department_id)
    except Department.DoesNotExist:
        return Response({'department': 'Selected department does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

    emp_conflict = Faculty.objects.filter(employee_id__iexact=employee_id).exclude(user=user).first()
    if emp_conflict:
        return Response(
            {'employee_id': f"Employee ID '{employee_id}' is already assigned to another faculty member."},
            status=status.HTTP_400_BAD_REQUEST
        )

    faculty, created = Faculty.objects.update_or_create(
        user=user,
        defaults={
            'employee_id': employee_id,
            'department': department,
            'designation': request.data.get('designation', 'Assistant Professor').strip(),
            'qualification': request.data.get('qualification', 'M.Tech').strip(),
        }
    )

    # Sync User.department
    user.department = department
    user.save(update_fields=['department'])

    from academic.serializers import FacultySerializer
    return Response(
        {
            'detail': 'Faculty profile created.' if created else 'Faculty profile updated.',
            'faculty': FacultySerializer(faculty).data,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAdminUserRole])
def admin_users_without_profile_view(request):
    """
    Returns users who have no academic profile yet:
    - Students with no Student record
    - Faculty/HOD/Mentor with no Faculty record

    Helps admins identify accounts that need onboarding.
    """
    from academic.models import Student, Faculty

    student_user_ids = Student.objects.values_list('user_id', flat=True)
    faculty_user_ids = Faculty.objects.values_list('user_id', flat=True)

    unprofiled_students = User.objects.filter(
        role=Role.STUDENT,
        is_active=True,
    ).exclude(id__in=student_user_ids)

    unprofiled_faculty = User.objects.filter(
        role__in=[Role.FACULTY, Role.HOD, Role.MENTOR],
        is_active=True,
    ).exclude(id__in=faculty_user_ids)

    return Response({
        'students_without_profile': [
            {'id': u.id, 'username': u.username, 'full_name': u.get_full_name() or u.username,
             'email': u.email, 'role': u.role, 'role_display': u.get_role_display()}
            for u in unprofiled_students
        ],
        'faculty_without_profile': [
            {'id': u.id, 'username': u.username, 'full_name': u.get_full_name() or u.username,
             'email': u.email, 'role': u.role, 'role_display': u.get_role_display()}
            for u in unprofiled_faculty
        ],
        'total_unprofiled': unprofiled_students.count() + unprofiled_faculty.count(),
    })
