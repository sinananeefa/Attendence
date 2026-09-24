from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS

from accounts.models import Role
from accounts.permissions import (
    IsAdminUserRole, IsFacultyUserRole, IsStudentUserRole
)
from .models import (
    Department, Program, AcademicYear, Semester, AcademicClass, Section,
    Subject, Student, Faculty, FacultyAllocation, CourseEnrollment, TimetableSlot
)
from .serializers import (
    DepartmentSerializer, ProgramSerializer, AcademicYearSerializer,
    SemesterSerializer, AcademicClassSerializer, SectionSerializer,
    SubjectSerializer, StudentSerializer, FacultySerializer,
    FacultyAllocationSerializer, CourseEnrollmentSerializer, TimetableSlotSerializer
)


class IsAdminOrReadOnly(BasePermission):
    """
    Allows authenticated users to read academic catalogs.
    Strictly restricts creation, modification, and deletion to Dean / Admins.
    """
    message = "Unauthorized: Only administrators can modify academic structures."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user.role == Role.ADMIN or request.user.is_superuser)


# ==========================================
# ADMIN-ONLY STRICT ENDPOINTS (ADMIN FOR GET & POST)
# ==========================================

class AdminDepartmentListCreateView(generics.ListCreateAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminUserRole]


class AdminSubjectListCreateView(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAdminUserRole]


# ==========================================
# ACADEMIC STRUCTURE CATALOG (ADMIN WRITABLE, AUTH READABLE)
# ==========================================

class DepartmentListCreateView(generics.ListCreateAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]


class ProgramListCreateView(generics.ListCreateAPIView):
    queryset = Program.objects.select_related('department').all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAdminOrReadOnly]


class AcademicYearListCreateView(generics.ListCreateAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = [IsAdminOrReadOnly]


class SemesterListCreateView(generics.ListCreateAPIView):
    queryset = Semester.objects.select_related('academic_year').all()
    serializer_class = SemesterSerializer
    permission_classes = [IsAdminOrReadOnly]


class AcademicClassListCreateView(generics.ListCreateAPIView):
    queryset = AcademicClass.objects.select_related('program', 'academic_year').all()
    serializer_class = AcademicClassSerializer
    permission_classes = [IsAdminOrReadOnly]


class SectionListCreateView(generics.ListCreateAPIView):
    queryset = Section.objects.select_related('program', 'academic_year', 'mentor').all()
    serializer_class = SectionSerializer
    permission_classes = [IsAdminOrReadOnly]


class SubjectListCreateView(generics.ListCreateAPIView):
    queryset = Subject.objects.select_related('department', 'program').all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAdminOrReadOnly]


class FacultyAllocationListCreateView(generics.ListCreateAPIView):
    queryset = FacultyAllocation.objects.select_related('faculty__user', 'subject', 'section', 'academic_year').all()
    serializer_class = FacultyAllocationSerializer
    permission_classes = [IsAdminOrReadOnly]


class CourseEnrollmentListCreateView(generics.ListCreateAPIView):
    queryset = CourseEnrollment.objects.select_related('student__user', 'subject', 'section', 'academic_year').all()
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAdminOrReadOnly]


class StudentListCreateView(generics.ListCreateAPIView):
    queryset = Student.objects.select_related('user', 'section').all()
    serializer_class = StudentSerializer
    permission_classes = [IsAdminOrReadOnly]


class FacultyListCreateView(generics.ListCreateAPIView):
    queryset = Faculty.objects.select_related('user', 'department').all()
    serializer_class = FacultySerializer
    permission_classes = [IsAdminOrReadOnly]


# ==========================================
# FACULTY-SPECIFIC SCOPED APIS
# ==========================================

class FacultyMyAllocationsView(APIView):
    permission_classes = [IsFacultyUserRole]

    def get(self, request):
        user = request.user
        if user.is_admin_role or user.is_superuser:
            allocations = FacultyAllocation.objects.filter(is_active=True).select_related('faculty__user', 'subject', 'section')
        else:
            try:
                faculty = user.faculty_profile
                allocations = faculty.allocations.filter(is_active=True).select_related('faculty__user', 'subject', 'section')
            except Faculty.DoesNotExist:
                return Response({'detail': 'Faculty profile not found for this user.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = FacultyAllocationSerializer(allocations, many=True)
        return Response({
            'faculty_id': getattr(user, 'faculty_profile', None) and user.faculty_profile.employee_id,
            'faculty_name': user.get_full_name(),
            'allocations': serializer.data,
            'total_active_classes': allocations.count()
        })


class FacultyClassRosterView(APIView):
    permission_classes = [IsFacultyUserRole]

    def get(self, request, section_id):
        user = request.user
        is_authorized = user.is_admin_role or user.is_hod_role
        if not is_authorized:
            try:
                faculty = user.faculty_profile
                teaches_section = faculty.allocations.filter(section_id=section_id, is_active=True).exists()
                is_mentor = Section.objects.filter(id=section_id, mentor=user).exists()
                is_authorized = teaches_section or is_mentor
            except Faculty.DoesNotExist:
                is_authorized = False

        if not is_authorized:
            return Response(
                {'detail': 'Access denied: You are not assigned to teach or mentor this class section.'},
                status=status.HTTP_403_FORBIDDEN
            )

        students = Student.objects.filter(section_id=section_id).select_related('user', 'section')
        serializer = StudentSerializer(students, many=True)
        return Response({
            'section_id': section_id,
            'students_count': students.count(),
            'roster': serializer.data
        })


# ==========================================
# STUDENT-SPECIFIC SCOPED APIS
# ==========================================

class StudentMyProfileView(APIView):
    permission_classes = [IsStudentUserRole]

    def get(self, request):
        user = request.user
        try:
            student = user.student_profile
        except Student.DoesNotExist:
            return Response({'detail': 'Student profile not found for this account.'}, status=status.HTTP_404_NOT_FOUND)

        enrollments = CourseEnrollment.objects.filter(
            student=student,
            is_active=True
        ).select_related('subject')

        if enrollments.exists():
            subjects = [e.subject for e in enrollments]
        else:
            subjects = Subject.objects.filter(
                department=student.section.program.department,
                semester=student.current_semester
            )

        return Response({
            'student_id': student.id,
            'roll_number': student.roll_number,
            'registration_number': student.registration_number,
            'full_name': user.get_full_name() or user.username,
            'email': user.email,
            'section': {
                'id': student.section.id,
                'label': str(student.section),
                'semester': student.current_semester,
                'program': student.section.program.name,
                'mentor_name': student.section.mentor.get_full_name() if student.section.mentor else 'Unassigned',
            },
            'admission_date': student.admission_date,
            'enrolled_subjects': SubjectSerializer(subjects, many=True).data,
            'enrolled_count': len(subjects)
        })
