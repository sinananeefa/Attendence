"""
Automated Validation Tests for Phase 9: AI Attendance Assistant.
All model field names verified against actual database schema.
"""

from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User
from academic.models import (
    Department, Program, AcademicYear, AcademicClass, Section, Subject,
    Faculty, Student, FacultyAllocation, CourseEnrollment
)
from attendance.models import AttendanceSession, AttendanceRecord, AttendanceStatus
from ai_assistant import tools
from ai_assistant.service import AIAttendanceAssistantService


def make_section(program, ay, academic_class, name='A'):
    """Helper: create a Section with all required denormalised fields."""
    return Section.objects.create(
        program=program,
        academic_year=ay,
        semester=4,
        academic_class=academic_class,
        name=name,
        max_capacity=60
    )


class AIAttendanceToolsValidationTests(TestCase):
    """Unit tests validating each deterministic AI tool function."""

    @classmethod
    def setUpTestData(cls):
        cls.dept_cse = Department.objects.create(name='Computer Science & Engineering', code='CSE')
        cls.dept_ece = Department.objects.create(name='Electronics & Communication', code='ECE')

        cls.program = Program.objects.create(
            name='B.Tech CSE', code='BTCSE', department=cls.dept_cse, total_semesters=8
        )
        cls.ay = AcademicYear.objects.create(
            year_label='2026-2027', start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30), is_current=True
        )
        cls.academic_class = AcademicClass.objects.create(
            program=cls.program, academic_year=cls.ay, semester=4
        )
        cls.section = make_section(cls.program, cls.ay, cls.academic_class, 'A')

        cls.subject_dbms = Subject.objects.create(
            department=cls.dept_cse, code='CS401', title='Database Systems', credits=4, semester=4
        )
        cls.subject_os = Subject.objects.create(
            department=cls.dept_cse, code='CS402', title='Operating Systems', credits=4, semester=4
        )

        cls.admin_user = User.objects.create_superuser('admin_ai', 'admin@ai.com', 'AdminPass123', role='ADMIN')
        cls.faculty_user = User.objects.create_user(
            'fac_priya', 'priya@ai.com', 'FacPass123', role='FACULTY',
            first_name='Priya', last_name='Nair'
        )
        cls.faculty = Faculty.objects.create(
            user=cls.faculty_user, department=cls.dept_cse,
            employee_id='EMP101', designation='Assistant Professor'
        )

        # Student 1: Rahul Sharma (24CSE001) - will be below 75%
        cls.student1_user = User.objects.create_user(
            'rahul_s', 'rahul@ai.com', 'StudentPass123',
            role='STUDENT', first_name='Rahul', last_name='Sharma'
        )
        cls.student1 = Student.objects.create(
            user=cls.student1_user, roll_number='24CSE001',
            registration_number='REG24001', section=cls.section,
            current_semester=4, admission_date=date(2024, 8, 1)
        )

        # Student 2: Ananya Iyer (24CSE002) - 100%
        cls.student2_user = User.objects.create_user(
            'ananya_i', 'ananya@ai.com', 'StudentPass123',
            role='STUDENT', first_name='Ananya', last_name='Iyer'
        )
        cls.student2 = Student.objects.create(
            user=cls.student2_user, roll_number='24CSE002',
            registration_number='REG24002', section=cls.section,
            current_semester=4, admission_date=date(2024, 8, 1)
        )

        # Enrollments
        CourseEnrollment.objects.create(
            student=cls.student1, subject=cls.subject_dbms,
            section=cls.section, academic_year=cls.ay, is_active=True
        )
        CourseEnrollment.objects.create(
            student=cls.student2, subject=cls.subject_dbms,
            section=cls.section, academic_year=cls.ay, is_active=True
        )

        # Faculty Allocation
        FacultyAllocation.objects.create(
            faculty=cls.faculty, subject=cls.subject_dbms,
            section=cls.section, academic_year=cls.ay, is_active=True
        )

        # Create 4 sessions: Rahul 2/4 (50%), Ananya 4/4 (100%)
        today = timezone.localdate()
        for i in range(1, 5):
            sess = AttendanceSession.objects.create(
                faculty=cls.faculty_user,
                section=cls.section,
                subject=cls.subject_dbms,
                session_date=today - timedelta(days=i),
                period_number=1
            )
            AttendanceRecord.objects.create(
                session=sess, student=cls.student2, status=AttendanceStatus.PRESENT
            )
            st_status = AttendanceStatus.PRESENT if i <= 2 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(
                session=sess, student=cls.student1, status=st_status
            )

    def test_get_student_attendance_by_name(self):
        """Tool resolves student by first name and returns calculated data"""
        res = tools.get_student_attendance('Rahul')
        self.assertTrue(res['found'])
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['student']['roll_number'], '24CSE001')
        self.assertEqual(res['student']['full_name'], 'Rahul Sharma')
        self.assertEqual(res['overall_attendance']['overall_percentage'], 50.0)
        self.assertEqual(res['overall_attendance']['total_conducted'], 4)
        self.assertEqual(res['overall_attendance']['total_attended'], 2)
        self.assertEqual(res['overall_attendance']['total_missed'], 2)
        self.assertTrue(res['overall_attendance']['is_low_attendance'])

    def test_get_student_attendance_by_roll_number(self):
        """Tool resolves student by roll number (case insensitive)"""
        res = tools.get_student_attendance('24cse002')
        self.assertTrue(res['found'])
        self.assertEqual(res['student']['roll_number'], '24CSE002')
        self.assertEqual(res['overall_attendance']['overall_percentage'], 100.0)
        self.assertFalse(res['overall_attendance']['is_low_attendance'])

    def test_get_student_attendance_not_found(self):
        """Tool returns clean not_found for non-existent student"""
        res = tools.get_student_attendance('XYZNonExistentStudent')
        self.assertFalse(res['found'])
        self.assertEqual(res['status'], 'not_found')

    def test_get_low_attendance_students_75_percent(self):
        """Identifies students strictly below 75%"""
        res = tools.get_low_attendance_students(threshold=75.0)
        self.assertEqual(res['status'], 'success')
        roll_numbers = [s['roll_number'] for s in res['students']]
        self.assertIn('24CSE001', roll_numbers)   # 50% < 75%
        self.assertNotIn('24CSE002', roll_numbers)  # 100% >= 75%

    def test_get_low_attendance_students_70_percent(self):
        """50% student also falls below 70%"""
        res = tools.get_low_attendance_students(threshold=70.0)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['threshold_used'], 70.0)
        roll_numbers = [s['roll_number'] for s in res['students']]
        self.assertIn('24CSE001', roll_numbers)

    def test_get_low_attendance_students_empty_when_threshold_low(self):
        """No students below 40% threshold"""
        res = tools.get_low_attendance_students(threshold=40.0)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['low_attendance_count'], 0)
        self.assertTrue(res['is_empty'])

    def test_get_subject_attendance_returns_active(self):
        """Returns subjects that have sessions"""
        res = tools.get_subject_attendance()
        self.assertEqual(res['status'], 'success')
        self.assertIsNotNone(res['lowest_attendance_subject'])

    def test_get_department_attendance(self):
        """Compares departments and identifies lowest"""
        res = tools.get_department_attendance()
        self.assertEqual(res['status'], 'success')
        self.assertGreaterEqual(res['total_departments'], 1)
        self.assertIsNotNone(res['lowest_attendance_department'])

    def test_get_attendance_history(self):
        """Returns chronological records in window"""
        res = tools.get_attendance_history(student_identifier='24CSE001', days=30)
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['total_matching_records'], 4)
        for r in res['records']:
            self.assertEqual(r['student_roll_number'], '24CSE001')

    def test_get_attendance_statistics(self):
        """Computes stats over time window"""
        res = tools.get_attendance_statistics(time_frame='month')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['current_window']['sessions_conducted'], 4)


