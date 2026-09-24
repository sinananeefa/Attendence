from datetime import date, time
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User, Role
from academic.models import (
    Department, Program, AcademicYear, Semester, AcademicClass, Section,
    Subject, Student, Faculty, FacultyAllocation, CourseEnrollment,
    TimetableSlot, DayOfWeek
)


class Command(BaseCommand):
    help = "Seeds comprehensive academic structure and course enrollments (Phase 3)"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Phase 3 Academic Structure & Enrollments..."))

        # 1. Departments
        cse, _ = Department.objects.get_or_create(
            code='CSE',
            defaults={'name': 'Computer Science & Engineering', 'description': 'Department of Computing, Systems & AI'}
        )
        ece, _ = Department.objects.get_or_create(
            code='ECE',
            defaults={'name': 'Electronics & Communication', 'description': 'Department of Embedded Systems & VLSI'}
        )
        mech, _ = Department.objects.get_or_create(
            code='MECH',
            defaults={'name': 'Mechanical Engineering', 'description': 'Department of Robotics & Thermal Engineering'}
        )
        it, _ = Department.objects.get_or_create(
            code='IT',
            defaults={'name': 'Information Technology', 'description': 'Department of Information Systems & Cyber Security'}
        )

        # 2. Degree Programs
        btech_cse, _ = Program.objects.get_or_create(
            department=cse,
            code='BTECH-CSE',
            defaults={'name': 'Bachelor of Technology in Computer Science & Engineering', 'total_semesters': 8}
        )
        btech_ece, _ = Program.objects.get_or_create(
            department=ece,
            code='BTECH-ECE',
            defaults={'name': 'Bachelor of Technology in Electronics & Communication', 'total_semesters': 8}
        )
        btech_mech, _ = Program.objects.get_or_create(
            department=mech,
            code='BTECH-MECH',
            defaults={'name': 'Bachelor of Technology in Mechanical Engineering', 'total_semesters': 8}
        )

        # 3. Academic Year
        ay, _ = AcademicYear.objects.get_or_create(
            year_label='2026-2027',
            defaults={'start_date': date(2026, 7, 15), 'end_date': date(2027, 5, 20), 'is_current': True}
        )

        # 4. Semesters
        sem4, _ = Semester.objects.get_or_create(
            academic_year=ay,
            semester_number=4,
            defaults={
                'term': Semester.TermChoices.EVEN,
                'start_date': date(2027, 1, 5),
                'end_date': date(2027, 5, 20),
                'is_active': True
            }
        )
        sem6, _ = Semester.objects.get_or_create(
            academic_year=ay,
            semester_number=6,
            defaults={
                'term': Semester.TermChoices.EVEN,
                'start_date': date(2027, 1, 5),
                'end_date': date(2027, 5, 20),
                'is_active': True
            }
        )

        # 5. Academic Classes (Cohort Groups)
        class_cse_s4, _ = AcademicClass.objects.get_or_create(
            program=btech_cse,
            academic_year=ay,
            semester=4
        )
        class_cse_s6, _ = AcademicClass.objects.get_or_create(
            program=btech_cse,
            academic_year=ay,
            semester=6
        )
        class_ece_s4, _ = AcademicClass.objects.get_or_create(
            program=btech_ece,
            academic_year=ay,
            semester=4
        )

        # 6. Faculty Personnel
        faculty_roster = [
            ('fac_priya', 'Dr. Priya', 'Natarajan', 'FAC-CSE-101', 'Associate Professor', cse),
            ('fac_vikram', 'Prof. Vikram', 'Seth', 'FAC-CSE-102', 'Assistant Professor', cse),
            ('hod_cse', 'Dr. Rajesh', 'Deshmukh', 'FAC-CSE-100', 'Professor & HOD', cse),
            ('mentor_arun', 'Prof. Arun', 'Kumar', 'FAC-CSE-108', 'Assistant Professor & Mentor', cse),
            ('fac_kavita', 'Dr. Kavita', 'Sharma', 'FAC-CSE-112', 'Associate Professor & Mentor', cse),
            ('fac_meenakshi', 'Prof. Meenakshi', 'Sundaram', 'FAC-ECE-101', 'Assistant Professor', ece),
        ]

        # Pre-compute password hashes for ultra-fast seeding
        from django.contrib.auth.hashers import make_password
        fac_hash = make_password('Faculty@123')
        hod_hash = make_password('Hod@123')
        mentor_hash = make_password('Mentor@123')
        stu_hash = make_password('Student@123')

        faculty_profiles = {}
        for username, fname, lname, emp_id, desig, dept in faculty_roster:
            p_hash = hod_hash if 'HOD' in desig else mentor_hash if 'Mentor' in desig else fac_hash
            u, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f"{username}@edumerge.ac.in",
                    'first_name': fname,
                    'last_name': lname,
                    'role': Role.HOD if 'HOD' in desig else Role.MENTOR if 'Mentor' in desig else Role.FACULTY,
                    'department': dept,
                    'password': p_hash
                }
            )

            f, _ = Faculty.objects.get_or_create(
                user=u,
                defaults={'employee_id': emp_id, 'designation': desig, 'department': dept}
            )
            faculty_profiles[username] = f

        # 7. Class Sections with Mentors
        sec_cse_4a, _ = Section.objects.get_or_create(
            program=btech_cse,
            academic_year=ay,
            semester=4,
            name='A',
            defaults={'mentor': faculty_profiles['mentor_arun'].user, 'academic_class': class_cse_s4, 'max_capacity': 60}
        )
        sec_cse_4b, _ = Section.objects.get_or_create(
            program=btech_cse,
            academic_year=ay,
            semester=4,
            name='B',
            defaults={'mentor': faculty_profiles['fac_kavita'].user, 'academic_class': class_cse_s4, 'max_capacity': 60}
        )
        sec_cse_6a, _ = Section.objects.get_or_create(
            program=btech_cse,
            academic_year=ay,
            semester=6,
            name='A',
            defaults={'mentor': faculty_profiles['hod_cse'].user, 'academic_class': class_cse_s6, 'max_capacity': 60}
        )
        sec_ece_4a, _ = Section.objects.get_or_create(
            program=btech_ece,
            academic_year=ay,
            semester=4,
            name='A',
            defaults={'mentor': faculty_profiles['fac_meenakshi'].user, 'academic_class': class_ece_s4, 'max_capacity': 60}
        )

        # 8. Curriculum Subjects
        subjects_spec = [
            # CSE Semester 4
            ('CS401', 'Database Management Systems', 4, 4, cse, btech_cse, False),
            ('CS402', 'Operating Systems Architecture', 4, 4, cse, btech_cse, False),
            ('CS403', 'Design and Analysis of Algorithms', 3, 4, cse, btech_cse, False),
            ('CS404', 'Computer Networks and Protocols', 3, 4, cse, btech_cse, False),
            ('CS405', 'Software Engineering Practices', 3, 4, cse, btech_cse, False),

            # CSE Semester 6
            ('CS601', 'Artificial Intelligence & Machine Learning', 4, 6, cse, btech_cse, False),
            ('CS602', 'Cloud Computing Systems', 3, 6, cse, btech_cse, False),
            ('CS603', 'Compiler Design', 3, 6, cse, btech_cse, False),

            # ECE Semester 4
            ('EC401', 'Microprocessors & Microcontrollers', 4, 4, ece, btech_ece, False),
            ('EC402', 'Signals and Communication Systems', 4, 4, ece, btech_ece, False),
        ]

        subjects = {}
        for code, title, credits, sem_num, dept, prog, is_elec in subjects_spec:
            s, _ = Subject.objects.get_or_create(
                code=code,
                defaults={
                    'title': title,
                    'credits': credits,
                    'semester': sem_num,
                    'department': dept,
                    'program': prog,
                    'is_elective': is_elec,
                    'min_attendance_pct': 75.0,
                    'condonation_min_pct': 65.0,
                }
            )
            subjects[code] = s

        # 9. Faculty Allocations (Assignments)
        allocations_spec = [
            ('fac_priya', 'CS401', sec_cse_4a),
            ('fac_priya', 'CS401', sec_cse_4b),
            ('fac_vikram', 'CS402', sec_cse_4a),
            ('fac_vikram', 'CS402', sec_cse_4b),
            ('hod_cse', 'CS403', sec_cse_4a),
            ('mentor_arun', 'CS404', sec_cse_4a),
            ('fac_kavita', 'CS405', sec_cse_4b),
            ('hod_cse', 'CS601', sec_cse_6a),
            ('fac_meenakshi', 'EC401', sec_ece_4a),
        ]

        allocations = []
        for fac_key, sub_code, sec in allocations_spec:
            alloc, _ = FacultyAllocation.objects.get_or_create(
                faculty=faculty_profiles[fac_key],
                subject=subjects[sub_code],
                section=sec,
                academic_year=ay,
                defaults={'is_active': True}
            )
            allocations.append(alloc)

        # 10. Student Cohorts and Course Enrollments
        student_data = [
            # Section 4-A Students
            ('24CSE001', 'Rahul', 'Sharma', sec_cse_4a, 4),
            ('24CSE002', 'Ananya', 'Iyer', sec_cse_4a, 4),
            ('24CSE003', 'Rohan', 'Verma', sec_cse_4a, 4),
            ('24CSE004', 'Sneha', 'Nair', sec_cse_4a, 4),
            ('24CSE005', 'Kavya', 'Reddy', sec_cse_4a, 4),
            ('24CSE006', 'Aditya', 'Mehta', sec_cse_4a, 4),
            ('24CSE007', 'Tanvi', 'Desai', sec_cse_4a, 4),
            ('24CSE008', 'Karthik', 'Swamy', sec_cse_4a, 4),

            # Section 4-B Students
            ('24CSE051', 'Manoj', 'Pandey', sec_cse_4b, 4),
            ('24CSE052', 'Divya', 'Prakash', sec_cse_4b, 4),
            ('24CSE053', 'Akash', 'Choudhury', sec_cse_4b, 4),
            ('24CSE054', 'Ritu', 'Agarwal', sec_cse_4b, 4),

            # Section 6-A Students
            ('22CSE010', 'Vikas', 'Gupta', sec_cse_6a, 6),
            ('22CSE011', 'Deepika', 'Menon', sec_cse_6a, 6),

            # Section ECE 4-A Students
            ('24ECE001', 'Nikhil', 'Joshi', sec_ece_4a, 4),
            ('24ECE002', 'Pooja', 'Hegde', sec_ece_4a, 4),
        ]

        cse_s4_subjects = [subjects['CS401'], subjects['CS402'], subjects['CS403'], subjects['CS404'], subjects['CS405']]
        cse_s6_subjects = [subjects['CS601'], subjects['CS602'], subjects['CS603']]
        ece_s4_subjects = [subjects['EC401'], subjects['EC402']]

        total_enrollments = 0
        for roll, fname, lname, sec, sem in student_data:
            u, _ = User.objects.get_or_create(
                username=roll.lower(),
                defaults={
                    'email': f"{roll.lower()}@edumerge.ac.in",
                    'first_name': fname,
                    'last_name': lname,
                    'role': Role.STUDENT,
                    'department': sec.program.department,
                    'password': stu_hash
                }
            )

            st, _ = Student.objects.get_or_create(
                user=u,
                defaults={
                    'roll_number': roll,
                    'registration_number': f"REG-2024-{roll}",
                    'section': sec,
                    'current_semester': sem,
                    'admission_date': date(2024, 8, 1),
                    'guardian_name': f"Parent of {fname}",
                    'guardian_phone': '+91 98765 00000'
                }
            )

            # Assign appropriate subject enrollments based on section
            if sec.program.code == 'BTECH-CSE' and sem == 4:
                target_subs = cse_s4_subjects
            elif sec.program.code == 'BTECH-CSE' and sem == 6:
                target_subs = cse_s6_subjects
            else:
                target_subs = ece_s4_subjects

            for sub in target_subs:
                ce, created = CourseEnrollment.objects.get_or_create(
                    student=st,
                    subject=sub,
                    academic_year=ay,
                    defaults={'section': sec, 'is_active': True}
                )
                if created:
                    total_enrollments += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded Phase 3 Academic Structure:\n"
            f"  • {Department.objects.count()} Departments\n"
            f"  • {Program.objects.count()} Degree Programs\n"
            f"  • {AcademicYear.objects.count()} Academic Years\n"
            f"  • {Semester.objects.count()} Semesters\n"
            f"  • {AcademicClass.objects.count()} Academic Classes\n"
            f"  • {Section.objects.count()} Sections (with assigned Class Mentors)\n"
            f"  • {Subject.objects.count()} Curriculum Subjects\n"
            f"  • {Faculty.objects.count()} Faculty Members\n"
            f"  • {FacultyAllocation.objects.count()} Faculty Teaching Allocations\n"
            f"  • {Student.objects.count()} Enrolled Students\n"
            f"  • {CourseEnrollment.objects.count()} Course Enrollments"
        ))
