from datetime import date, time
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User, Role
from academic.models import (
    Department, Program, AcademicYear, Section, Subject, Student, Faculty,
    FacultyAllocation, TimetableSlot, DayOfWeek
)
from attendance.models import (
    AttendanceSession, AttendanceRecord, AttendanceCorrection, AttendanceAuditLog,
    AttendanceStatus, SessionStatus, CorrectionStatus, AuditAction
)


class Command(BaseCommand):
    help = "Seeds database with Phase 1 initial demonstration data"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Phase 1 initial academic & attendance models..."))

        # 1. Departments
        cse, _ = Department.objects.get_or_create(code='CSE', defaults={'name': 'Computer Science & Engineering'})
        ece, _ = Department.objects.get_or_create(code='ECE', defaults={'name': 'Electronics & Communication'})
        mech, _ = Department.objects.get_or_create(code='MECH', defaults={'name': 'Mechanical Engineering'})
        it, _ = Department.objects.get_or_create(code='IT', defaults={'name': 'Information Technology'})

        # 2. Program
        btech_cse, _ = Program.objects.get_or_create(
            department=cse,
            code='BTECH-CSE',
            defaults={'name': 'Bachelor of Technology in Computer Science', 'total_semesters': 8}
        )

        # 3. Academic Year
        ay, _ = AcademicYear.objects.get_or_create(
            year_label='2026-2027',
            defaults={
                'start_date': date(2026, 7, 15),
                'end_date': date(2027, 5, 20),
                'is_current': True
            }
        )

        # 4. Key Persona Users
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'dean.academics@edumerge.ac.in',
                'first_name': 'Dr. K. R.',
                'last_name': 'Sundaram',
                'role': Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('Admin@123')
        admin_user.save()

        hod_user, _ = User.objects.get_or_create(
            username='hod_cse',
            defaults={
                'email': 'hod.cse@edumerge.ac.in',
                'first_name': 'Dr. Rajesh',
                'last_name': 'Deshmukh',
                'role': Role.HOD,
                'department': cse
            }
        )
        hod_user.set_password('Hod@123')
        hod_user.save()

        fac1_user, _ = User.objects.get_or_create(
            username='fac_priya',
            defaults={
                'email': 'priya.n@edumerge.ac.in',
                'first_name': 'Dr. Priya',
                'last_name': 'Natarajan',
                'role': Role.FACULTY,
                'department': cse
            }
        )
        fac1_user.set_password('Faculty@123')
        fac1_user.save()

        mentor_user, _ = User.objects.get_or_create(
            username='mentor_arun',
            defaults={
                'email': 'arun.kumar@edumerge.ac.in',
                'first_name': 'Prof. Arun',
                'last_name': 'Kumar',
                'role': Role.MENTOR,
                'department': cse
            }
        )
        mentor_user.set_password('Mentor@123')
        mentor_user.save()

        # Faculty Profiles
        fac_profile1, _ = Faculty.objects.get_or_create(
            user=fac1_user,
            defaults={'employee_id': 'FAC-CSE-101', 'designation': 'Associate Professor', 'department': cse}
        )
        mentor_profile, _ = Faculty.objects.get_or_create(
            user=mentor_user,
            defaults={'employee_id': 'FAC-CSE-108', 'designation': 'Assistant Professor & Mentor', 'department': cse}
        )

        # 5. Section with Mentor
        sec_4a, _ = Section.objects.get_or_create(
            program=btech_cse,
            academic_year=ay,
            semester=4,
            name='A',
            defaults={'mentor': mentor_user}
        )

        # 6. Subjects
        sub_dbms, _ = Subject.objects.get_or_create(
            department=cse,
            code='CS401',
            defaults={'title': 'Database Management Systems', 'credits': 4, 'semester': 4, 'min_attendance_pct': 75.0, 'condonation_min_pct': 65.0}
        )
        sub_os, _ = Subject.objects.get_or_create(
            department=cse,
            code='CS402',
            defaults={'title': 'Operating Systems Architecture', 'credits': 4, 'semester': 4, 'min_attendance_pct': 75.0, 'condonation_min_pct': 65.0}
        )
        sub_algo, _ = Subject.objects.get_or_create(
            department=cse,
            code='CS403',
            defaults={'title': 'Design and Analysis of Algorithms', 'credits': 3, 'semester': 4, 'min_attendance_pct': 75.0, 'condonation_min_pct': 65.0}
        )

        # 7. Faculty Allocations
        alloc_dbms, _ = FacultyAllocation.objects.get_or_create(
            faculty=fac_profile1,
            subject=sub_dbms,
            section=sec_4a,
            academic_year=ay
        )
        alloc_os, _ = FacultyAllocation.objects.get_or_create(
            faculty=mentor_profile,
            subject=sub_os,
            section=sec_4a,
            academic_year=ay
        )

        # 8. Timetable Slots
        TimetableSlot.objects.get_or_create(
            allocation=alloc_dbms,
            day_of_week=DayOfWeek.MONDAY,
            period_number=1,
            defaults={'start_time': time(9, 0), 'end_time': time(9, 50), 'room_number': 'LH-302'}
        )
        TimetableSlot.objects.get_or_create(
            allocation=alloc_os,
            day_of_week=DayOfWeek.MONDAY,
            period_number=2,
            defaults={'start_time': time(10, 0), 'end_time': time(10, 50), 'room_number': 'LH-302'}
        )

        # 9. Students Roster for Section 4A
        student_samples = [
            ('24CSE001', 'Rahul', 'Sharma', 'rahul.s@edumerge.ac.in'),
            ('24CSE002', 'Ananya', 'Iyer', 'ananya.i@edumerge.ac.in'),
            ('24CSE003', 'Rohan', 'Verma', 'rohan.v@edumerge.ac.in'),
            ('24CSE004', 'Sneha', 'Nair', 'sneha.n@edumerge.ac.in'),
            ('24CSE005', 'Kavya', 'Reddy', 'kavya.r@edumerge.ac.in'),
            ('24CSE006', 'Aditya', 'Mehta', 'aditya.m@edumerge.ac.in'),
            ('24CSE007', 'Tanvi', 'Desai', 'tanvi.d@edumerge.ac.in'),
            ('24CSE008', 'Karthik', 'Swamy', 'karthik.s@edumerge.ac.in'),
        ]

        students = []
        for roll, fname, lname, email in student_samples:
            s_user, _ = User.objects.get_or_create(
                username=roll.lower(),
                defaults={
                    'email': email,
                    'first_name': fname,
                    'last_name': lname,
                    'role': Role.STUDENT,
                    'department': cse
                }
            )
            s_user.set_password('Student@123')
            s_user.save()

            st, _ = Student.objects.get_or_create(
                user=s_user,
                defaults={
                    'roll_number': roll,
                    'registration_number': f"REG-2024-{roll}",
                    'section': sec_4a,
                    'current_semester': 4,
                    'admission_date': date(2024, 8, 1),
                    'guardian_name': f"Parent of {fname}",
                    'guardian_phone': '+91 98765 43210'
                }
            )
            students.append(st)

        # 10. Sample Attendance Session
        session, _ = AttendanceSession.objects.get_or_create(
            section=sec_4a,
            subject=sub_dbms,
            session_date=date(2026, 9, 24),
            period_number=1,
            defaults={
                'faculty': fac1_user,
                'status': SessionStatus.SUBMITTED,
                'topic_covered': 'B+ Trees and Relational Indexing Mechanics'
            }
        )

        # Sample Records
        status_map = {
            '24CSE001': AttendanceStatus.PRESENT,
            '24CSE002': AttendanceStatus.PRESENT,
            '24CSE003': AttendanceStatus.ABSENT,
            '24CSE004': AttendanceStatus.PRESENT,
            '24CSE005': AttendanceStatus.LATE,
            '24CSE006': AttendanceStatus.PRESENT,
            '24CSE007': AttendanceStatus.PRESENT,
            '24CSE008': AttendanceStatus.ABSENT,
        }

        records = {}
        for st in students:
            rec_status = status_map.get(st.roll_number, AttendanceStatus.PRESENT)
            rec, _ = AttendanceRecord.objects.get_or_create(
                session=session,
                student=st,
                defaults={'status': rec_status, 'remarks': 'Marked during regular morning lecture'}
            )
            records[st.roll_number] = rec

        # 11. Sample Correction Dispute and Audit Log for 24CSE003
        disputed_rec = records.get('24CSE003')
        if disputed_rec:
            corr, _ = AttendanceCorrection.objects.get_or_create(
                record=disputed_rec,
                defaults={
                    'requested_by': disputed_rec.student.user,
                    'old_status': AttendanceStatus.ABSENT,
                    'requested_status': AttendanceStatus.ON_DUTY,
                    'reason': 'Represented institution at National Smart India Hackathon',
                    'document_url': 'https://edumerge-college.ac.in/docs/od_sih_2026.pdf',
                    'status': CorrectionStatus.PENDING
                }
            )

            # Create initial audit log for session recording
            AttendanceAuditLog.objects.get_or_create(
                record=disputed_rec,
                action=AuditAction.SESSION_CREATED,
                defaults={
                    'previous_status': '',
                    'new_status': AttendanceStatus.ABSENT,
                    'changed_by': fac1_user,
                    'reason': 'Initial roll-call submission by Dr. Priya Natarajan',
                    'ip_address': '192.168.1.104'
                }
            )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded Phase 1 models:\n"
            f"  • {Department.objects.count()} Departments\n"
            f"  • {Program.objects.count()} Programs\n"
            f"  • {Section.objects.count()} Sections with Mentor\n"
            f"  • {Subject.objects.count()} Subjects\n"
            f"  • {Faculty.objects.count()} Faculty\n"
            f"  • {Student.objects.count()} Students\n"
            f"  • {AttendanceSession.objects.count()} Conducted Attendance Session\n"
            f"  • {AttendanceRecord.objects.count()} Period Attendance Records\n"
            f"  • {AttendanceCorrection.objects.count()} Correction Dispute\n"
            f"  • {AttendanceAuditLog.objects.count()} Audit Log Entry"
        ))
