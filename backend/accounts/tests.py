from datetime import date
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User, Role
from academic.models import (
    Department, Program, AcademicYear, Section, Subject, Student, Faculty,
    FacultyAllocation
)


class AuthenticationAndRBACTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create basic academic structure
        self.dept = Department.objects.create(code='CSE', name='Computer Science')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE')
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A')
        self.subject = Subject.objects.create(department=self.dept, code='CS401', title='Database Systems', semester=4)

        # 1. Admin User
        self.admin_user = User.objects.create_user(
            username='test_admin',
            email='admin@edumerge.ac.in',
            password='AdminPassword123',
            role=Role.ADMIN
        )

        # 2. Faculty User & Profile
        self.faculty_user = User.objects.create_user(
            username='test_faculty',
            email='faculty@edumerge.ac.in',
            password='FacultyPassword123',
            role=Role.FACULTY,
            department=self.dept
        )
        self.faculty = Faculty.objects.create(
            user=self.faculty_user,
            employee_id='FAC-999',
            designation='Assistant Professor',
            department=self.dept
        )
        self.allocation = FacultyAllocation.objects.create(
            faculty=self.faculty,
            subject=self.subject,
            section=self.section,
            academic_year=self.ay
        )

        # 3. Student User & Profile
        self.student_user = User.objects.create_user(
            username='test_student',
            email='student@edumerge.ac.in',
            password='StudentPassword123',
            role=Role.STUDENT,
            department=self.dept
        )
        self.student = Student.objects.create(
            user=self.student_user,
            roll_number='24CSE999',
            registration_number='REG999',
            section=self.section,
            current_semester=4,
            admission_date=date(2024, 8, 1)
        )

    def test_login_success_returns_jwt_tokens(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'test_admin',
            'password': 'AdminPassword123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertTrue(response.data['permissions']['is_admin'])

    def test_login_invalid_password_fails(self):
        response = self.client.post('/api/auth/login/', {
            'username': 'test_admin',
            'password': 'WrongPassword!'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)

    def test_registration_creates_hashed_student_account_and_logs_in(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'new_student',
            'email': 'new.student@edumerge.ac.in',
            'password': 'NewStudentPassword123!',
            'password_confirm': 'NewStudentPassword123!',
            'first_name': 'New',
            'last_name': 'Student',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        created_user = User.objects.get(username='new_student')
        self.assertEqual(created_user.role, Role.STUDENT)
        self.assertTrue(created_user.check_password('NewStudentPassword123!'))
        self.assertNotEqual(created_user.password, 'NewStudentPassword123!')

    def test_registration_rejects_duplicate_identity_and_privileged_role_input(self):
        response = self.client.post('/api/auth/register/', {
            'username': 'test_admin',
            'email': 'another@edumerge.ac.in',
            'password': 'NewStudentPassword123!',
            'password_confirm': 'NewStudentPassword123!',
            'role': Role.ADMIN,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.get(username='test_admin').role, Role.ADMIN)

    def test_demo_role_switch_endpoint_is_removed(self):
        response = self.client.post('/api/auth/demo-switch-role/', {'role': Role.ADMIN})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get('/api/academic/admin/departments/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_cannot_access_admin_api(self):
        """Student token must receive 403 Forbidden when requesting admin endpoints"""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get('/api/academic/admin/departments/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_access_faculty_api(self):
        """Student token must receive 403 Forbidden when requesting faculty allocations"""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get('/api/academic/faculty/my-allocations/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_faculty_cannot_access_admin_api(self):
        """Faculty token must receive 403 Forbidden when requesting admin endpoints"""
        self.client.force_authenticate(user=self.faculty_user)
        response = self.client.get('/api/academic/admin/departments/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_faculty_can_access_their_allocations(self):
        """Faculty token can view their own allocated teaching classes"""
        self.client.force_authenticate(user=self.faculty_user)
        response = self.client.get('/api/academic/faculty/my-allocations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_active_classes'], 1)
        self.assertEqual(response.data['allocations'][0]['subject_code'], 'CS401')

    def test_student_can_access_their_own_profile(self):
        """Student token can access their enrolled profile and curriculum"""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get('/api/academic/student/my-profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['roll_number'], '24CSE999')
        self.assertIn('section', response.data)

    def test_admin_can_access_admin_departments(self):
        """Admin token receives 200 OK and can manage academic hierarchy"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/academic/admin/departments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
