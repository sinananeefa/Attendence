from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User, Role
from academic.models import (
    Department, Program, AcademicYear, AcademicClass, Section,
    Subject, Student, Faculty, FacultyAllocation, CourseEnrollment
)
from attendance.models import (
    AttendanceSession, AttendanceRecord, AttendanceCorrection, AttendanceAuditLog,
    AttendanceStatus, SessionStatus, CorrectionStatus, AuditAction, SessionType,
    AttendancePolicy
)
from attendance.services import (
    calculate_attendance_percentage,
    calculate_classes_needed_for_target,
    calculate_classes_can_afford_to_miss,
    get_attendance_status_category,
    AttendanceCalculationService,
    AttendanceStatusCategory,
    is_low_attendance,
    get_effective_threshold,
    AttendanceCorrectionService
)




class AttendanceDomainModelTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(code='CSE', name='Computer Science')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE', total_semesters=8)
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.academic_class = AcademicClass.objects.create(program=self.program, academic_year=self.ay, semester=4)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A', academic_class=self.academic_class)
        self.section_b = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='B', academic_class=self.academic_class)
        self.subject = Subject.objects.create(department=self.dept, code='CS401', title='Database Systems', semester=4)
        self.subject_sem5 = Subject.objects.create(department=self.dept, code='CS501', title='Operating Systems', semester=5)

        # Faculty
        self.faculty_user = User.objects.create_user(
            username='prof_patel', email='patel@edumerge.ac.in', role=Role.FACULTY, first_name='Sanjay', last_name='Patel'
        )
        self.faculty = Faculty.objects.create(user=self.faculty_user, employee_id='FAC-201', designation='Professor', department=self.dept)

        # Students
        self.student_user1 = User.objects.create_user(username='24cse001', email='s1@edumerge.ac.in', role=Role.STUDENT, first_name='Amit', last_name='Verma')
        self.student1 = Student.objects.create(user=self.student_user1, roll_number='24CSE001', registration_number='REG001', section=self.section, admission_date=date(2024, 8, 1))

        self.student_user2 = User.objects.create_user(username='24cse002', email='s2@edumerge.ac.in', role=Role.STUDENT, first_name='Neha', last_name='Gupta')
        self.student2 = Student.objects.create(user=self.student_user2, roll_number='24CSE002', registration_number='REG002', section=self.section, admission_date=date(2024, 8, 1))

        self.student_user3 = User.objects.create_user(username='24cse003', email='s3@edumerge.ac.in', role=Role.STUDENT, first_name='Rahul', last_name='Sharma')
        self.student3 = Student.objects.create(user=self.student_user3, roll_number='24CSE003', registration_number='REG003', section=self.section, admission_date=date(2024, 8, 1))

        self.student_user4 = User.objects.create_user(username='24cse004', email='s4@edumerge.ac.in', role=Role.STUDENT, first_name='Pooja', last_name='Reddy')
        self.student4 = Student.objects.create(user=self.student_user4, roll_number='24CSE004', registration_number='REG004', section=self.section_b, admission_date=date(2024, 8, 1))

    def test_deterministic_attendance_percentage_calculation(self):
        """Attendance percentage is strictly deterministic: (Present + Late + OD + Medical) / Total * 100"""
        session = AttendanceSession.objects.create(
            faculty=self.faculty_user,
            section=self.section,
            subject=self.subject,
            session_date=date(2026, 9, 24),
            period_number=1,
            topic_covered='SQL Joins and Normalization'
        )

        # 0 records -> 0.0% zero-division safe
        self.assertEqual(session.total_students, 0)
        self.assertEqual(session.attendance_percentage, 0.0)

        # 1 Present, 1 Absent, 1 Late -> Effective Present = 2, Total = 3 -> 66.67%
        AttendanceRecord.objects.create(session=session, student=self.student1, status=AttendanceStatus.PRESENT)
        AttendanceRecord.objects.create(session=session, student=self.student2, status=AttendanceStatus.ABSENT)
        AttendanceRecord.objects.create(session=session, student=self.student3, status=AttendanceStatus.LATE)

        self.assertEqual(session.total_students, 3)
        self.assertEqual(session.present_count, 1)
        self.assertEqual(session.absent_count, 1)
        self.assertEqual(session.late_count, 1)
        self.assertEqual(session.attendance_percentage, 66.67)

    def test_future_date_rejected_by_model(self):
        """Sessions cannot be scheduled or marked for future dates"""
        tomorrow = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            session = AttendanceSession(
                faculty=self.faculty_user,
                section=self.section,
                subject=self.subject,
                session_date=tomorrow,
                period_number=1
            )
            session.clean()

    def test_invalid_period_number_rejected_by_model(self):
        """Period number must be bounded between 1 and 7"""
        with self.assertRaises(ValidationError):
            s_zero = AttendanceSession(
                faculty=self.faculty_user,
                section=self.section,
                subject=self.subject,
                session_date=date.today(),
                period_number=0
            )
            s_zero.clean()

        with self.assertRaises(ValidationError):
            s_eight = AttendanceSession(
                faculty=self.faculty_user,
                section=self.section,
                subject=self.subject,
                session_date=date.today(),
                period_number=8
            )
            s_eight.clean()

    def test_semester_mismatch_rejected_by_model(self):
        """Subject semester must match section semester"""
        with self.assertRaises(ValidationError):
            session = AttendanceSession(
                faculty=self.faculty_user,
                section=self.section,  # Semester 4
                subject=self.subject_sem5,  # Semester 5
                session_date=date.today(),
                period_number=1
            )
            session.clean()

    def test_student_from_different_section_rejected_by_model(self):
        """Student from Section B cannot be marked in a Section A session"""
        session = AttendanceSession.objects.create(
            faculty=self.faculty_user,
            section=self.section,
            subject=self.subject,
            session_date=date.today(),
            period_number=1
        )
        with self.assertRaises(ValidationError):
            record = AttendanceRecord(session=session, student=self.student4, status=AttendanceStatus.PRESENT)
            record.clean()

    def test_unique_session_constraint_prevents_duplicate_marking(self):
        """Cannot create two attendance sessions for the same section, subject, date, and period"""
        today = date.today()
        AttendanceSession.objects.create(
            faculty=self.faculty_user,
            section=self.section,
            subject=self.subject,
            session_date=today,
            period_number=2
        )

        with self.assertRaises((IntegrityError, ValidationError)):
            AttendanceSession.objects.create(
                faculty=self.faculty_user,
                section=self.section,
                subject=self.subject,
                session_date=today,
                period_number=2
            )

    def test_unique_record_constraint_prevents_duplicate_student_in_session(self):
        """A student cannot have more than one record in the same session"""
        session = AttendanceSession.objects.create(
            faculty=self.faculty_user,
            section=self.section,
            subject=self.subject,
            session_date=date.today(),
            period_number=3
        )
        AttendanceRecord.objects.create(session=session, student=self.student1, status=AttendanceStatus.PRESENT)

        with self.assertRaises((IntegrityError, ValidationError)):
            AttendanceRecord.objects.create(session=session, student=self.student1, status=AttendanceStatus.ABSENT)


class AttendanceBatchRecordingAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = Department.objects.create(code='CSE', name='Computer Science')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE', total_semesters=8)
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.academic_class = AcademicClass.objects.create(program=self.program, academic_year=self.ay, semester=4)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A', academic_class=self.academic_class)
        self.section_b = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='B', academic_class=self.academic_class)
        self.subject = Subject.objects.create(department=self.dept, code='CS401', title='Database Systems', semester=4)

        # Faculty 1 (Allocated)
        self.faculty_user1 = User.objects.create_user(
            username='prof_patel', email='patel@edumerge.ac.in', role=Role.FACULTY, first_name='Sanjay', last_name='Patel'
        )
        self.faculty1 = Faculty.objects.create(user=self.faculty_user1, employee_id='FAC-201', designation='Professor', department=self.dept)
        self.allocation1 = FacultyAllocation.objects.create(
            faculty=self.faculty1, subject=self.subject, section=self.section, academic_year=self.ay, is_active=True
        )

        # Faculty 2 (Not allocated)
        self.faculty_user2 = User.objects.create_user(
            username='prof_rao', email='rao@edumerge.ac.in', role=Role.FACULTY, first_name='Vikram', last_name='Rao'
        )
        self.faculty2 = Faculty.objects.create(user=self.faculty_user2, employee_id='FAC-202', designation='Asst Professor', department=self.dept)

        # Students
        self.student_user1 = User.objects.create_user(username='24cse001', email='s1@edumerge.ac.in', role=Role.STUDENT, first_name='Amit', last_name='Verma')
        self.student1 = Student.objects.create(user=self.student_user1, roll_number='24CSE001', registration_number='REG001', section=self.section, admission_date=date(2024, 8, 1))

        self.student_user2 = User.objects.create_user(username='24cse002', email='s2@edumerge.ac.in', role=Role.STUDENT, first_name='Neha', last_name='Gupta')
        self.student2 = Student.objects.create(user=self.student_user2, roll_number='24CSE002', registration_number='REG002', section=self.section, admission_date=date(2024, 8, 1))

        self.student_user3 = User.objects.create_user(username='24cse003', email='s3@edumerge.ac.in', role=Role.STUDENT, first_name='Rahul', last_name='Sharma')
        self.student3 = Student.objects.create(user=self.student_user3, roll_number='24CSE003', registration_number='REG003', section=self.section, admission_date=date(2024, 8, 1))

        self.student_user_other = User.objects.create_user(username='24cse099', email='s99@edumerge.ac.in', role=Role.STUDENT, first_name='Other', last_name='Student')
        self.student_other = Student.objects.create(user=self.student_user_other, roll_number='24CSE099', registration_number='REG099', section=self.section_b, admission_date=date(2024, 8, 1))

    def test_allocated_faculty_submits_attendance_successfully(self):
        """Allocated faculty can mark attendance with deterministic statistics and audit trail"""
        self.client.force_authenticate(user=self.faculty_user1)
        today_str = date.today().isoformat()

        payload = {
            'section_id': self.section.id,
            'subject_id': self.subject.id,
            'session_date': today_str,
            'period_number': 1,
            'session_type': 'REGULAR',
            'topic_covered': 'B-Tree Indexing and Query Optimization',
            'records': [
                {'student_id': self.student1.id, 'status': 'PRESENT', 'remarks': ''},
                {'student_id': self.student2.id, 'status': 'PRESENT', 'remarks': ''},
                {'student_id': self.student3.id, 'status': 'ABSENT', 'remarks': 'Unexcused'},
            ]
        }

        response = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['stats']['total_students'], 3)
        self.assertEqual(response.data['stats']['present_count'], 2)
        self.assertEqual(response.data['stats']['absent_count'], 1)
        # Deterministic: 2 / 3 * 100 = 66.67
        self.assertEqual(response.data['stats']['attendance_percentage'], 66.67)

        # Verify database entities
        session = AttendanceSession.objects.get(id=response.data['session']['id'])
        self.assertEqual(session.records.count(), 3)
        self.assertEqual(session.status, SessionStatus.SUBMITTED)

        # Verify audit logs
        audit_count = AttendanceAuditLog.objects.filter(record__session=session).count()
        self.assertEqual(audit_count, 3)

    def test_duplicate_attendance_session_prevented(self):
        """Duplicate session for identical section, subject, date, and period is rejected with 400 Bad Request"""
        self.client.force_authenticate(user=self.faculty_user1)
        today_str = date.today().isoformat()

        payload = {
            'section_id': self.section.id,
            'subject_id': self.subject.id,
            'session_date': today_str,
            'period_number': 2,
            'topic_covered': 'Transactions & ACID properties',
            'records': [
                {'student_id': self.student1.id, 'status': 'PRESENT'},
                {'student_id': self.student2.id, 'status': 'PRESENT'},
            ]
        }

        # First submission succeeds
        resp1 = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Immediate duplicate submission fails
        resp2 = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue('non_field_errors' in resp2.data or 'detail' in resp2.data)

    def test_student_role_strictly_forbidden_from_recording_attendance(self):
        """Students cannot submit attendance"""
        self.client.force_authenticate(user=self.student_user1)
        today_str = date.today().isoformat()

        payload = {
            'section_id': self.section.id,
            'subject_id': self.subject.id,
            'session_date': today_str,
            'period_number': 1,
            'records': [{'student_id': self.student1.id, 'status': 'PRESENT'}]
        }

        response = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unallocated_faculty_forbidden_from_recording_attendance(self):
        """Faculty not allocated to the section/subject cannot record attendance"""
        self.client.force_authenticate(user=self.faculty_user2)
        today_str = date.today().isoformat()

        payload = {
            'section_id': self.section.id,
            'subject_id': self.subject.id,
            'session_date': today_str,
            'period_number': 1,
            'records': [{'student_id': self.student1.id, 'status': 'PRESENT'}]
        }

        response = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_future_date_rejected_by_api(self):
        """Attendance submission for a future date returns 400 Bad Request"""
        self.client.force_authenticate(user=self.faculty_user1)
        tomorrow_str = (date.today() + timedelta(days=2)).isoformat()

        payload = {
            'section_id': self.section.id,
            'subject_id': self.subject.id,
            'session_date': tomorrow_str,
            'period_number': 1,
            'records': [{'student_id': self.student1.id, 'status': 'PRESENT'}]
        }

        response = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_student_in_payload_rejected(self):
        """Payload with same student twice returns 400 Bad Request"""
        self.client.force_authenticate(user=self.faculty_user1)
        today_str = date.today().isoformat()

        payload = {
            'section_id': self.section.id,
            'subject_id': self.subject.id,
            'session_date': today_str,
            'period_number': 3,
            'records': [
                {'student_id': self.student1.id, 'status': 'PRESENT'},
                {'student_id': self.student1.id, 'status': 'ABSENT'},
            ]
        }

        response = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_from_different_section_rejected_by_api(self):
        """Payload containing a student from another section returns 400 Bad Request"""
        self.client.force_authenticate(user=self.faculty_user1)
        today_str = date.today().isoformat()

        payload = {
            'section_id': self.section.id,
            'subject_id': self.subject.id,
            'session_date': today_str,
            'period_number': 4,
            'records': [
                {'student_id': self.student1.id, 'status': 'PRESENT'},
                {'student_id': self.student_other.id, 'status': 'PRESENT'},
            ]
        }

        response = self.client.post('/api/attendance/record/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AttendanceHistoryAndRosterAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = Department.objects.create(code='CSE', name='Computer Science')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE', total_semesters=8)
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.academic_class = AcademicClass.objects.create(program=self.program, academic_year=self.ay, semester=4)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A', academic_class=self.academic_class)
        self.subject = Subject.objects.create(department=self.dept, code='CS401', title='Database Systems', semester=4)

        self.faculty_user = User.objects.create_user(
            username='prof_patel', email='patel@edumerge.ac.in', role=Role.FACULTY, first_name='Sanjay', last_name='Patel'
        )
        self.faculty = Faculty.objects.create(user=self.faculty_user, employee_id='FAC-201', designation='Professor', department=self.dept)
        self.allocation = FacultyAllocation.objects.create(
            faculty=self.faculty, subject=self.subject, section=self.section, academic_year=self.ay, is_active=True
        )

        self.student_user1 = User.objects.create_user(username='24cse001', email='s1@edumerge.ac.in', role=Role.STUDENT, first_name='Amit', last_name='Verma')
        self.student1 = Student.objects.create(user=self.student_user1, roll_number='24CSE001', registration_number='REG001', section=self.section, admission_date=date(2024, 8, 1))

    def test_roster_endpoint_returns_students_and_recorded_periods(self):
        """Roster endpoint returns student list and marks recorded periods for the selected date"""
        self.client.force_authenticate(user=self.faculty_user)
        today = date.today()

        # Create 1 session for period 1
        AttendanceSession.objects.create(
            faculty=self.faculty_user, section=self.section, subject=self.subject,
            session_date=today, period_number=1
        )

        url = f"/api/attendance/roster/?section_id={self.section.id}&subject_id={self.subject.id}&date={today.isoformat()}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['students_count'], 1)
        self.assertEqual(response.data['students'][0]['roll_number'], '24CSE001')
        self.assertIn(1, response.data['recorded_periods'])

    def test_history_api_returns_recorded_sessions_with_deterministic_stats(self):
        """History API returns recorded sessions list with percentage and counts"""
        self.client.force_authenticate(user=self.faculty_user)
        session = AttendanceSession.objects.create(
            faculty=self.faculty_user, section=self.section, subject=self.subject,
            session_date=date.today(), period_number=1, topic_covered='Relational Models'
        )
        AttendanceRecord.objects.create(session=session, student=self.student1, status=AttendanceStatus.PRESENT)

        response = self.client.get(f"/api/attendance/history/?section_id={self.section.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['attendance_percentage'], 100.0)
        self.assertEqual(results[0]['total_students'], 1)
        self.assertEqual(results[0]['present_count'], 1)

    def test_session_detail_endpoint_returns_full_student_records(self):
        """Detail endpoint returns session information with all student attendance records"""
        self.client.force_authenticate(user=self.faculty_user)
        session = AttendanceSession.objects.create(
            faculty=self.faculty_user, section=self.section, subject=self.subject,
            session_date=date.today(), period_number=1
        )
        rec = AttendanceRecord.objects.create(session=session, student=self.student1, status=AttendanceStatus.PRESENT, remarks='Good participation')

        response = self.client.get(f"/api/attendance/sessions/{session.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], session.id)
        self.assertEqual(len(response.data['records']), 1)
        self.assertEqual(response.data['records'][0]['student_roll'], '24CSE001')
        self.assertEqual(response.data['records'][0]['status'], 'PRESENT')


class AttendanceCalculationEngineTests(TestCase):
    """
    Dedicated test suite for the Attendance Calculation Engine (Phase 5).
    Verifies:
    - Safe numeric/Decimal calculations
    - 0 classes conducted (zero division safe)
    - 100% attendance
    - 0% attendance
    - Partial attendance with exact Decimal rounding (ROUND_HALF_UP)
    - Boundary checking & ValueError triggers
    - Predictive projection metrics (classes needed / can afford to miss)
    - Subject-wise and overall aggregate calculations
    - API endpoints for student summary and section analytics
    """

    def setUp(self):
        self.client = APIClient()
        self.dept = Department.objects.create(code='CSE', name='Computer Science')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE', total_semesters=8)
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.academic_class = AcademicClass.objects.create(program=self.program, academic_year=self.ay, semester=4)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A', academic_class=self.academic_class)

        # Subjects
        self.sub_dbms = Subject.objects.create(department=self.dept, code='CS401', title='Database Systems', semester=4, credits=4, min_attendance_pct=75.0, condonation_min_pct=65.0)
        self.sub_os = Subject.objects.create(department=self.dept, code='CS402', title='Operating Systems', semester=4, credits=4, min_attendance_pct=75.0, condonation_min_pct=65.0)

        # Faculty
        self.faculty_user = User.objects.create_user(username='prof_patel', email='patel@edumerge.ac.in', role=Role.FACULTY, first_name='Sanjay', last_name='Patel')
        self.faculty = Faculty.objects.create(user=self.faculty_user, employee_id='FAC-201', designation='Professor', department=self.dept)
        FacultyAllocation.objects.create(faculty=self.faculty, subject=self.sub_dbms, section=self.section, academic_year=self.ay, is_active=True)
        FacultyAllocation.objects.create(faculty=self.faculty, subject=self.sub_os, section=self.section, academic_year=self.ay, is_active=True)

        # Student
        self.student_user = User.objects.create_user(username='24cse001', email='s1@edumerge.ac.in', role=Role.STUDENT, first_name='Amit', last_name='Verma')
        self.student = Student.objects.create(user=self.student_user, roll_number='24CSE001', registration_number='REG001', section=self.section, admission_date=date(2024, 8, 1))

        # Enrollments
        CourseEnrollment.objects.create(student=self.student, subject=self.sub_dbms, section=self.section, academic_year=self.ay)
        CourseEnrollment.objects.create(student=self.student, subject=self.sub_os, section=self.section, academic_year=self.ay)

    # ---------------------------------------------------------
    # 1. Pure Calculation Decimal Arithmetic Tests
    # ---------------------------------------------------------

    def test_zero_classes_conducted_safe_calculation(self):
        """0 classes conducted returns Decimal('0.00') safely without ZeroDivisionError"""
        pct = calculate_attendance_percentage(attended_classes=0, conducted_classes=0)
        self.assertIsInstance(pct, Decimal)
        self.assertEqual(pct, Decimal('0.00'))

    def test_hundred_percent_attendance(self):
        """100% attendance returns Decimal('100.00')"""
        self.assertEqual(calculate_attendance_percentage(1, 1), Decimal('100.00'))
        self.assertEqual(calculate_attendance_percentage(10, 10), Decimal('100.00'))
        self.assertEqual(calculate_attendance_percentage(45, 45), Decimal('100.00'))

    def test_zero_percent_attendance(self):
        """0% attendance returns Decimal('0.00') when classes have been conducted"""
        self.assertEqual(calculate_attendance_percentage(0, 1), Decimal('0.00'))
        self.assertEqual(calculate_attendance_percentage(0, 10), Decimal('0.00'))
        self.assertEqual(calculate_attendance_percentage(0, 50), Decimal('0.00'))

    def test_partial_attendance_and_exact_decimal_rounding(self):
        """Partial attendance uses exact Decimal arithmetic with ROUND_HALF_UP precision"""
        # 1 / 3 = 0.333333... -> 33.33%
        self.assertEqual(calculate_attendance_percentage(1, 3), Decimal('33.33'))

        # 2 / 3 = 0.666666... -> 66.67%
        self.assertEqual(calculate_attendance_percentage(2, 3), Decimal('66.67'))

        # 3 / 4 = 0.750000... -> 75.00%
        self.assertEqual(calculate_attendance_percentage(3, 4), Decimal('75.00'))

        # 7 / 8 = 0.875000... -> 87.50%
        self.assertEqual(calculate_attendance_percentage(7, 8), Decimal('87.50'))

        # 1 / 6 = 0.166666... -> 16.67%
        self.assertEqual(calculate_attendance_percentage(1, 6), Decimal('16.67'))

        # 5 / 6 = 0.833333... -> 83.33%
        self.assertEqual(calculate_attendance_percentage(5, 6), Decimal('83.33'))

        # 1 / 7 = 0.142857... -> 14.29%
        self.assertEqual(calculate_attendance_percentage(1, 7), Decimal('14.29'))

        # 29 / 33 = 0.878787... -> 87.88%
        self.assertEqual(calculate_attendance_percentage(29, 33), Decimal('87.88'))

    def test_invalid_parameters_raise_value_error(self):
        """Negative counts or attended > conducted raise ValueError"""
        with self.assertRaises(ValueError):
            calculate_attendance_percentage(attended_classes=-1, conducted_classes=5)

        with self.assertRaises(ValueError):
            calculate_attendance_percentage(attended_classes=5, conducted_classes=-1)

        with self.assertRaises(ValueError):
            calculate_attendance_percentage(attended_classes=6, conducted_classes=5)

    def test_classes_needed_for_target_projection(self):
        """Predicts exact consecutive classes needed to cross target attendance threshold"""
        # Attended 5 of 10 (50%). Target: 75%.
        # (5 + x) / (10 + x) >= 0.75 -> 5 + x >= 7.5 + 0.75x -> 0.25x >= 2.5 -> x >= 10 classes
        needed = calculate_classes_needed_for_target(attended=5, conducted=10, target_pct=Decimal('75.00'))
        self.assertEqual(needed, 10)
        # Verify: (5 + 10) / (10 + 10) = 15 / 20 = 75.0%
        self.assertEqual(calculate_attendance_percentage(5 + needed, 10 + needed), Decimal('75.00'))

        # If already at 80% (8 of 10), 0 needed
        self.assertEqual(calculate_classes_needed_for_target(8, 10, Decimal('75.00')), 0)

    def test_classes_can_afford_to_miss_projection(self):
        """Predicts safe buffer classes student can afford to miss without dropping below target"""
        # Attended 30 of 30 (100%). Target: 75%.
        # 30 / (30 + y) >= 0.75 -> 30 >= 22.5 + 0.75y -> 7.5 >= 0.75y -> y <= 10 classes
        buffer_classes = calculate_classes_can_afford_to_miss(attended=30, conducted=30, target_pct=Decimal('75.00'))
        self.assertEqual(buffer_classes, 10)
        # Verify: 30 / (30 + 10) = 30 / 40 = 75.0%
        self.assertEqual(calculate_attendance_percentage(30, 30 + buffer_classes), Decimal('75.00'))

        # Attended 8 of 10 (80%). Target: 75%.
        # 8 / (10 + y) >= 0.75 -> 8 >= 7.5 + 0.75y -> 0.5 >= 0.75y -> y <= 0.666 -> 0 classes
        self.assertEqual(calculate_classes_can_afford_to_miss(8, 10, Decimal('75.00')), 0)

    # ---------------------------------------------------------
    # 2. Database Integration Service Tests
    # ---------------------------------------------------------

    def test_service_zero_classes_conducted_in_subject(self):
        """Service returns safe 0.00% and NO_DATA status when no sessions have been conducted"""
        stats = AttendanceCalculationService.calculate_student_subject_attendance(
            student=self.student,
            subject=self.sub_dbms
        )
        self.assertEqual(stats['classes_conducted'], 0)
        self.assertEqual(stats['classes_attended'], 0)
        self.assertEqual(stats['classes_missed'], 0)
        self.assertEqual(stats['attendance_percentage'], 0.0)
        self.assertEqual(stats['status'], AttendanceStatusCategory.NO_DATA)

    def test_service_100_percent_attendance_in_subject(self):
        """Service calculates 100% attendance and ELIGIBLE status"""
        for period in range(1, 5):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=period), period_number=period
            )
            AttendanceRecord.objects.create(session=sess, student=self.student, status=AttendanceStatus.PRESENT)

        stats = AttendanceCalculationService.calculate_student_subject_attendance(
            student=self.student,
            subject=self.sub_dbms
        )
        self.assertEqual(stats['classes_conducted'], 4)
        self.assertEqual(stats['classes_attended'], 4)
        self.assertEqual(stats['classes_missed'], 0)
        self.assertEqual(stats['attendance_percentage'], 100.0)
        self.assertEqual(stats['status'], AttendanceStatusCategory.ELIGIBLE)
        self.assertTrue(stats['is_eligible'])

    def test_service_0_percent_attendance_in_subject(self):
        """Service calculates 0% attendance and CRITICAL shortage status"""
        for period in range(1, 5):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=period), period_number=period
            )
            AttendanceRecord.objects.create(session=sess, student=self.student, status=AttendanceStatus.ABSENT)

        stats = AttendanceCalculationService.calculate_student_subject_attendance(
            student=self.student,
            subject=self.sub_dbms
        )
        self.assertEqual(stats['classes_conducted'], 4)
        self.assertEqual(stats['classes_attended'], 0)
        self.assertEqual(stats['classes_missed'], 4)
        self.assertEqual(stats['attendance_percentage'], 0.0)
        self.assertEqual(stats['status'], AttendanceStatusCategory.CRITICAL_SHORTAGE)
        self.assertTrue(stats['is_critical'])

    def test_service_partial_attendance_and_authorized_leaves(self):
        """Service counts Present, Late, and authorized On-Duty/Medical towards effective attendance"""
        statuses = [
            AttendanceStatus.PRESENT,
            AttendanceStatus.LATE,
            AttendanceStatus.ON_DUTY,
            AttendanceStatus.ABSENT,
        ]
        for idx, st in enumerate(statuses, start=1):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=idx), period_number=idx
            )
            AttendanceRecord.objects.create(session=sess, student=self.student, status=st)

        # 4 conducted: 1 Present + 1 Late + 1 OnDuty = 3 attended, 1 Absent = 1 missed -> 75.0%
        stats = AttendanceCalculationService.calculate_student_subject_attendance(
            student=self.student,
            subject=self.sub_dbms
        )
        self.assertEqual(stats['classes_conducted'], 4)
        self.assertEqual(stats['classes_attended'], 3)
        self.assertEqual(stats['classes_missed'], 1)
        self.assertEqual(stats['attendance_percentage'], 75.0)
        self.assertEqual(stats['status'], AttendanceStatusCategory.ELIGIBLE)

    def test_service_student_overall_aggregate_calculation(self):
        """Calculates aggregate metrics across all enrolled subjects for student"""
        # Subject 1 (DBMS): 4 conducted, 4 attended -> 100%
        for period in range(1, 5):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=period), period_number=period
            )
            AttendanceRecord.objects.create(session=sess, student=self.student, status=AttendanceStatus.PRESENT)

        # Subject 2 (OS): 4 conducted, 2 attended, 2 absent -> 50%
        for period in range(1, 5):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_os,
                session_date=date.today() - timedelta(days=period), period_number=period
            )
            st = AttendanceStatus.PRESENT if period <= 2 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student, status=st)

        # Overall: (4 + 2) / (4 + 4) = 6 / 8 = 75.00%
        overall = AttendanceCalculationService.calculate_student_overall_attendance(self.student)
        self.assertEqual(overall['total_conducted'], 8)
        self.assertEqual(overall['total_attended'], 6)
        self.assertEqual(overall['total_missed'], 2)
        self.assertEqual(overall['overall_percentage'], 75.0)
        self.assertEqual(overall['overall_status'], AttendanceStatusCategory.ELIGIBLE)
        self.assertEqual(overall['subject_stats']['eligible_subjects_count'], 1)  # DBMS (100%)
        self.assertEqual(overall['subject_stats']['critical_shortage_subjects_count'], 1)  # OS (50%)

    # ---------------------------------------------------------
    # 3. API Endpoints Integration Tests
    # ---------------------------------------------------------

    def test_student_my_summary_api_endpoint(self):
        """Student can view their live calculated attendance summary"""
        self.client.force_authenticate(user=self.student_user)

        # Create 1 session in DBMS with PRESENT record
        sess = AttendanceSession.objects.create(
            faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
            session_date=date.today(), period_number=1
        )
        AttendanceRecord.objects.create(session=sess, student=self.student, status=AttendanceStatus.PRESENT)

        response = self.client.get('/api/attendance/student/my-summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['roll_number'], '24CSE001')
        self.assertEqual(response.data['total_conducted'], 1)
        self.assertEqual(response.data['total_attended'], 1)
        self.assertEqual(response.data['overall_percentage'], 100.0)

    def test_section_attendance_analytics_api_endpoint(self):
        """Faculty can inspect class-wide attendance analytics and distribution"""
        self.client.force_authenticate(user=self.faculty_user)

        sess = AttendanceSession.objects.create(
            faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
            session_date=date.today(), period_number=1
        )
        AttendanceRecord.objects.create(session=sess, student=self.student, status=AttendanceStatus.PRESENT)

        response = self.client.get(f'/api/attendance/analytics/section/{self.section.id}/?subject_id={self.sub_dbms.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['section_id'], self.section.id)
        self.assertEqual(response.data['class_average_percentage'], 100.0)
        self.assertEqual(response.data['distribution']['eligible_above_75'], 1)


class LowAttendanceDetectionTests(TestCase):
    """
    Phase 6: Comprehensive Automated Tests for Low Attendance Detection.
    Requirements:
    1. Configurable attendance threshold with default of 75%.
    2. Student low-attendance status (overall).
    3. Subject low-attendance status.
    4. Low-attendance student list.
    5. Admin report.
    6. Faculty report.
    7. Student warning.
    8. Deterministic boundary tests:
       - 74.99% -> is_low_attendance is True
       - 75%    -> is_low_attendance is False
       - 75.01% -> is_low_attendance is False
       - 0%     -> is_low_attendance is True
       - 100%   -> is_low_attendance is False
    """

    def setUp(self):
        self.client = APIClient()

        # Institutional Academic Hierarchy
        self.dept = Department.objects.create(code='CSE', name='Computer Science and Engineering')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE', total_semesters=8)
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.academic_class = AcademicClass.objects.create(program=self.program, academic_year=self.ay, semester=4)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A', academic_class=self.academic_class)

        # Subjects
        self.sub_dbms = Subject.objects.create(department=self.dept, code='CS401', title='Database Management Systems', semester=4, credits=4)
        self.sub_os = Subject.objects.create(department=self.dept, code='CS402', title='Operating Systems', semester=4, credits=4)

        # Admin User
        self.admin_user = User.objects.create_user(
            username='admin_dean', email='dean@edumerge.ac.in', role=Role.ADMIN, first_name='Dr. Dean', last_name='Administrator'
        )

        # Faculty User & Allocation
        self.faculty_user = User.objects.create_user(
            username='prof_anand', email='anand@edumerge.ac.in', role=Role.FACULTY, first_name='Anand', last_name='Kumar'
        )
        self.faculty = Faculty.objects.create(
            user=self.faculty_user, employee_id='FAC-401', designation='Associate Professor', department=self.dept
        )
        self.allocation = FacultyAllocation.objects.create(
            faculty=self.faculty, subject=self.sub_dbms, section=self.section, academic_year=self.ay, is_active=True
        )

        # Students
        self.student_user1 = User.objects.create_user(
            username='24cse001', email='student1@edumerge.ac.in', role=Role.STUDENT, first_name='Aarav', last_name='Patel'
        )
        self.student1 = Student.objects.create(
            user=self.student_user1, roll_number='24CSE001', registration_number='REG001', section=self.section, admission_date=date(2024, 8, 1)
        )
        CourseEnrollment.objects.create(student=self.student1, subject=self.sub_dbms, section=self.section, academic_year=self.ay)
        CourseEnrollment.objects.create(student=self.student1, subject=self.sub_os, section=self.section, academic_year=self.ay)

        self.student_user2 = User.objects.create_user(
            username='24cse002', email='student2@edumerge.ac.in', role=Role.STUDENT, first_name='Diya', last_name='Sharma'
        )
        self.student2 = Student.objects.create(
            user=self.student_user2, roll_number='24CSE002', registration_number='REG002', section=self.section, admission_date=date(2024, 8, 1)
        )
        CourseEnrollment.objects.create(student=self.student2, subject=self.sub_dbms, section=self.section, academic_year=self.ay)
        CourseEnrollment.objects.create(student=self.student2, subject=self.sub_os, section=self.section, academic_year=self.ay)


    # -------------------------------------------------------------------------
    # 1. Deterministic Boundary Tests (Mandatory Explicit Specifications)
    # -------------------------------------------------------------------------

    def test_boundary_74_99_percent_is_low_attendance(self):
        """
        Boundary test: 74.99% is strictly below the 75.00% threshold.
        MUST evaluate is_low_attendance == True.
        """
        val = Decimal('74.99')
        threshold = Decimal('75.00')
        self.assertTrue(is_low_attendance(val, threshold))
        # Float representation also evaluates deterministically
        self.assertTrue(is_low_attendance(74.99, 75.0))

    def test_boundary_75_00_percent_is_not_low_attendance(self):
        """
        Boundary test: Exactly 75.00% satisfies the statutory requirement.
        MUST evaluate is_low_attendance == False.
        """
        val = Decimal('75.00')
        threshold = Decimal('75.00')
        self.assertFalse(is_low_attendance(val, threshold))
        self.assertFalse(is_low_attendance(75.0, 75.0))

    def test_boundary_75_01_percent_is_not_low_attendance(self):
        """
        Boundary test: 75.01% is strictly above 75.00%.
        MUST evaluate is_low_attendance == False.
        """
        val = Decimal('75.01')
        threshold = Decimal('75.00')
        self.assertFalse(is_low_attendance(val, threshold))
        self.assertFalse(is_low_attendance(75.01, 75.0))

    def test_boundary_0_percent_is_low_attendance(self):
        """
        Boundary test: 0.00% is a critical attendance shortage.
        MUST evaluate is_low_attendance == True.
        """
        val = Decimal('0.00')
        threshold = Decimal('75.00')
        self.assertTrue(is_low_attendance(val, threshold))
        self.assertTrue(is_low_attendance(0, 75))

    def test_boundary_100_percent_is_not_low_attendance(self):
        """
        Boundary test: 100.00% is perfect compliance.
        MUST evaluate is_low_attendance == False.
        """
        val = Decimal('100.00')
        threshold = Decimal('75.00')
        self.assertFalse(is_low_attendance(val, threshold))
        self.assertFalse(is_low_attendance(100, 75))

    # -------------------------------------------------------------------------
    # 2. Configurable Threshold Tests
    # -------------------------------------------------------------------------

    def test_default_threshold_is_75_percent(self):
        """Institutional policy defaults to 75.00% statutory threshold."""
        policy = AttendancePolicy.get_active_policy()
        self.assertEqual(policy.default_threshold, Decimal('75.00'))
        self.assertEqual(policy.condonation_threshold, Decimal('65.00'))
        self.assertEqual(get_effective_threshold(), Decimal('75.00'))

    def test_configurable_threshold_updates_low_attendance_evaluation(self):
        """
        Updating threshold to 80.00% causes 76.00% to trigger low-attendance status,
        while 80.00% is compliant.
        """
        policy = AttendancePolicy.get_active_policy()
        policy.default_threshold = Decimal('80.00')
        policy.save()

        self.assertEqual(get_effective_threshold(), Decimal('80.00'))

        # 76.00% is compliant under 75% threshold, but LOW under 80% threshold
        self.assertTrue(is_low_attendance(Decimal('76.00'), get_effective_threshold()))
        # 80.00% is compliant under 80% threshold
        self.assertFalse(is_low_attendance(Decimal('80.00'), get_effective_threshold()))
        # 80.01% is compliant under 80% threshold
        self.assertFalse(is_low_attendance(Decimal('80.01'), get_effective_threshold()))

        # Reset back to 75.00% for subsequent tests
        policy.default_threshold = Decimal('75.00')
        policy.save()

    def test_custom_threshold_override_in_service(self):
        """Services allow custom threshold override via explicit parameter."""
        custom_thresh = Decimal('60.00')
        self.assertFalse(is_low_attendance(Decimal('65.00'), threshold=custom_thresh))
        self.assertTrue(is_low_attendance(Decimal('59.99'), threshold=custom_thresh))

    # -------------------------------------------------------------------------
    # 3. Student & Subject Low-Attendance Status Evaluation
    # -------------------------------------------------------------------------

    def test_student_and_subject_low_attendance_detection(self):
        """
        Evaluates subject-level and overall low attendance flags with realistic session records.
        Student 1:
        - DBMS: 10 classes, 7 attended -> 70.00% (< 75.00% -> is_low_attendance = True, deficit = 5.00%)
        - OS:   10 classes, 9 attended -> 90.00% (>= 75.00% -> is_low_attendance = False, deficit = 0.00%)
        - Overall: 20 classes, 16 attended -> 80.00% (>= 75.00% -> is_low_attendance = False)
        """
        # Create 10 DBMS sessions: 7 Present, 3 Absent
        for i in range(1, 11):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=20 - i), period_number=1
            )
            st = AttendanceStatus.PRESENT if i <= 7 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student1, status=st)

        # Create 10 OS sessions: 9 Present, 1 Absent
        for i in range(1, 11):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_os,
                session_date=date.today() - timedelta(days=20 - i), period_number=2
            )
            st = AttendanceStatus.PRESENT if i <= 9 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student1, status=st)

        # Subject 1 (DBMS) verification
        sub1_stat = AttendanceCalculationService.calculate_student_subject_attendance(
            student=self.student1, subject=self.sub_dbms
        )
        self.assertEqual(sub1_stat['attendance_percentage'], 70.0)
        self.assertTrue(sub1_stat['is_low_attendance'])
        self.assertEqual(sub1_stat['deficit_percentage'], 5.0)
        # Recovery calculation: (7 + x) / (10 + x) >= 0.75 -> x >= 2
        self.assertEqual(sub1_stat['classes_needed_for_75'], 2)

        # Subject 2 (OS) verification
        sub2_stat = AttendanceCalculationService.calculate_student_subject_attendance(
            student=self.student1, subject=self.sub_os
        )
        self.assertEqual(sub2_stat['attendance_percentage'], 90.0)
        self.assertFalse(sub2_stat['is_low_attendance'])
        self.assertEqual(sub2_stat['deficit_percentage'], 0.0)
        self.assertEqual(sub2_stat['classes_needed_for_75'], 0)

        # Student Overall verification: 16/20 = 80.00%
        overall = AttendanceCalculationService.calculate_student_overall_attendance(self.student1)
        self.assertEqual(overall['total_conducted'], 20)
        self.assertEqual(overall['total_attended'], 16)
        self.assertEqual(overall['overall_percentage'], 80.0)
        self.assertFalse(overall['is_low_attendance'])
        self.assertEqual(overall['subject_stats']['low_attendance_subjects_count'], 1)

    # -------------------------------------------------------------------------
    # 4. Student Warning Generation
    # -------------------------------------------------------------------------

    def test_student_attendance_warning_notice_and_recovery(self):
        """
        Generates individual attendance warning notices with recovery trajectory
        for any subject where attendance is below 75%.
        """
        # Student 1 in DBMS: 10 classes, 6 attended -> 60.00% (< 65% critical floor)
        for i in range(1, 11):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=20 - i), period_number=1
            )
            st = AttendanceStatus.PRESENT if i <= 6 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student1, status=st)

        warnings = AttendanceCalculationService.generate_student_warnings(self.student1)
        self.assertEqual(len(warnings), 1)

        warn = warnings[0]
        self.assertEqual(warn['subject_code'], 'CS401')
        self.assertEqual(warn['current_percentage'], 60.0)
        self.assertEqual(warn['deficit_percentage'], 15.0)
        self.assertEqual(warn['severity'], 'CRITICAL_DEBARMENT')
        self.assertTrue(warn['is_debarment_risk'])
        # Recovery: (6 + x) / (10 + x) >= 0.75 -> 6 + x >= 7.5 + 0.75x -> 0.25x >= 1.5 -> x >= 6
        self.assertEqual(warn['classes_needed_to_recover'], 6)
        self.assertIn('Statutory Warning', warn['warning_message'])

    # -------------------------------------------------------------------------
    # 5. Low Attendance Student List API
    # -------------------------------------------------------------------------

    def test_low_attendance_students_list_api(self):
        """
        API endpoint /api/attendance/low-attendance/students/ lists students
        falling below the statutory threshold.
        """
        self.client.force_authenticate(user=self.admin_user)

        # Student 1: 5 classes, 1 attended -> 20.00%
        for i in range(1, 6):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=10 - i), period_number=1
            )
            st = AttendanceStatus.PRESENT if i == 1 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student1, status=st)

        response = self.client.get('/api/attendance/low-attendance/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['threshold_used'], 75.0)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['students'][0]['roll_number'], '24CSE001')
        self.assertEqual(response.data['students'][0]['overall_percentage'], 20.0)

    # -------------------------------------------------------------------------
    # 6. Admin Low-Attendance Report API
    # -------------------------------------------------------------------------

    def test_admin_low_attendance_report_api(self):
        """
        Admin report endpoint /api/attendance/reports/admin/ provides
        institutional metrics, departmental breakdown, and critical students.
        """
        self.client.force_authenticate(user=self.admin_user)

        # Student 1: 10 classes, 4 attended -> 40.00%
        for i in range(1, 11):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=15 - i), period_number=1
            )
            st = AttendanceStatus.PRESENT if i <= 4 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student1, status=st)

        response = self.client.get('/api/attendance/reports/admin/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['threshold_used'], 75.0)
        self.assertIn('institutional_at_risk_percentage', response.data)
        self.assertIn('departments', response.data)
        self.assertIn('top_critical_students', response.data)

        # Non-admin access must be rejected with 403 Forbidden
        self.client.force_authenticate(user=self.student_user1)
        resp_forbidden = self.client.get('/api/attendance/reports/admin/')
        self.assertEqual(resp_forbidden.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 7. Faculty Low-Attendance Report API
    # -------------------------------------------------------------------------

    def test_faculty_low_attendance_report_api(self):
        """
        Faculty report endpoint /api/attendance/reports/faculty/ scopes results
        to sections allocated to the faculty member.
        """
        self.client.force_authenticate(user=self.faculty_user)

        # Create session and record for Student 1 (30% attendance)
        for i in range(1, 11):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=12 - i), period_number=1
            )
            st = AttendanceStatus.PRESENT if i <= 3 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student1, status=st)

        response = self.client.get('/api/attendance/reports/faculty/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['threshold_used'], 75.0)
        self.assertIn('sections', response.data)
        self.assertIn('at_risk_students', response.data)
        self.assertTrue(len(response.data['at_risk_students']) >= 1)

    # -------------------------------------------------------------------------
    # 8. Student Warnings API
    # -------------------------------------------------------------------------

    def test_student_attendance_warnings_api(self):
        """
        Student warnings endpoint /api/attendance/student/warnings/ allows
        logged-in student to retrieve their own warning notices.
        """
        self.client.force_authenticate(user=self.student_user1)

        # Student 1: 10 classes, 5 attended -> 50.00% (< 75%)
        for i in range(1, 11):
            sess = AttendanceSession.objects.create(
                faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
                session_date=date.today() - timedelta(days=12 - i), period_number=1
            )
            st = AttendanceStatus.PRESENT if i <= 5 else AttendanceStatus.ABSENT
            AttendanceRecord.objects.create(session=sess, student=self.student1, status=st)

        response = self.client.get('/api/attendance/student/warnings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['roll_number'], '24CSE001')
        self.assertTrue(response.data['has_active_warnings'])
        self.assertEqual(response.data['warnings_count'], 1)
        self.assertEqual(response.data['warnings'][0]['subject_code'], 'CS401')
        self.assertEqual(response.data['warnings'][0]['classes_needed_to_recover'], 10)

    # -------------------------------------------------------------------------
    # 9. Attendance Policy Configuration API
    # -------------------------------------------------------------------------

    def test_attendance_policy_config_api(self):
        """
        Policy config endpoint /api/attendance/policy/ allows Admin to inspect
        and modify threshold settings, and rejects unauthorized modifications.
        """
        # GET by authenticated user
        self.client.force_authenticate(user=self.student_user1)
        response = self.client.get('/api/attendance/policy/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['default_threshold'], 75.0)

        # PUT by Student should fail with 403 Forbidden
        put_resp = self.client.put('/api/attendance/policy/', {'default_threshold': 80.0}, format='json')
        self.assertEqual(put_resp.status_code, status.HTTP_403_FORBIDDEN)

        # PUT by Admin succeeds
        self.client.force_authenticate(user=self.admin_user)
        put_resp_admin = self.client.put(
            '/api/attendance/policy/',
            {'default_threshold': 80.0, 'condonation_threshold': 70.0},
            format='json'
        )
        self.assertEqual(put_resp_admin.status_code, status.HTTP_200_OK)
        self.assertEqual(put_resp_admin.data['default_threshold'], 80.0)
        self.assertEqual(put_resp_admin.data['condonation_threshold'], 70.0)

        # Restore default for test isolation
        self.client.put(
            '/api/attendance/policy/',
            {'default_threshold': 75.0, 'condonation_threshold': 65.0},
            format='json'
        )


class AttendanceCorrectionWorkflowTests(TestCase):
    """
    Phase 7: Comprehensive Automated Tests for Attendance Correction Workflow.
    Requirements:
    1. Correction request.
    2. Original attendance status.
    3. Requested status.
    4. Reason.
    5. Requester.
    6. Timestamp.
    7. Pending status.
    8. Approval.
    9. Rejection.
    10. Audit history.
    - Do NOT silently overwrite historical attendance.
    - Only authorized users can approve corrections.
    """

    def setUp(self):
        self.client = APIClient()

        # Department, Program, Academic Year, Class, Section
        self.dept = Department.objects.create(code='CSE', name='Computer Science and Engineering')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE', total_semesters=8)
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.academic_class = AcademicClass.objects.create(program=self.program, academic_year=self.ay, semester=4)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A', academic_class=self.academic_class)

        # Subject
        self.subject = Subject.objects.create(department=self.dept, code='CS401', title='Database Systems', semester=4, credits=4)

        # Admin
        self.admin_user = User.objects.create_user(
            username='admin_dean', email='dean@edumerge.ac.in', role=Role.ADMIN, first_name='Dean', last_name='Academic'
        )

        # Authorized Faculty (Course Instructor)
        self.faculty_user = User.objects.create_user(
            username='fac_patel', email='patel@edumerge.ac.in', role=Role.FACULTY, first_name='Sanjay', last_name='Patel'
        )
        self.faculty = Faculty.objects.create(
            user=self.faculty_user, employee_id='FAC-501', designation='Professor', department=self.dept
        )
        self.allocation = FacultyAllocation.objects.create(
            faculty=self.faculty, subject=self.subject, section=self.section, academic_year=self.ay, is_active=True
        )

        # Unrelated Faculty (ECE Department - not allocated to this section/subject)
        self.dept_ece = Department.objects.create(code='ECE', name='Electronics and Communication')
        self.unrelated_faculty_user = User.objects.create_user(
            username='fac_sharma', email='sharma@edumerge.ac.in', role=Role.FACULTY, first_name='Vikram', last_name='Sharma'
        )
        self.unrelated_faculty = Faculty.objects.create(
            user=self.unrelated_faculty_user, employee_id='FAC-999', designation='Assistant Professor', department=self.dept_ece
        )

        # Students
        self.student_user1 = User.objects.create_user(
            username='24cse001', email='s1@edumerge.ac.in', role=Role.STUDENT, first_name='Rahul', last_name='Verma'
        )
        self.student1 = Student.objects.create(
            user=self.student_user1, roll_number='24CSE001', registration_number='REG001', section=self.section, admission_date=date(2024, 8, 1)
        )
        CourseEnrollment.objects.create(student=self.student1, subject=self.subject, section=self.section, academic_year=self.ay)

        self.student_user2 = User.objects.create_user(
            username='24cse002', email='s2@edumerge.ac.in', role=Role.STUDENT, first_name='Ananya', last_name='Deshmukh'
        )
        self.student2 = Student.objects.create(
            user=self.student_user2, roll_number='24CSE002', registration_number='REG002', section=self.section, admission_date=date(2024, 8, 1)
        )
        CourseEnrollment.objects.create(student=self.student2, subject=self.subject, section=self.section, academic_year=self.ay)

        # Initial Recorded Attendance Session
        self.session = AttendanceSession.objects.create(
            faculty=self.faculty_user,
            section=self.section,
            subject=self.subject,
            session_date=date.today() - timedelta(days=2),
            period_number=1,
            topic_covered='Relational Algebra and Calculus'
        )
        # Student 1 is marked ABSENT
        self.record1 = AttendanceRecord.objects.create(
            session=self.session, student=self.student1, status=AttendanceStatus.ABSENT
        )
        # Student 2 is marked PRESENT
        self.record2 = AttendanceRecord.objects.create(
            session=self.session, student=self.student2, status=AttendanceStatus.PRESENT
        )

    # -------------------------------------------------------------------------
    # 1. Correction Request Tests
    # -------------------------------------------------------------------------

    def test_student_can_submit_correction_request(self):
        """
        Student submits a correction request for their own marked absence.
        Verifies:
        - Original attendance status auto-captured ('ABSENT')
        - Requested status set ('MEDICAL_LEAVE')
        - Reason captured
        - Requester set to authenticated student
        - Timestamp recorded
        - Status is PENDING
        """
        self.client.force_authenticate(user=self.student_user1)
        payload = {
            'record_id': self.record1.id,
            'requested_status': AttendanceStatus.MEDICAL_LEAVE,
            'reason': 'Hospitalized due to acute gastroenteritis at Apollo Hospital.',
            'document_url': 'https://edumerge.ac.in/docs/medical_cert_24cse001.pdf'
        }
        response = self.client.post('/api/attendance/corrections/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        corr_data = response.data['correction']
        self.assertEqual(corr_data['record'], self.record1.id)
        self.assertEqual(corr_data['old_status'], AttendanceStatus.ABSENT)
        self.assertEqual(corr_data['requested_status'], AttendanceStatus.MEDICAL_LEAVE)
        self.assertEqual(corr_data['reason'], payload['reason'])
        self.assertEqual(corr_data['document_url'], payload['document_url'])
        self.assertEqual(corr_data['status'], CorrectionStatus.PENDING)
        self.assertEqual(corr_data['requested_by'], self.student_user1.id)
        self.assertIsNotNone(corr_data['created_at'])
        self.assertIsNone(corr_data['resolved_at'])

    def test_student_cannot_submit_correction_for_another_student(self):
        """Student 2 is forbidden from requesting correction for Student 1's record."""
        self.client.force_authenticate(user=self.student_user2)
        payload = {
            'record_id': self.record1.id,
            'requested_status': AttendanceStatus.PRESENT,
            'reason': 'Impersonated request attempt on peer attendance record.'
        }
        response = self.client.post('/api/attendance/corrections/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_request_identical_status(self):
        """Requesting the same status as currently marked is rejected."""
        self.client.force_authenticate(user=self.student_user1)
        payload = {
            'record_id': self.record1.id,
            'requested_status': AttendanceStatus.ABSENT,  # already ABSENT
            'reason': 'Redundant request for identical status.'
        }
        response = self.client.post('/api/attendance/corrections/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_duplicate_pending_correction(self):
        """Submitting a second correction request while one is already pending is rejected."""
        self.client.force_authenticate(user=self.student_user1)
        AttendanceCorrection.objects.create(
            record=self.record1,
            requested_by=self.student_user1,
            old_status=AttendanceStatus.ABSENT,
            requested_status=AttendanceStatus.MEDICAL_LEAVE,
            reason='Initial pending request for viral fever.',
            status=CorrectionStatus.PENDING
        )
        payload = {
            'record_id': self.record1.id,
            'requested_status': AttendanceStatus.ON_DUTY,
            'reason': 'Secondary request while first is still pending.'
        }
        response = self.client.post('/api/attendance/corrections/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 2. Approval Workflow Tests (Do NOT silently overwrite attendance!)
    # -------------------------------------------------------------------------

    def test_authorized_faculty_can_approve_correction_with_audit_trail(self):
        """
        Authorized faculty approves a correction request.
        Guarantees:
        1. Historical attendance record is updated to requested status.
        2. It is NOT silently overwritten: an immutable AttendanceAuditLog entry is created.
        3. Audit log captures old_status, new_status, actor, reason, timestamp.
        4. Correction status transitions to APPROVED.
        """
        correction = AttendanceCorrection.objects.create(
            record=self.record1,
            requested_by=self.student_user1,
            old_status=AttendanceStatus.ABSENT,
            requested_status=AttendanceStatus.MEDICAL_LEAVE,
            reason='Severe typhoid with hospital admission slip attached.',
            status=CorrectionStatus.PENDING
        )

        self.client.force_authenticate(user=self.faculty_user)
        approve_payload = {
            'review_notes': 'Verified with Apollo Hospital discharge summary. Leave approved.'
        }
        response = self.client.post(f'/api/attendance/corrections/{correction.id}/approve/', approve_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 1. Verify correction record
        correction.refresh_from_db()
        self.assertEqual(correction.status, CorrectionStatus.APPROVED)
        self.assertEqual(correction.reviewed_by, self.faculty_user)
        self.assertEqual(correction.review_notes, approve_payload['review_notes'])
        self.assertIsNotNone(correction.resolved_at)

        # 2. Verify attendance record was updated
        self.record1.refresh_from_db()
        self.assertEqual(self.record1.status, AttendanceStatus.MEDICAL_LEAVE)

        # 3. Verify immutable audit log was created (NOT silently overwritten)
        audit_logs = AttendanceAuditLog.objects.filter(record=self.record1)
        self.assertEqual(audit_logs.count(), 1)
        audit = audit_logs.first()
        self.assertEqual(audit.action, AuditAction.CORRECTION_APPROVED)
        self.assertEqual(audit.previous_status, AttendanceStatus.ABSENT)
        self.assertEqual(audit.new_status, AttendanceStatus.MEDICAL_LEAVE)
        self.assertEqual(audit.changed_by, self.faculty_user)
        self.assertIn('Verified with Apollo Hospital', audit.reason)
        self.assertIsNotNone(audit.timestamp)

    # -------------------------------------------------------------------------
    # 3. Rejection Workflow Tests
    # -------------------------------------------------------------------------

    def test_authorized_faculty_can_reject_correction(self):
        """
        Authorized faculty rejects an invalid correction request.
        Guarantees:
        1. Attendance record status remains strictly UNALTERED ('ABSENT').
        2. Correction status transitions to REJECTED.
        3. An immutable audit log entry is created capturing rejection rationale.
        """
        correction = AttendanceCorrection.objects.create(
            record=self.record1,
            requested_by=self.student_user1,
            old_status=AttendanceStatus.ABSENT,
            requested_status=AttendanceStatus.ON_DUTY,
            reason='Attended regional hackathon without prior HoD permission slip.',
            status=CorrectionStatus.PENDING
        )

        self.client.force_authenticate(user=self.faculty_user)
        reject_payload = {
            'review_notes': 'Rejected: No prior approval letter from HOD submitted.'
        }
        response = self.client.post(f'/api/attendance/corrections/{correction.id}/reject/', reject_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 1. Verify correction record
        correction.refresh_from_db()
        self.assertEqual(correction.status, CorrectionStatus.REJECTED)
        self.assertEqual(correction.reviewed_by, self.faculty_user)
        self.assertEqual(correction.review_notes, reject_payload['review_notes'])
        self.assertIsNotNone(correction.resolved_at)

        # 2. Verify attendance record is UNCHANGED
        self.record1.refresh_from_db()
        self.assertEqual(self.record1.status, AttendanceStatus.ABSENT)

        # 3. Verify audit log entry was created for rejection
        audit_logs = AttendanceAuditLog.objects.filter(record=self.record1)
        self.assertEqual(audit_logs.count(), 1)
        audit = audit_logs.first()
        self.assertEqual(audit.action, AuditAction.CORRECTION_REJECTED)
        self.assertEqual(audit.previous_status, AttendanceStatus.ABSENT)
        self.assertEqual(audit.new_status, AttendanceStatus.ABSENT)
        self.assertEqual(audit.changed_by, self.faculty_user)
        self.assertIn('No prior approval letter', audit.reason)

    # -------------------------------------------------------------------------
    # 4. Unauthorized Access Tests
    # -------------------------------------------------------------------------

    def test_student_cannot_approve_or_reject_correction(self):
        """Students can NEVER approve or reject attendance corrections."""
        correction = AttendanceCorrection.objects.create(
            record=self.record1,
            requested_by=self.student_user1,
            old_status=AttendanceStatus.ABSENT,
            requested_status=AttendanceStatus.PRESENT,
            reason='Attempted self-approval test.',
            status=CorrectionStatus.PENDING
        )

        # Student 1 attempts to approve their own request
        self.client.force_authenticate(user=self.student_user1)
        resp_approve = self.client.post(f'/api/attendance/corrections/{correction.id}/approve/', {}, format='json')
        self.assertEqual(resp_approve.status_code, status.HTTP_403_FORBIDDEN)

        # Student 2 attempts to reject Student 1's request
        self.client.force_authenticate(user=self.student_user2)
        resp_reject = self.client.post(f'/api/attendance/corrections/{correction.id}/reject/', {}, format='json')
        self.assertEqual(resp_reject.status_code, status.HTTP_403_FORBIDDEN)

        # Verify status remains PENDING and record untouched
        correction.refresh_from_db()
        self.assertEqual(correction.status, CorrectionStatus.PENDING)
        self.record1.refresh_from_db()
        self.assertEqual(self.record1.status, AttendanceStatus.ABSENT)

    def test_unrelated_faculty_cannot_approve_correction(self):
        """Faculty from an unrelated department/class cannot approve corrections."""
        correction = AttendanceCorrection.objects.create(
            record=self.record1,
            requested_by=self.student_user1,
            old_status=AttendanceStatus.ABSENT,
            requested_status=AttendanceStatus.MEDICAL_LEAVE,
            reason='Typhoid fever hospitalization.',
            status=CorrectionStatus.PENDING
        )

        self.client.force_authenticate(user=self.unrelated_faculty_user)
        resp = self.client.post(f'/api/attendance/corrections/{correction.id}/approve/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_approve_any_correction(self):
        """Institutional Administrator has full authority to review and approve corrections."""
        correction = AttendanceCorrection.objects.create(
            record=self.record1,
            requested_by=self.student_user1,
            old_status=AttendanceStatus.ABSENT,
            requested_status=AttendanceStatus.ON_DUTY,
            reason='Represented institution at National Science Congress.',
            status=CorrectionStatus.PENDING
        )

        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.post(
            f'/api/attendance/corrections/{correction.id}/approve/',
            {'review_notes': 'Dean administrative sanction granted.'},
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        correction.refresh_from_db()
        self.assertEqual(correction.status, CorrectionStatus.APPROVED)
        self.assertEqual(correction.reviewed_by, self.admin_user)

        self.record1.refresh_from_db()
        self.assertEqual(self.record1.status, AttendanceStatus.ON_DUTY)

    # -------------------------------------------------------------------------
    # 5. Audit Trail History Verification Tests
    # -------------------------------------------------------------------------

    def test_audit_history_timeline_endpoint(self):
        """
        Record audit history endpoint /api/attendance/records/<id>/audit-logs/
        returns full chronological audit trail with actions and actors.
        """
        # Create audit entry
        AttendanceAuditLog.objects.create(
            record=self.record1,
            action=AuditAction.CORRECTION_APPROVED,
            previous_status=AttendanceStatus.ABSENT,
            new_status=AttendanceStatus.PRESENT,
            changed_by=self.faculty_user,
            reason='Verified attendance was mistakenly marked absent.'
        )

        # Student 1 views their record's audit history
        self.client.force_authenticate(user=self.student_user1)
        resp = self.client.get(f'/api/attendance/records/{self.record1.id}/audit-logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['record_id'], self.record1.id)
        self.assertEqual(resp.data['student_roll'], '24CSE001')
        self.assertEqual(len(resp.data['audit_trail']), 1)
        self.assertEqual(resp.data['audit_trail'][0]['action'], AuditAction.CORRECTION_APPROVED)
        self.assertEqual(resp.data['audit_trail'][0]['changed_by_name'], 'Sanjay Patel')

        # Student 2 cannot view Student 1's record audit history
        self.client.force_authenticate(user=self.student_user2)
        resp_forbid = self.client.get(f'/api/attendance/records/{self.record1.id}/audit-logs/')
        self.assertEqual(resp_forbid.status_code, status.HTTP_403_FORBIDDEN)


class Phase8DashboardsAndReportsTests(TestCase):
    """
    Phase 8: Comprehensive Automated Tests for Dashboards and Reports.
    Requirements:
    1. ADMIN DASHBOARD:
       - Total students
       - Total faculty
       - Departments
       - Overall attendance
       - Low attendance students
       - Attendance by department
       - Attendance trends
    2. FACULTY DASHBOARD:
       - Today's classes
       - Pending attendance
       - Class attendance
       - Low attendance students
    3. STUDENT DASHBOARD:
       - Overall attendance
       - Subject-wise attendance
       - Attendance history
       - Low attendance warnings
    """

    def setUp(self):
        self.client = APIClient()

        # Academic Hierarchy
        self.dept = Department.objects.create(code='CSE', name='Computer Science and Engineering')
        self.dept_ece = Department.objects.create(code='ECE', name='Electronics and Communication')
        self.program = Program.objects.create(department=self.dept, code='BTECH-CSE', name='B.Tech CSE', total_semesters=8)
        self.ay = AcademicYear.objects.create(year_label='2026-2027', start_date=date(2026, 7, 1), end_date=date(2027, 5, 31), is_current=True)
        self.academic_class = AcademicClass.objects.create(program=self.program, academic_year=self.ay, semester=4)
        self.section = Section.objects.create(program=self.program, academic_year=self.ay, semester=4, name='A', academic_class=self.academic_class)

        # Subjects
        self.sub_dbms = Subject.objects.create(department=self.dept, code='CS401', title='Database Systems', semester=4, credits=4)
        self.sub_os = Subject.objects.create(department=self.dept, code='CS402', title='Operating Systems', semester=4, credits=4)

        # Users
        self.admin_user = User.objects.create_user(
            username='admin_dean', email='dean@edumerge.ac.in', role=Role.ADMIN, first_name='Dr. Dean', last_name='Academic'
        )

        self.faculty_user = User.objects.create_user(
            username='prof_anand', email='anand@edumerge.ac.in', role=Role.FACULTY, first_name='Anand', last_name='Kumar'
        )
        self.faculty = Faculty.objects.create(
            user=self.faculty_user, employee_id='FAC-801', designation='Associate Professor', department=self.dept
        )
        self.allocation = FacultyAllocation.objects.create(
            faculty=self.faculty, subject=self.sub_dbms, section=self.section, academic_year=self.ay, is_active=True
        )

        self.student_user = User.objects.create_user(
            username='24cse001', email='student1@edumerge.ac.in', role=Role.STUDENT, first_name='Aarav', last_name='Patel'
        )
        self.student = Student.objects.create(
            user=self.student_user, roll_number='24CSE001', registration_number='REG001', section=self.section, admission_date=date(2024, 8, 1)
        )
        CourseEnrollment.objects.create(student=self.student, subject=self.sub_dbms, section=self.section, academic_year=self.ay)
        CourseEnrollment.objects.create(student=self.student, subject=self.sub_os, section=self.section, academic_year=self.ay)

        # Create Historical Sessions & Records
        # Session 1: DBMS (Present)
        self.sess1 = AttendanceSession.objects.create(
            faculty=self.faculty_user, section=self.section, subject=self.sub_dbms,
            session_date=date.today() - timedelta(days=2), period_number=1, topic_covered='SQL Joins'
        )
        self.rec1 = AttendanceRecord.objects.create(session=self.sess1, student=self.student, status=AttendanceStatus.PRESENT)

        # Session 2: OS (Absent) -> OS is at 0%, DBMS at 100% -> Overall 50%
        self.sess2 = AttendanceSession.objects.create(
            faculty=self.faculty_user, section=self.section, subject=self.sub_os,
            session_date=date.today() - timedelta(days=1), period_number=2, topic_covered='Process Scheduling'
        )
        self.rec2 = AttendanceRecord.objects.create(session=self.sess2, student=self.student, status=AttendanceStatus.ABSENT)

    # -------------------------------------------------------------------------
    # 1. Admin Dashboard Tests
    # -------------------------------------------------------------------------

    def test_admin_dashboard_metrics(self):
        """
        Admin Dashboard returns accurate institutional metrics:
        - Total students
        - Total faculty
        - Departments
        - Overall attendance
        - Low attendance students
        - Attendance by department
        - Attendance trends
        """
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/attendance/dashboard/admin/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['total_students'], 1)
        self.assertEqual(data['total_faculty'], 1)
        self.assertEqual(data['total_departments'], 2)  # CSE, ECE
        self.assertEqual(data['total_sessions'], 2)
        # 1 present out of 2 records = 50.00%
        self.assertEqual(data['overall_attendance_percentage'], 50.0)
        self.assertEqual(data['low_attendance_count'], 1)  # student is at 50% (< 75%)
        self.assertIn('departments', data)
        self.assertTrue(len(data['departments']) >= 1)
        self.assertIn('low_attendance_students', data)
        self.assertTrue(len(data['low_attendance_students']) >= 1)
        self.assertIn('attendance_trends', data)
        self.assertTrue(len(data['attendance_trends']) >= 1)

    def test_admin_dashboard_rbac(self):
        """Non-admin users cannot access the Admin Dashboard endpoint."""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get('/api/attendance/dashboard/admin/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 2. Faculty Dashboard Tests
    # -------------------------------------------------------------------------

    def test_faculty_dashboard_metrics(self):
        """
        Faculty Dashboard returns class and cohort metrics:
        - Today's classes
        - Pending attendance
        - Class attendance
        - Low attendance students
        """
        self.client.force_authenticate(user=self.faculty_user)
        response = self.client.get('/api/attendance/dashboard/faculty/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['faculty_name'], 'Anand Kumar')
        self.assertIn('today_classes', data)
        self.assertEqual(len(data['today_classes']), 1)  # DBMS allocated to Section A
        self.assertEqual(data['today_classes'][0]['subject_code'], 'CS401')
        # Since no session was conducted TODAY, pending_attendance_count must be 1
        self.assertEqual(data['pending_attendance_count'], 1)
        self.assertFalse(data['today_classes'][0]['is_attendance_taken'])

        self.assertIn('class_attendance', data)
        self.assertTrue(len(data['class_attendance']) >= 1)

        self.assertIn('low_attendance_students', data)

    # -------------------------------------------------------------------------
    # 3. Student Dashboard Tests
    # -------------------------------------------------------------------------

    def test_student_dashboard_metrics(self):
        """
        Student Dashboard returns personalized academic metrics:
        - Overall attendance
        - Subject-wise attendance
        - Attendance history
        - Low attendance warnings
        """
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get('/api/attendance/dashboard/student/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        # Profile
        self.assertEqual(data['student']['roll_number'], '24CSE001')
        self.assertEqual(data['student']['department_name'], 'Computer Science and Engineering')

        # Overall attendance: 1 attended / 2 conducted = 50.0%
        self.assertEqual(data['overall_attendance']['total_conducted'], 2)
        self.assertEqual(data['overall_attendance']['total_attended'], 1)
        self.assertEqual(data['overall_attendance']['overall_percentage'], 50.0)
        self.assertTrue(data['overall_attendance']['is_low_attendance'])

        # Subject-wise attendance: 2 subjects
        subs = data['subject_wise_attendance']
        self.assertEqual(len(subs), 2)
        sub_codes = [s['subject_code'] for s in subs]
        self.assertIn('CS401', sub_codes)  # DBMS
        self.assertIn('CS402', sub_codes)  # OS

        # Attendance history: 2 records
        self.assertEqual(len(data['attendance_history']), 2)

        # Low attendance warnings: Student is below 75% in OS (0%)
        warnings = data['low_attendance_warnings']
        self.assertTrue(warnings['has_warnings'])
        self.assertTrue(warnings['warnings_count'] >= 1)
        self.assertEqual(warnings['warnings'][0]['subject_code'], 'CS402')