class AIAssistantNaturalLanguageQueriesTests(TestCase):
    """Tests all 6 required natural language query patterns."""

    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name='Computer Science & Engineering', code='CSE')
        cls.program = Program.objects.create(
            name='B.Tech CSE', code='BTCSE', department=cls.dept, total_semesters=8
        )
        cls.ay = AcademicYear.objects.create(
            year_label='2026-2027', start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30), is_current=True
        )
        cls.academic_class = AcademicClass.objects.create(
            program=cls.program, academic_year=cls.ay, semester=4
        )
        cls.section = make_section(cls.program, cls.ay, cls.academic_class, 'A')
        cls.subject = Subject.objects.create(
            department=cls.dept, code='CS401', title='Database Systems', credits=4, semester=4
        )

        cls.admin_user = User.objects.create_superuser('admin_ai', 'admin@ai.com', 'AdminPass123', role='ADMIN')
        cls.faculty_user = User.objects.create_user(
            'fac_priya', 'priya@ai.com', 'FacPass123', role='FACULTY', first_name='Priya'
        )
        cls.faculty = Faculty.objects.create(
            user=cls.faculty_user, department=cls.dept,
            employee_id='EMP101', designation='Assistant Professor'
        )

        cls.student_user = User.objects.create_user(
            'rahul_s', 'rahul@ai.com', 'StudentPass123',
            role='STUDENT', first_name='Rahul', last_name='Sharma'
        )
        cls.student = Student.objects.create(
            user=cls.student_user, roll_number='24CSE001',
            registration_number='REG24001', section=cls.section,
            current_semester=4, admission_date=date(2024, 8, 1)
        )
        CourseEnrollment.objects.create(
            student=cls.student, subject=cls.subject,
            section=cls.section, academic_year=cls.ay, is_active=True
        )
        FacultyAllocation.objects.create(
            faculty=cls.faculty, subject=cls.subject,
            section=cls.section, academic_year=cls.ay, is_active=True
        )

        today = timezone.localdate()
        for i in range(1, 5):
            sess = AttendanceSession.objects.create(
                faculty=cls.faculty_user, section=cls.section, subject=cls.subject,
                session_date=today - timedelta(days=i), period_number=1
            )
            st_status = AttendanceStatus.PRESENT if i <= 2 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=cls.student, status=st_status)

    def test_query_below_75_percent(self):
        """'Which students are below 75%?' → get_low_attendance_students"""
        res = AIAttendanceAssistantService.process_query(self.admin_user, "Which students are below 75%?")
        self.assertTrue(res['success'])
        self.assertEqual(res['tool_called'], 'get_low_attendance_students')
        self.assertIn("Rahul Sharma", res['answer'])

    def test_query_lowest_subject_attendance(self):
        """'Which subjects have the lowest attendance?' → get_subject_attendance"""
        res = AIAttendanceAssistantService.process_query(self.admin_user, "Which subjects have the lowest attendance?")
        self.assertTrue(res['success'])
        self.assertEqual(res['tool_called'], 'get_subject_attendance')
        self.assertIn("CS401", res['answer'])

    def test_query_show_rahuls_attendance(self):
        """'Show Rahul's attendance.' → get_student_attendance"""
        res = AIAttendanceAssistantService.process_query(self.admin_user, "Show Rahul's attendance.")
        self.assertTrue(res['success'])
        self.assertEqual(res['tool_called'], 'get_student_attendance')
        self.assertIn("Rahul Sharma", res['answer'])

    def test_query_lowest_department(self):
        """'Which department has the lowest attendance?' → get_department_attendance"""
        res = AIAttendanceAssistantService.process_query(self.admin_user, "Which department has the lowest attendance?")
        self.assertTrue(res['success'])
        self.assertEqual(res['tool_called'], 'get_department_attendance')
        self.assertIn("CSE", res['answer'])

    def test_query_below_70_percent(self):
        """'Which students have attendance below 70%?' → get_low_attendance_students with threshold=70"""
        res = AIAttendanceAssistantService.process_query(self.admin_user, "Which students have attendance below 70%?")
        self.assertTrue(res['success'])
        self.assertEqual(res['tool_called'], 'get_low_attendance_students')
        self.assertEqual(res['tool_parameters']['threshold'], 70.0)

    def test_query_attendance_changed_month(self):
        """'How has attendance changed this month?' → get_attendance_statistics"""
        res = AIAttendanceAssistantService.process_query(self.admin_user, "How has attendance changed this month?")
        self.assertTrue(res['success'])
        self.assertEqual(res['tool_called'], 'get_attendance_statistics')


