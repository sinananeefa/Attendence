from datetime import date
from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User, Role
from academic.models import (
    Department, Program, AcademicYear, Semester, AcademicClass, Section,
    Subject, Student, Faculty, FacultyAllocation, CourseEnrollment,
    TimetableSlot, DayOfWeek
)


class AcademicStructureAndValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 1. Department
        self.dept_cse = Department.objects.create(code='CSE', name='Computer Science and Engineering')
        self.dept_ece = Department.objects.create(code='ECE', name='Electronics and Communication')

        # 2. Program
        self.program_cse = Program.objects.create(
            department=self.dept_cse,
            code='BTECH-CSE',
            name='B.Tech in Computer Science',
            total_semesters=8
        )
        self.program_ece = Program.objects.create(
            department=self.dept_ece,
            code='BTECH-ECE',
            name='B.Tech in Electronics',
            total_semesters=8
        )

        # 3. Academic Year & Semester
        self.ay = AcademicYear.objects.create(
            year_label='2026-2027',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 5, 31),
            is_current=True
        )
        self.sem4 = Semester.objects.create(
            academic_year=self.ay,
            semester_number=4,
            term=Semester.TermChoices.EVEN,
            start_date=date(2027, 1, 5),
            end_date=date(2027, 5, 20)
        )

        # 4. Class & Section
        self.class_cse_s4 = AcademicClass.objects.create(
            program=self.program_cse,
            academic_year=self.ay,
            semester=4
        )
        self.mentor_user = User.objects.create_user(
            username='mentor_cse',
            email='mentor@edumerge.ac.in',
            role=Role.MENTOR,
            first_name='Arun',
            last_name='Kumar'
        )
        self.section_4a = Section.objects.create(
            program=self.program_cse,
            academic_year=self.ay,
            semester=4,
            name='A',
            mentor=self.mentor_user,
            academic_class=self.class_cse_s4
        )
        self.section_4b = Section.objects.create(
            program=self.program_cse,
            academic_year=self.ay,
            semester=4,
            name='B',
            academic_class=self.class_cse_s4
        )

        # 5. Subjects
        self.subject_dbms = Subject.objects.create(
            department=self.dept_cse,
            program=self.program_cse,
            code='CS401',
            title='Database Management Systems',
            credits=4,
            semester=4,
            min_attendance_pct=75.0,
            condonation_min_pct=65.0
        )
        self.subject_os = Subject.objects.create(
            department=self.dept_cse,
            program=self.program_cse,
            code='CS402',
            title='Operating Systems',
            credits=4,
            semester=4,
            min_attendance_pct=75.0,
            condonation_min_pct=65.0
        )
        self.subject_ai_s6 = Subject.objects.create(
            department=self.dept_cse,
            program=self.program_cse,
            code='CS601',
            title='Artificial Intelligence',
            credits=4,
            semester=6,
            min_attendance_pct=75.0,
            condonation_min_pct=65.0
        )

        # 6. Faculty Profile
        self.faculty_user = User.objects.create_user(
            username='fac_priya',
            email='priya@edumerge.ac.in',
            password='Faculty@123',
            role=Role.FACULTY,
            first_name='Priya',
            last_name='Natarajan'
        )
        self.faculty = Faculty.objects.create(
            user=self.faculty_user,
            employee_id='FAC-101',
            designation='Associate Professor',
            department=self.dept_cse
        )

        # 7. Student Profile
        self.student_user = User.objects.create_user(
            username='24cse001',
            email='student1@edumerge.ac.in',
            password='Student@123',
            role=Role.STUDENT,
            first_name='Rahul',
            last_name='Sharma'
        )
        self.student = Student.objects.create(
            user=self.student_user,
            roll_number='24CSE001',
            registration_number='REG-2024-001',
            section=self.section_4a,
            current_semester=4,
            admission_date=date(2024, 8, 1)
        )

        # 8. Admin User
        self.admin_user = User.objects.create_user(
            username='admin_dean',
            email='dean@edumerge.ac.in',
            password='Admin@123',
            role=Role.ADMIN
        )

    # =======================================================
    # 1. STUDENT ENROLLMENT VALIDATION TESTS
    # =======================================================

    def test_student_course_enrollment_success(self):
        enrollment = CourseEnrollment.objects.create(
            student=self.student,
            subject=self.subject_dbms,
            section=self.section_4a,
            academic_year=self.ay
        )
        self.assertEqual(enrollment.student, self.student)
        self.assertEqual(enrollment.subject, self.subject_dbms)

    def test_student_cannot_be_enrolled_twice_in_same_subject(self):
        """A student cannot be enrolled twice in the same subject/academic year"""
        CourseEnrollment.objects.create(
            student=self.student,
            subject=self.subject_dbms,
            section=self.section_4a,
            academic_year=self.ay
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            CourseEnrollment.objects.create(
                student=self.student,
                subject=self.subject_dbms,
                section=self.section_4a,
                academic_year=self.ay
            )

    def test_student_enrollment_section_mismatch_rejected(self):
        """Enrolling a student in Section B when they are enrolled in Section A raises ValidationError"""
        with self.assertRaises(ValidationError):
            CourseEnrollment.objects.create(
                student=self.student,
                subject=self.subject_dbms,
                section=self.section_4b,  # Student belongs to section_4a!
                academic_year=self.ay
            )

    def test_student_enrollment_semester_mismatch_rejected(self):
        """Enrolling a Semester 4 student in a Semester 6 subject raises ValidationError"""
        with self.assertRaises(ValidationError):
            CourseEnrollment.objects.create(
                student=self.student,
                subject=self.subject_ai_s6,  # Semester 6 subject!
                section=self.section_4a,     # Semester 4 section!
                academic_year=self.ay
            )

    # =======================================================
    # 2. FACULTY ASSIGNMENT VALIDATION TESTS
    # =======================================================

    def test_faculty_assignment_success(self):
        alloc = FacultyAllocation.objects.create(
            faculty=self.faculty,
            subject=self.subject_dbms,
            section=self.section_4a,
            academic_year=self.ay
        )
        self.assertEqual(alloc.subject.code, 'CS401')

    def test_faculty_cannot_be_assigned_twice_to_same_subject_section(self):
        """A faculty member cannot be assigned twice to the same subject, section, and year"""
        FacultyAllocation.objects.create(
            faculty=self.faculty,
            subject=self.subject_dbms,
            section=self.section_4a,
            academic_year=self.ay
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            FacultyAllocation.objects.create(
                faculty=self.faculty,
                subject=self.subject_dbms,
                section=self.section_4a,
                academic_year=self.ay
            )

    def test_faculty_assignment_semester_mismatch_rejected(self):
        """Cannot assign a Semester 6 subject (CS601) to a Semester 4 section (4A)"""
        with self.assertRaises(ValidationError):
            FacultyAllocation.objects.create(
                faculty=self.faculty,
                subject=self.subject_ai_s6,  # S6
                section=self.section_4a,     # S4
                academic_year=self.ay
            )

    def test_faculty_assignment_inactive_account_rejected(self):
        """Cannot assign an inactive faculty account to teach classes"""
        self.faculty_user.is_active = False
        self.faculty_user.save()
        with self.assertRaises(ValidationError):
            FacultyAllocation.objects.create(
                faculty=self.faculty,
                subject=self.subject_dbms,
                section=self.section_4a,
                academic_year=self.ay
            )

    # =======================================================
    # 3. SUBJECT ACADEMIC STRUCTURE VALIDATION TESTS
    # =======================================================

    def test_subject_semester_exceeding_program_rejected(self):
        """Subject with semester 10 for an 8-semester program must raise ValidationError"""
        subject = Subject(
            department=self.dept_cse,
            program=self.program_cse,
            code='CS999',
            title='Quantum Computing',
            credits=3,
            semester=10  # Exceeds total_semesters = 8
        )
        with self.assertRaises(ValidationError):
            subject.clean()

    def test_subject_department_program_mismatch_rejected(self):
        """Subject in ECE department cannot have a CSE program without raising ValidationError"""
        subject = Subject(
            department=self.dept_ece,       # Department ECE
            program=self.program_cse,       # Program CSE!
            code='EC999',
            title='Cross Department Subject',
            credits=3,
            semester=4
        )
        with self.assertRaises(ValidationError):
            subject.clean()

    # =======================================================
    # 4. UNAUTHORIZED MODIFICATION RESTRICTION TESTS (APIs)
    # =======================================================

    def test_student_cannot_create_department(self):
        """Student token attempting POST /api/academic/departments/ receives 403 Forbidden"""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post('/api/academic/departments/', {
            'code': 'BIO',
            'name': 'Biotechnology'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_faculty_cannot_create_department(self):
        """Faculty token attempting POST /api/academic/departments/ receives 403 Forbidden"""
        self.client.force_authenticate(user=self.faculty_user)
        response = self.client.post('/api/academic/departments/', {
            'code': 'BIO',
            'name': 'Biotechnology'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_create_subject(self):
        """Student token attempting POST /api/academic/subjects/ receives 403 Forbidden"""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post('/api/academic/subjects/', {
            'department': self.dept_cse.id,
            'code': 'CS499',
            'title': 'Hacking Class',
            'credits': 4,
            'semester': 4
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_department(self):
        """Admin token can create departments with 201 Created"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/academic/departments/', {
            'code': 'BIO',
            'name': 'Biotechnology & Bioinformatics'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'BIO')

    def test_admin_can_create_subject(self):
        """Admin token can create curriculum subjects with 201 Created"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/api/academic/subjects/', {
            'department': self.dept_cse.id,
            'program': self.program_cse.id,
            'code': 'CS480',
            'title': 'Applied Cryptography',
            'credits': 3,
            'semester': 4,
            'min_attendance_pct': 75.0,
            'condonation_min_pct': 65.0
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['code'], 'CS480')
