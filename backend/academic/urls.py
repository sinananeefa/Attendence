from django.urls import path
from .views import (
    AdminDepartmentListCreateView, AdminSubjectListCreateView,
    DepartmentListCreateView, ProgramListCreateView, AcademicYearListCreateView,
    SemesterListCreateView, AcademicClassListCreateView, SectionListCreateView,
    SubjectListCreateView, FacultyAllocationListCreateView, CourseEnrollmentListCreateView,
    StudentListCreateView, FacultyListCreateView,
    FacultyMyAllocationsView, FacultyClassRosterView, StudentMyProfileView
)

urlpatterns = [
    # Admin-Only Strict Governance Endpoints (Admin for GET & POST)
    path('admin/departments/', AdminDepartmentListCreateView.as_view(), name='admin_departments'),
    path('admin/subjects/', AdminSubjectListCreateView.as_view(), name='admin_subjects'),

    # Academic Structure Catalog & Management (Admin Writable, Authenticated Readable)
    path('departments/', DepartmentListCreateView.as_view(), name='department_list_create'),
    path('programs/', ProgramListCreateView.as_view(), name='program_list_create'),
    path('academic-years/', AcademicYearListCreateView.as_view(), name='academic_year_list_create'),
    path('semesters/', SemesterListCreateView.as_view(), name='semester_list_create'),
    path('classes/', AcademicClassListCreateView.as_view(), name='class_list_create'),
    path('sections/', SectionListCreateView.as_view(), name='section_list_create'),
    path('subjects/', SubjectListCreateView.as_view(), name='subject_list_create'),
    path('faculty-allocations/', FacultyAllocationListCreateView.as_view(), name='faculty_allocation_list_create'),
    path('student-enrollments/', CourseEnrollmentListCreateView.as_view(), name='student_enrollment_list_create'),
    path('students/', StudentListCreateView.as_view(), name='student_list_create'),
    path('faculty/', FacultyListCreateView.as_view(), name='faculty_list_create'),

    # Faculty-Scoped Endpoints
    path('faculty/my-allocations/', FacultyMyAllocationsView.as_view(), name='faculty_allocations'),
    path('faculty/roster/<int:section_id>/', FacultyClassRosterView.as_view(), name='faculty_roster'),

    # Student-Scoped Endpoints
    path('student/my-profile/', StudentMyProfileView.as_view(), name='student_profile'),
]