class AIAssistantSecurityAndRBACAPITests(TestCase):
    """Verifies read-only integrity, SQL safety, and role scoping."""

    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name='Computer Science', code='CSE')
        cls.program = Program.objects.create(
            name='B.Tech CSE', code='BTCSE', department=cls.dept, total_semesters=8
        )
        cls.ay = AcademicYear.objects.create(
            year_label='2026-2027', start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30), is_current=True
        )
        cls.academic_class = AcademicClass.objects.create(
            program=cls.program, academic_year=cls.ay, semester=4
        )
        cls.section = make_section(cls.program, cls.ay, cls.academic_class, 'A')

        cls.admin_user = User.objects.create_superuser('admin_ai', 'admin@ai.com', 'AdminPass123', role='ADMIN')
        cls.student_user = User.objects.create_user(
            'stud_user', 'stud@ai.com', 'StudentPass123', role='STUDENT'
        )
        cls.student = Student.objects.create(
            user=cls.student_user, roll_number='24CSE099',
            registration_number='REG24099', section=cls.section,
            current_semester=4, admission_date=date(2024, 8, 1)
        )

    def setUp(self):
        self.client = APIClient()

    def test_student_blocked_from_institutional_list(self):
        """Student gets privacy guard when querying institutional low attendance list"""
        self.client.force_authenticate(user=self.student_user)
        resp = self.client.post('/api/ai/query/', {'query': 'Which students are below 75%?'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('privacy protection', resp.data['answer'].lower())
        self.assertEqual(resp.data['execution_source'], 'security_guard')

    def test_student_blocked_from_other_student(self):
        """Student cannot query another student by name"""
        self.client.force_authenticate(user=self.student_user)
        resp = self.client.post('/api/ai/query/', {'query': 'Show Rahul attendance'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('do not have permission', resp.data['answer'].lower())

    def test_student_can_query_own(self):
        """Student can ask for their own attendance"""
        self.client.force_authenticate(user=self.student_user)
        resp = self.client.post('/api/ai/query/', {'query': 'Show my attendance'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['tool_called'], 'get_student_attendance')
        self.assertEqual(resp.data['tool_parameters']['student_identifier'], 'stud_user')

    def test_read_only_guarantee(self):
        """No mutations occur during AI queries"""
        self.client.force_authenticate(user=self.admin_user)
        before_sessions = AttendanceSession.objects.count()
        before_records = AttendanceRecord.objects.count()
        self.client.post('/api/ai/query/', {'query': 'Which students are below 75%?'}, format='json')
        self.client.post('/api/ai/query/', {'query': 'How has attendance changed this month?'}, format='json')
        self.assertEqual(AttendanceSession.objects.count(), before_sessions)
        self.assertEqual(AttendanceRecord.objects.count(), before_records)

    def test_sql_injection_defense(self):
        """Malicious SQL input cannot execute arbitrary queries"""
        malicious = "Rahul' OR '1'='1'; DROP TABLE attendance_record; --"
        res = tools.get_student_attendance(malicious)
        self.assertFalse(res['found'])
        self.assertEqual(res['status'], 'not_found')

    def test_unauthenticated_blocked(self):
        """Unauthenticated requests are rejected with 401"""
        resp = self.client.post('/api/ai/query/', {'query': 'Which students below 75%?'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
